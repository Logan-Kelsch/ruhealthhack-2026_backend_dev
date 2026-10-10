import { useEffect, useMemo, useRef, useState } from "react";
import { asApiError, api, type ApiClient, type PublicChartEntry, type PublicEncounter } from "../../api/client";
import type { components } from "../../api/schema";
import type { Go, StudentRoute } from "../../app/types";
import { Documentation } from "./Documentation";
import { PatientCall } from "../../components/PatientCall";
import { GhostButton, Wordmark } from "../../components/ui";
import { stopOwnedAudio as stopPageAudio, type ScribeConnector, type ScribeEvent } from "../../voice/scribe";
import { connectElevenLabsScribe } from "../../voice/scribeLive";
import {
  createBrowserVoice,
  createMpegPlayback,
  observeFirstAudioByte,
  verifiedAudioSource,
  type BrowserVoice,
  type SpeechPlayback,
} from "../../voice/speech";

type TurnResult = components["schemas"]["TurnResult"];
type TranscriptEntry = components["schemas"]["TranscriptEntry"];

type LoadState =
  | { kind: "missing" }
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; encounter: PublicEncounter };

type VoiceState = "off" | "connecting" | "live" | "muted";

const UNCERTAIN = "This turn may not have been saved. The saved visit is shown. It was not sent again.";

// The live visit. Speech goes through Scribe, and only committed turns hit the encounter API.
export function Encounter({
  route,
  client = api,
  connectScribe = connectElevenLabsScribe,
  stopOwnedAudio = stopPageAudio,
  playSpeech,
  browserVoice,
  now = monotonicNow,
  timingOrigin = "live",
  go,
}: {
  route: StudentRoute;
  client?: ApiClient;
  connectScribe?: ScribeConnector;
  stopOwnedAudio?: () => void;
  playSpeech?: SpeechPlayback;
  browserVoice?: BrowserVoice;
  // Tests pass a fixture clock. The visit itself uses a monotonic clock.
  now?: () => number;
  timingOrigin?: "live" | "fixture";
  go?: Go;
}) {
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<LoadState>(route.encounterId ? { kind: "loading" } : { kind: "missing" });
  // One player and one browser voice for this screen. Tests pass their own.
  const playback = useMemo(() => playSpeech ?? createMpegPlayback(), [playSpeech]);
  const spoken = useMemo(() => browserVoice ?? createBrowserVoice(), [browserVoice]);

  useEffect(() => {
    if (!route.encounterId) {
      setLoad({ kind: "missing" });
      return;
    }
    let cancelled = false;
    setLoad({ kind: "loading" });
    const encounterId = route.encounterId;
    // Refresh reads the saved encounter. It does not call the start route or open the microphone.
    client
      .GET("/api/encounters/{enc_id}", { params: { path: { enc_id: encounterId } } })
      .then((result) => {
        if (cancelled) return;
        if (!result.response?.ok || !result.data) {
          const status = result.response?.status ?? 0;
          setLoad({ kind: "error", message: asApiError(status, result.error).message });
          return;
        }
        setLoad({ kind: "ready", encounter: result.data });
      })
      .catch(() => {
        if (!cancelled) setLoad({ kind: "error", message: "The encounter could not be loaded." });
      });
    return () => {
      cancelled = true;
    };
  }, [client, route.encounterId, attempt]);

  if (load.kind === "missing") {
    return <p className="px-6 py-8 text-sm text-muted">This visit has not been started.</p>;
  }
  if (load.kind === "loading") {
    return <p className="px-6 py-8 text-sm text-muted">Loading the encounter</p>;
  }
  if (load.kind === "error") {
    return (
      <div className="flex flex-col items-start gap-3 px-6 py-8">
        <p className="text-sm text-ink">{load.message}</p>
        <GhostButton onClick={() => setAttempt((value) => value + 1)}>Retry</GhostButton>
      </div>
    );
  }
  return (
    <EncounterLive
      initial={load.encounter}
      client={client}
      connectScribe={connectScribe}
      stopOwnedAudio={stopOwnedAudio}
      playback={playback}
      browserVoice={spoken}
      now={now}
      timingOrigin={timingOrigin}
      go={go}
    />
  );
}

