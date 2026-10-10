import { useEffect, useRef, useState } from "react";
import { asApiError, api, type ApiClient, type PublicChartEntry, type PublicEncounter } from "../../api/client";
import type { components } from "../../api/schema";
import type { Go, StudentRoute } from "../../app/types";
import { Documentation } from "./Documentation";
import { Avatar } from "../../components/Avatar";
import { CardHead, GhostButton, Wordmark } from "../../components/ui";
import { portraitFor } from "../student/portrait";
import { stopOwnedAudio as stopPageAudio, type ScribeConnector, type ScribeEvent } from "../../voice/scribe";
import { connectElevenLabsScribe } from "../../voice/scribeLive";

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
  go,
}: {
  route: StudentRoute;
  client?: ApiClient;
  connectScribe?: ScribeConnector;
  stopOwnedAudio?: () => void;
  go?: Go;
}) {
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<LoadState>(route.encounterId ? { kind: "loading" } : { kind: "missing" });

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
  go,
}: {
  initial: PublicEncounter;
  client: ApiClient;
  connectScribe: ScribeConnector;
  stopOwnedAudio: () => void;
  go?: Go;
}) {
  const [view, setView] = useState(initial);
  const [voice, setVoice] = useState<VoiceState>("off");
  const [partial, setPartial] = useState("");
  const [banner, setBanner] = useState<string | null>(null);
  const [notices, setNotices] = useState<string[]>([]);
  const sessionRef = useRef<Awaited<ReturnType<ScribeConnector>> | null>(null);
  const queueRef = useRef(Promise.resolve());
  const closedRef = useRef(false);
  const mutedRef = useRef(false);
  const encounterId = view.encounter_id;

  useEffect(() => {
    return () => {
      // Leaving the screen stops the mic, the provider socket, and any audio we started.
      closedRef.current = true;
      sessionRef.current?.stop();
      sessionRef.current = null;
      stopOwnedAudio();
    };
  }, [stopOwnedAudio]);

  // Turns one Scribe event into a caption, a queued turn, or a visible failure.
  function onEvent(event: ScribeEvent) {
    if (closedRef.current) return;
    switch (event.type) {
      case "partial":
        if (!mutedRef.current) setPartial(event.text);
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
    try {
      const result = await client.POST("/api/encounters/{enc_id}/utterances", {
        params: { path: { enc_id: encounterId } },
        body: {
          text: event.text,
          start_ms: event.startMs,
          end_ms: event.endMs,
          words: event.words.map((word) => ({ text: word.text, start_ms: word.startMs, end_ms: word.endMs })),
        },
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
  }

  // Ending drops queued speech and anything still playing, then marks the visit ended.
  async function endVisit() {
    closedRef.current = true;
    sessionRef.current?.stop();
    sessionRef.current = null;
    setVoice("off");
    setPartial("");
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
    <div className="flex min-h-full flex-col">
      <div className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-4 border-b border-ink/7 bg-card/70 px-6 py-3.5 backdrop-blur-xl">
        <div className="flex items-center gap-4">
          <Wordmark size="sm" />
          <span className="h-[22px] w-px bg-line-3" />
          <span className="text-sm font-semibold">{view.visit_label}</span>
          <span className="text-sm text-ink-soft">{timingLabel(view.started_at, view.ended_at)}</span>
        </div>
        <div className="flex items-center gap-2">
          {active ? (
            <button
              type="button"
              onClick={() => {
                if (voice === "live" || voice === "muted") toggleMute();
                else void connect();
              }}
              disabled={voice === "connecting"}
              className="inline-flex h-[38px] items-center gap-2 rounded-[10px] border border-line-2 bg-card px-3.5 text-[13.5px] font-medium text-ink"
            >
              <span className={`size-2 rounded-full ${voice === "live" ? "bg-ok" : "bg-inactive"}`} />
              {micLabel(voice)}
            </button>
          ) : (
            <span className="text-[13.5px] text-muted">This visit has ended.</span>
          )}
          <button
            type="button"
            onClick={() => void endVisit()}
            disabled={!active}
            className="h-[38px] rounded-[10px] bg-segment px-4 text-[13.5px] font-semibold text-ink disabled:text-muted"
          >
            End visit
          </button>
        </div>
      </div>

      <div className="mx-auto grid w-full max-w-[1440px] flex-1 items-start gap-4 px-6 py-5 lg:grid-cols-[280px_minmax(0,1fr)_300px]">
        <aside aria-label="Visit notes" className="flex flex-col gap-3">
          <section className="rounded-2xl bg-panel px-[18px] py-4 text-white">
            <div className="text-[11.5px] font-semibold tracking-[0.6px] text-indigo-on-ink uppercase">Goal</div>
            <div className="mt-1 font-serif text-[19px] leading-snug">{view.briefing.goal}</div>
          </section>
          <section className="rounded-2xl border border-line bg-card px-[18px] py-3.5">
            <div className="text-[12.5px] text-muted">Referral</div>
            {notes.length === 0 ? <div className="mt-1 text-sm text-ink-soft">No referral has been released.</div> : null}
            {notes.map((note) => (
              <div key={note.ref} className="mt-2">
                <div className="text-sm font-semibold">{note.label}</div>
                {note.body ? <div className="mt-1 text-sm leading-snug">{note.body}</div> : null}
                <Provenance item={note} />
              </div>
            ))}
          </section>
          <section className="overflow-hidden rounded-2xl border border-line bg-card">
            <CardHead title="Exam log" className="px-[18px] py-3" />
            {exams.length === 0 ? <div className="px-[18px] py-3 text-sm text-muted">No exam has been released.</div> : null}
            {exams.map((exam) => (
              <div key={exam.ref} className="border-t border-hair px-[18px] py-[11px] text-sm first:border-t-0">
                <div>{exam.label}</div>
                {exam.value ? <div className="text-ink-soft">{exam.value}</div> : null}
                <Provenance item={exam} />
              </div>
            ))}
          </section>
        </aside>

        <div className="flex min-w-0 flex-col gap-4">
          <section aria-label="Patient" className="overflow-hidden rounded-2xl border border-line bg-card">
            <div className="flex items-center gap-3.5 px-5 py-4">
              <Avatar who={portraitFor(patient)} size={72} />
              <div>
                <div className="font-serif text-2xl leading-none font-medium tracking-[-0.4px]">
                  {patient.name}, {patient.age}
                </div>
                <div className="mt-1 text-[12.5px] text-muted">{statusLabel(voice, active)}</div>
                <div className="mt-1 text-[12.5px] text-muted">Headphones recommended, so the patient's voice doesn't echo</div>
              </div>
            </div>
          </section>
          <section aria-label="Transcript" className="flex flex-col gap-3 rounded-2xl border border-line bg-card px-5 py-4">
            {banner ? <p className="text-sm text-ink">{banner}</p> : null}
            {simplified || notices.includes("Simplified responses") ? (
              <p className="text-sm text-ink-soft">Simplified responses</p>
            ) : null}
            {notices
              .filter((notice) => notice !== "Simplified responses")
              .map((notice) => (
                <p key={notice} className="text-sm text-ink-soft">
                  {notice}
                </p>
              ))}
            {(view.transcript ?? []).length === 0 && !partial ? <p className="text-sm text-muted">No transcript yet.</p> : null}
            {(view.transcript ?? []).map((line) => (
              <div key={line.turn} className="flex flex-col gap-2">
                <TurnLine who="Student" text={line.student_text} align="end" />
                <TurnLine who={patient.speaker || patient.name} text={line.reply_text} align="start" />
                {line.is_last ? <div className="text-[11.5px] font-semibold text-muted">Latest turn</div> : null}
              </div>
            ))}
            {partial ? <p className="text-sm text-ink-soft">{partial}</p> : null}
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

        <aside aria-label="Chart" className="flex flex-col gap-3">
          {groupChart(released).map((group) => (
            <section key={group.section} className="overflow-hidden rounded-2xl border border-line bg-card">
              <CardHead title={group.section} className="px-[18px] py-3" />
              {group.items.map((item) => (
                <div key={`${item.kind}-${item.ref}`} className="border-t border-hair px-[18px] py-[11px] first:border-t-0">
                  <div className="text-sm font-semibold">{item.label}</div>
                  {item.value ? <div className="text-[12.5px] text-muted">{item.value}</div> : null}
                  <Provenance item={item} />
                </div>
              ))}
            </section>
          ))}
          {released.length === 0 ? (
            <section className="rounded-2xl border border-line bg-card px-[18px] py-3 text-sm text-muted">No chart entries have been released.</section>
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
      <div className={`max-w-[88%] rounded-[14px] px-3.5 py-2.5 text-[15px] leading-snug ${student ? "bg-panel text-white" : "bg-segment text-ink"}`}>
        {text}
      </div>
    </div>
  );
}