// Patient in the center, transcript under the patient, notes on the left, chart on the right.
function EncounterLive({
  initial,
  client,
  connectScribe,
  stopOwnedAudio,
  playback,
  browserVoice,
  now,
  timingOrigin,
  go,
}: {
  initial: PublicEncounter;
  client: ApiClient;
  connectScribe: ScribeConnector;
  stopOwnedAudio: () => void;
  playback: SpeechPlayback;
  browserVoice: BrowserVoice;
  now: () => number;
  timingOrigin: "live" | "fixture";
  go?: Go;
}) {
  const [view, setView] = useState(initial);
  const [voice, setVoice] = useState<VoiceState>("off");
  const [partial, setPartial] = useState("");
  const [banner, setBanner] = useState<string | null>(null);
  const [notices, setNotices] = useState<string[]>([]);
  const [voiceLabel, setVoiceLabel] = useState<string | null>(null);
  // Mirrors speechActiveRef for the call frame's speaking glow. Display only.
  const [speaking, setSpeaking] = useState(false);
  const sessionRef = useRef<Awaited<ReturnType<ScribeConnector>> | null>(null);
  const queueRef = useRef(Promise.resolve());
  const closedRef = useRef(false);
  const mutedRef = useRef(false);
  const ttsRef = useRef(false);
  const speechQueueRef = useRef<{ turn: number; text: string }[]>([]);
  const drainingRef = useRef(false);
  const speechActiveRef = useRef(false);
  const bargeMsRef = useRef<number | undefined>(undefined);
  const abortRef = useRef<AbortController | null>(null);
  // Commit time for each saved turn, so later speech marks use the same clock.
  const timingRef = useRef(new Map<number, { committedAt: number; verifiedReplyArrivalMs: number }>());
  const encounterId = view.encounter_id;

  // Drops queued replies and the stream that is playing. Leaving is not an interruption.
  function stopSpeech() {
    speechQueueRef.current = [];
    speechActiveRef.current = false;
    setSpeaking(false);
    abortRef.current?.abort();
    playback.stop();
    browserVoice.cancel();
  }

  useEffect(() => {
    return () => {
      // Leaving the screen stops the mic, the provider socket, and any audio we started.
      closedRef.current = true;
      sessionRef.current?.stop();
      sessionRef.current = null;
      stopSpeech();
      stopOwnedAudio();
    };
  }, [browserVoice, playback, stopOwnedAudio]);

  // Turns one Scribe event into a caption, a queued turn, or a visible failure.
  function onEvent(event: ScribeEvent) {
    if (closedRef.current) return;
    switch (event.type) {
      case "partial":
        if (mutedRef.current) return;
        // Student speech stops the patient. The microphone stays open.
        if (speechActiveRef.current || drainingRef.current) interruptSpeech();
        setPartial(event.text);
        return;
      case "committed":
        if (mutedRef.current) return;
        setPartial("");
        queueRef.current = queueRef.current.then(() => submitCommitted(event)).catch(() => undefined);
        return;
      case "disconnected":
        sessionRef.current = null;
        setVoice("off");
        setPartial("");
        setBanner("The transcription service disconnected. Connect the microphone again.");
        return;
      case "token_expired":
        sessionRef.current?.stop();
        sessionRef.current = null;
        setVoice("off");
        setPartial("");
        setBanner("The transcription token expired. Connect the microphone again.");
        return;
      case "error":
        setBanner(event.message);
        return;
      default: {
        const unreachable: never = event;
        return unreachable;
      }
    }
  }

  // A click opens the mic. Refresh does not, because the browser requires a user action.
  async function connect() {
    if (closedRef.current || voice === "connecting") return;
    setBanner(null);
    setVoice("connecting");
    const configResult = await client.GET("/api/config");
    if (!configResult.data) {
      setVoice("off");
      setBanner(asApiError(configResult.response?.status ?? 0, configResult.error).message);
      return;
    }
    const tokenResult = await client.POST("/api/stt/token");
    if (!tokenResult.data) {
      setVoice("off");
      setBanner(asApiError(tokenResult.response?.status ?? 0, tokenResult.error).message);
      return;
    }
    const config = configResult.data;
    try {
      const session = await connectScribe({
        token: tokenResult.data.token,
        modelId: config.stt_model_id,
        vadSilenceSecs: config.vad_silence_secs,
        vadThreshold: config.vad_threshold,
        echoCancellation: true,
        noiseSuppression: true,
        includeTimestamps: config.include_timestamps,
        onEvent,
      });
      if (closedRef.current) {
        session.stop();
        return;
      }
      sessionRef.current = session;
      mutedRef.current = false;
      ttsRef.current = config.tts;
      setVoice("live");
    } catch (error) {
      setVoice("off");
      setBanner(permissionMessage(error));
    }
  }

  // Privacy mute stays on the same connection. It is not a push-to-talk control.
  function toggleMute() {
    const session = sessionRef.current;
    if (!session) return;
    if (mutedRef.current) {
      mutedRef.current = false;
      session.unmute();
      setVoice("live");
      return;
    }
    mutedRef.current = true;
    session.mute();
    setPartial("");
    setVoice("muted");
  }

  // Sends one committed turn. The queue calls this only after the previous turn has a result.
  async function submitCommitted(event: Extract<ScribeEvent, { type: "committed" }>) {
    if (closedRef.current) return;
    // Stamp before the request so reply arrival includes the wait, not only the handling after it.
    const committedAt = now();
    try {
      const result = await client.POST("/api/encounters/{enc_id}/utterances", {
        params: { path: { enc_id: encounterId } },
        body: utteranceBody(event),
      });
      if (closedRef.current) return;
      if (!result.response || result.data === undefined) {
        if (!result.response) {
          await reconcile();
          return;
        }
        setBanner(asApiError(result.response.status, result.error).message);
        return;
      }
      timingRef.current.set(result.data.turn, {
        committedAt,
        verifiedReplyArrivalMs: Math.round(now() - committedAt),
      });
      applyTurn(result.data, event.text);
    } catch {
      // No response means we cannot tell whether the turn was saved. Do not send it again.
      if (!closedRef.current) await reconcile();
    }
  }

  // Loads the saved visit after a turn with no response. It does not submit the turn again.
  async function reconcile() {
    try {
      const result = await client.GET("/api/encounters/{enc_id}", { params: { path: { enc_id: encounterId } } });
      if (result.data) setView(result.data);
      setBanner(UNCERTAIN);
    } catch {
      setBanner(UNCERTAIN);
    }
  }

  // Copies the reply and the released rows onto the screen. The fact ids stay on those rows.
  function applyTurn(turn: TurnResult, studentText: string) {
    setNotices((turn.notices ?? []).map((notice) => notice.text));
    setView((current) => {
      const chart = mergeChart(current.chart ?? [], [...(turn.chart_releases ?? []), ...(turn.exam_results ?? [])]);
      const previous = (current.transcript ?? []).map((line) => ({ ...line, is_last: false }));
      const entry: TranscriptEntry = {
        turn: turn.turn,
        student_text: studentText,
        reply_text: turn.reply_text,
        mode: turn.mode,
        is_last: true,
      };
      return { ...current, chart, transcript: [...previous, entry], last_turn: turn.turn };
    });
    enqueueSpeech(turn.turn, turn.reply_text);
  }

  // Builds the saved-turn request. Remaining audio is included only when playback reported it.
  function utteranceBody(event: Extract<ScribeEvent, { type: "committed" }>) {
    const body: {
      text: string;
      start_ms: number | null;
      end_ms: number | null;
      words: { text: string; start_ms: number; end_ms: number }[];
      barge_in_remaining_ms?: number;
    } = {
      text: event.text,
      start_ms: event.startMs,
      end_ms: event.endMs,
      words: event.words.map((word) => ({ text: word.text, start_ms: word.startMs, end_ms: word.endMs })),
    };
    if (typeof bargeMsRef.current === "number") {
      body.barge_in_remaining_ms = bargeMsRef.current;
      bargeMsRef.current = undefined;
    }
    return body;
  }

  // Keeps the reply that just arrived behind any reply still playing.
  function enqueueSpeech(turn: number, text: string) {
    speechQueueRef.current.push({ turn, text });
    speechActiveRef.current = true;
    setSpeaking(true);
    void drainSpeech();
  }

  // Plays one saved reply at a time. A barge-in clears the queue from under this loop.
  async function drainSpeech() {
    if (drainingRef.current) return;
    drainingRef.current = true;
    while (speechQueueRef.current.length > 0 && !closedRef.current) {
      const next = speechQueueRef.current.shift();
      if (!next) break;
      await playVerified(next.turn, next.text);
    }
    drainingRef.current = false;
    speechActiveRef.current = speechQueueRef.current.length > 0;
    setSpeaking(speechActiveRef.current);
  }

  // Stops what is playing and what is waiting. Transcription is left running.
  function interruptSpeech() {
    const remaining = playback.remainingMs();
    // No duration means we do not invent how much of a sentence was left.
    if (typeof remaining === "number") bargeMsRef.current = remaining;
    stopSpeech();
  }

  // Milliseconds since this turn was committed. No saved commit means the mark stays missing.
  function sinceCommit(turn: number): number | null {
    const pending = timingRef.current.get(turn);
    if (!pending) return null;
    return Math.round(now() - pending.committedAt);
  }

  // Stores the client clock for one turn. A failed post leaves the sample missing.
  async function reportTiming(
    turn: number,
    marks: {
      speechRequestMs: number | null;
      firstAudioBytesMs: number | null;
      firstPlaybackMs: number | null;
      speechPath: "vendor" | "browser" | "none";
      error: string | null;
    },
  ) {
    const pending = timingRef.current.get(turn);
    if (!pending) return;
    try {
      await client.POST("/api/encounters/{enc_id}/turns/{turn}/timings", {
        params: { path: { enc_id: encounterId, turn } },
        body: {
          verified_reply_arrival_ms: pending.verifiedReplyArrivalMs,
          speech_request_ms: marks.speechRequestMs,
          first_audio_bytes_ms: marks.firstAudioBytesMs,
          first_playback_ms: marks.firstPlaybackMs,
          origin: timingOrigin,
          speech_path: marks.speechPath,
          error: marks.error,
        },
      });
    } catch {
      // The caption and the reply are already saved. Losing the timing row does not change them.
    }
  }

  // Speaks one verified reply. The caption is already on screen before this runs.
  async function playVerified(turn: number, text: string) {
    if (closedRef.current) return;
    const marks = {
      speechRequestMs: null as number | null,
      firstAudioBytesMs: null as number | null,
      firstPlaybackMs: null as number | null,
      speechPath: "none" as "vendor" | "browser" | "none",
      error: null as string | null,
    };
    let reported = false;
    // One sample per turn. The first moment we know the outcome is enough.
    async function send() {
      if (reported) return;
      reported = true;
      await reportTiming(turn, marks);
    }
    if (!ttsRef.current) {
      browserVoice.speak(text);
      setVoiceLabel("Browser voice");
      marks.speechPath = "browser";
      marks.firstPlaybackMs = sinceCommit(turn);
      await send();
      return;
    }
    marks.speechPath = "vendor";
    marks.speechRequestMs = sinceCommit(turn);
    const controller = new AbortController();
    abortRef.current = controller;
    setVoiceLabel(null);
    try {
      const result = await client.POST("/api/encounters/{enc_id}/turns/{turn}/speech", {
        params: { path: { enc_id: encounterId, turn } },
        parseAs: "stream",
        signal: controller.signal,
      });
      if (controller.signal.aborted || closedRef.current) {
        await send();
        return;
      }
      if (result.response?.status === 204) {
        browserVoice.speak(text);
        setVoiceLabel("Browser voice");
        // No vendor bytes arrived. Playback is the browser voice, if it started.
        marks.speechPath = "browser";
        marks.firstPlaybackMs = sinceCommit(turn);
        await send();
        return;
      }
      if (!result.response?.ok || !result.data) {
        marks.error = asApiError(result.response?.status ?? 0, result.error).message;
        setBanner(marks.error);
        await send();
        return;
      }
      const source = observeFirstAudioByte(verifiedAudioSource(result.data, controller), () => {
        if (marks.firstAudioBytesMs === null) marks.firstAudioBytesMs = sinceCommit(turn);
      });
      await playback.play(source, {
        onFirstPlayback() {
          if (marks.firstPlaybackMs === null) marks.firstPlaybackMs = sinceCommit(turn);
          // Report at the start. Waiting for the sentence to finish would hide the playback time.
          void send();
        },
      });
      await send();
    } catch {
      if (!(controller.signal.aborted || closedRef.current)) {
        marks.error = "The reply could not be played. The caption is still shown.";
        setBanner(marks.error);
      }
      await send();
    }
  }

  // Ending drops queued speech and anything still playing, then marks the visit ended.
  async function endVisit() {
    closedRef.current = true;
    sessionRef.current?.stop();
    sessionRef.current = null;
    setVoice("off");
    setPartial("");
    stopSpeech();
    stopOwnedAudio();
    const result = await client.POST("/api/encounters/{enc_id}/end", { params: { path: { enc_id: encounterId } } });
    if (result.data) setView(result.data);
    else setBanner(asApiError(result.response?.status ?? 0, result.error).message);
  }

  const chart = view.chart ?? [];
  const notes = chart.filter((item) => item.kind === "artifact");
  const exams = chart.filter((item) => item.kind === "exam");
  const released = chart.filter((item) => item.kind !== "artifact" && item.kind !== "exam");
  const patient = view.patient;
  const simplified = (view.transcript ?? []).some((line) => line.mode === "template");
  const active = view.status === "active";
  // The note opens only after the visit has ended, and only with the template the case saved.
  const template = view.documentation_template;
  const showDocumentation = !active && template !== undefined && template.fields.length > 0;

  return (
    <div className="relative flex h-full min-h-[700px] flex-col overflow-auto text-ink">
      <div className="bg-world fixed inset-0" aria-hidden />

      <header className="relative flex flex-wrap items-center justify-between gap-4 px-[clamp(24px,3vw,48px)] pt-5 pb-3">
        <div className="flex items-center gap-5">
          <Wordmark size="md" />
          <span className="rounded-full bg-white/75 px-4 py-1.5 font-serif text-[17px] backdrop-blur-sm">{view.visit_label}</span>
          <span className="font-sans text-[13px] text-ink-soft">{timingLabel(view.started_at, view.ended_at)}</span>
        </div>
        <div className="flex items-center gap-4">
          {active ? (
            <button
              type="button"
              onClick={() => {
                if (voice === "live" || voice === "muted") toggleMute();
                else void connect();
              }}
              disabled={voice === "connecting"}
              className="inline-flex h-[54px] items-center gap-3 rounded-full border border-indigo-line/50 bg-white/85 px-6 font-serif text-[20px] backdrop-blur-sm hover:bg-white disabled:opacity-70"
            >
              <span className={`size-3.5 rounded-full ${voice === "live" ? "rnd-blink bg-bright" : "bg-inactive"}`} />
              {micLabel(voice)}
            </button>
          ) : (
            <span className="rounded-full bg-white/80 px-5 py-2.5 font-serif text-[18px] text-ink-soft backdrop-blur-sm">This visit has ended.</span>
          )}
          <button
            type="button"
            onClick={() => void endVisit()}
            disabled={!active}
            className="h-[54px] rounded-full bg-danger px-7 font-serif text-[20px] text-white shadow-[0_12px_26px_-14px_rgba(200,50,50,.8)] hover:brightness-95 disabled:bg-inactive disabled:shadow-none"
          >
            End visit
          </button>
        </div>
      </header>

      <div className="relative mx-auto grid w-full max-w-[1680px] flex-1 items-start gap-5 px-[clamp(16px,2.4vw,40px)] pt-2 pb-8 lg:grid-cols-[minmax(240px,300px)_minmax(0,1fr)_minmax(260px,320px)]">
        <aside aria-label="Visit notes" className="flex flex-col gap-4">
          <section className="rounded-[18px] bg-panel px-5 py-4 text-white shadow-[0_18px_40px_-24px_rgba(25,31,92,.7)]">
            <div className="font-sans text-[11.5px] font-semibold tracking-[0.6px] text-indigo-on-ink uppercase">Goal</div>
            <div className="mt-1 font-serif text-[21px] leading-snug">{view.briefing.goal}</div>
          </section>
          <section className="rounded-[18px] border border-white/70 bg-card/85 shadow-[0_18px_40px_-28px_rgba(25,31,92,.5)] backdrop-blur-md px-5 py-4">
            <div className="font-serif text-[22px]">Referral</div>
            {notes.length === 0 ? <div className="mt-1 font-serif text-[17px] text-ink-soft">No referral has been released.</div> : null}
            {notes.map((note) => (
              <div key={note.ref} className="mt-2">
                <div className="font-serif text-[18px]">{note.label}</div>
                {note.body ? <div className="mt-1 font-serif text-[17px] leading-snug text-ink-soft">{note.body}</div> : null}
                <Provenance item={note} />
              </div>
            ))}
          </section>
          <section className="rounded-[18px] border border-white/70 bg-card/85 shadow-[0_18px_40px_-28px_rgba(25,31,92,.5)] backdrop-blur-md overflow-hidden">
            <div className="px-5 pt-4 pb-2 font-serif text-[22px]">Exam log</div>
            {exams.length === 0 ? <div className="px-5 pb-4 font-serif text-[17px] text-ink-soft">No exam has been released.</div> : null}
            {exams.map((exam) => (
              <div key={exam.ref} className="border-t border-hair px-5 py-3 font-serif text-[17px]">
                <div>{exam.label}</div>
                {exam.value ? <div className="text-ink-soft">{exam.value}</div> : null}
                <Provenance item={exam} />
              </div>
            ))}
          </section>
        </aside>

        <div className="flex min-w-0 flex-col gap-4">
          <section aria-label="Patient" className="rounded-[18px] border border-white/70 bg-card/85 shadow-[0_18px_40px_-28px_rgba(25,31,92,.5)] backdrop-blur-md p-3">
            <PatientCall name={patient.speaker || patient.name} speaking={speaking} muted={voice === "muted"} listening={voice === "live"} />
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-2 pt-3 pb-1">
              <div className="font-serif text-[clamp(26px,2.2vw,34px)] leading-none tracking-[-0.6px]">
                {patient.name}, {patient.age}
              </div>
              <div className="font-sans text-[13px] text-ink-soft">
                {statusLabel(voice, active)} · Headphones recommended, so the patient's voice doesn't echo
              </div>
            </div>
          </section>
          <section aria-label="Transcript" className="rounded-[18px] border border-white/70 bg-card/85 shadow-[0_18px_40px_-28px_rgba(25,31,92,.5)] backdrop-blur-md flex flex-col gap-3 px-5 py-4">
            {banner ? <p className="font-serif text-[17px] text-ink">{banner}</p> : null}
            {voiceLabel ? <p className="font-serif text-[17px] text-ink">{voiceLabel}</p> : null}
            {simplified || notices.includes("Simplified responses") ? (
              <p className="font-sans text-[13px] text-ink-soft">Simplified responses</p>
            ) : null}
            {notices
              .filter((notice) => notice !== "Simplified responses")
              .map((notice) => (
                <p key={notice} className="font-sans text-[13px] text-ink-soft">
                  {notice}
                </p>
              ))}
            {(view.transcript ?? []).length === 0 && !partial ? <p className="font-serif text-[17px] text-ink-soft">No transcript yet.</p> : null}
            {(view.transcript ?? []).map((line) => (
              <div key={line.turn} className="flex flex-col gap-2">
                <TurnLine who="Student" text={line.student_text} align="end" />
                <TurnLine who={patient.speaker || patient.name} text={line.reply_text} align="start" />
                {line.is_last ? <div className="font-sans text-[11.5px] font-semibold text-muted">Latest turn</div> : null}
              </div>
            ))}
            {partial ? <p className="font-serif text-[17px] text-ink-soft italic">{partial}</p> : null}
          </section>
          {showDocumentation && view.status !== "active" ? (
            <Documentation
              template={template}
              saved={view.saved_documentation ?? null}
              status={view.status}
              encounterId={view.encounter_id}
              client={client}
              connectScribe={connectScribe}
              go={go}
            />
          ) : null}
        </div>

        <aside aria-label="Chart" className="flex flex-col gap-4">
          {groupChart(released).map((group) => (
            <section key={group.section} className="rounded-[18px] border border-white/70 bg-card/85 shadow-[0_18px_40px_-28px_rgba(25,31,92,.5)] backdrop-blur-md overflow-hidden">
              <div className="px-5 pt-4 pb-2 font-serif text-[22px]">{group.section}</div>
              {group.items.map((item) => (
                <div key={`${item.kind}-${item.ref}`} className="border-t border-hair px-5 py-3">
                  <div className="font-serif text-[18px]">{item.label}</div>
                  {item.value ? <div className="font-serif text-[17px] text-ink-soft tabular-nums">{item.value}</div> : null}
                  <Provenance item={item} />
                </div>
              ))}
            </section>
          ))}
          {released.length === 0 ? (
            <section className="rounded-[18px] border border-white/70 bg-card/85 shadow-[0_18px_40px_-28px_rgba(25,31,92,.5)] backdrop-blur-md px-5 py-4 font-serif text-[17px] text-ink-soft">No chart entries have been released.</section>
          ) : null}
        </aside>
      </div>
    </div>
  );
}

// A denied prompt is named by the browser. Anything else is the provider not connecting.
function permissionMessage(error: unknown): string {
  if (typeof error === "object" && error !== null && "name" in error && error.name === "NotAllowedError") {
    return "Microphone permission was denied.";
  }
  return "The transcription service could not be reached.";
}

// The button name is the next action: connect, mute, or unmute.
function micLabel(voice: VoiceState): string {
  switch (voice) {
    case "off":
      return "Connect microphone";
    case "connecting":
      return "Connecting microphone";
    case "live":
      return "Mute microphone";
    case "muted":
      return "Unmute microphone";
    default: {
      const unreachable: never = voice;
      return unreachable;
    }
  }
}

// Short status under the patient. Color is not the only signal; the words say the state.
function statusLabel(voice: VoiceState, active: boolean): string {
  if (!active) return "This visit has ended.";
  switch (voice) {
    case "off":
      return "Connect the microphone to speak.";
    case "connecting":
      return "Connecting microphone";
    case "live":
      return "Microphone live";
    case "muted":
      return "Microphone muted";
    default: {
      const unreachable: never = voice;
      return unreachable;
    }
  }
}

// Keeps doorway rows and adds the rows this turn released. A repeated ref is replaced.
function mergeChart(current: PublicChartEntry[], incoming: PublicChartEntry[]): PublicChartEntry[] {
  const next = [...current];
  for (const item of incoming) {
    const index = next.findIndex((row) => row.kind === item.kind && row.ref === item.ref);
    if (index >= 0) next[index] = item;
    else next.push(item);
  }
  return next;
}

// A monotonic clock when the browser has one, so a timing mark is not a wall-clock jump.
function monotonicNow(): number {
  if (typeof performance !== "undefined" && typeof performance.now === "function") return performance.now();
  return Date.now();
}

// Shows the saved start or end time. The clock is the saved time, not a running timer.
function timingLabel(startedAt: string | null | undefined, endedAt: string | null | undefined): string {
  if (endedAt) return `Ended ${endedAt}`;
  if (startedAt) return `Started ${startedAt}`;
  return "Not started";
}

// Keeps the fact id and the source kind on screen so a released value can be traced.
function Provenance({ item }: { item: PublicChartEntry }) {
  if (!item.source_fact && !item.source?.kind) return null;
  return (
    <div className="mt-0.5 text-xs text-muted">
      {item.source_fact ? <span>Fact {item.source_fact}</span> : null}
      {item.source_fact && item.source?.kind ? <span> · </span> : null}
      {item.source?.kind ? <span>Source: {item.source.kind}</span> : null}
    </div>
  );
}

// Groups released rows by chart section without dropping their order.
function groupChart(items: PublicChartEntry[]): { section: string; items: PublicChartEntry[] }[] {
  const groups: { section: string; items: PublicChartEntry[] }[] = [];
  for (const item of items) {
    const section = item.section || "Chart";
    const existing = groups.find((group) => group.section === section);
    if (existing) existing.items.push(item);
    else groups.push({ section, items: [item] });
  }
  return groups;
}

// One transcript bubble. align puts the student on the right and the patient on the left.
function TurnLine({ who, text, align }: { who: string; text: string; align: "start" | "end" }) {
  const student = align === "end";
  return (
    <div className={`flex flex-col gap-0.5 ${student ? "items-end" : "items-start"}`}>
      <span className="px-1 text-[11.5px] font-semibold text-muted">{who}</span>
      <div className={`max-w-[88%] rounded-[16px] px-4 py-2.5 font-serif text-[18px] leading-snug ${student ? "bg-panel text-white" : "bg-indigo-soft text-ink"}`}>
        {text}
      </div>
    </div>
  );
}
