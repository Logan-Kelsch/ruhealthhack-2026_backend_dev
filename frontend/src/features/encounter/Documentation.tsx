import { useEffect, useRef, useState } from "react";
import { asApiError, type ApiClient } from "../../api/client";
import type { components } from "../../api/schema";
import type { Go } from "../../app/types";
import type { ScribeConnector, ScribeEvent, ScribeSession } from "../../voice/scribe";

type DocumentationTemplate = components["schemas"]["DocumentationTemplate"];
type NoteStatus = "ended" | "complete";

// The note is dictated after the visit, on its own microphone session.
// The encounter mic has already been stopped. This component never posts an utterance.
export function Documentation({
  template,
  saved,
  status,
  encounterId,
  client,
  connectScribe,
  go,
}: {
  template: DocumentationTemplate;
  saved: Record<string, string> | null;
  status: NoteStatus;
  encounterId: string;
  client: ApiClient;
  connectScribe: ScribeConnector;
  go?: Go;
}) {
  const finished = status === "complete";
  const [fields, setFields] = useState<Record<string, string>>(() => initialFields(template, saved));
  const [activeField, setActiveField] = useState<string | null>(null);
  const [partial, setPartial] = useState("");
  const [voice, setVoice] = useState<"off" | "connecting" | "live">("off");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [accepted, setAccepted] = useState(finished);
  const sessionRef = useRef<ScribeSession | null>(null);
  const closedRef = useRef(false);
  // The field that should receive the next committed phrase. Events can arrive after a render.
  const fieldRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      // Leaving the note stops this capture. It does not touch the visit, which already ended.
      closedRef.current = true;
      sessionRef.current?.stop();
      sessionRef.current = null;
    };
  }, []);

  // Drops the socket without changing the button label. dictate uses this while a new session is starting.
  function releaseSession() {
    sessionRef.current?.stop();
    sessionRef.current = null;
  }

  // The student asked to stop. The note text stays so they can still review it.
  function stopSession() {
    releaseSession();
    setVoice("off");
    setPartial("");
  }

  // Puts one dictated phrase into the field the student selected, so they can read it before submitting.
  function onEvent(event: ScribeEvent) {
    if (closedRef.current) return;
    switch (event.type) {
      case "partial":
        setPartial(event.text);
        return;
      case "committed":
        setPartial("");
        appendField(fieldRef.current, event.text);
        return;
      case "disconnected":
        stopSession();
        setError("The transcription service disconnected. Start dictation again.");
        return;
      case "token_expired":
        stopSession();
        setError("The transcription token expired. Start dictation again.");
        return;
      case "error":
        setError(event.message);
        return;
      default: {
        const unreachable: never = event;
        return unreachable;
      }
    }
  }

  // Adds the committed words to one field. A second phrase follows the first so the review shows both.
  function appendField(fieldId: string | null, spoken: string) {
    const text = spoken.trim();
    if (!fieldId || !text) return;
    setFields((current) => {
      const previous = current[fieldId]?.trim() ?? "";
      const next = previous ? `${previous} ${text}` : text;
      return { ...current, [fieldId]: next };
    });
  }

  // Opens a new Scribe session for one template field. This is not the encounter microphone.
  async function dictate(fieldId: string) {
    if (finished || accepted || voice === "connecting") return;
    setError(null);
    setVoice("connecting");
    fieldRef.current = fieldId;
    setActiveField(fieldId);
    // The previous note session ends here. The visit microphone is a different session and is already stopped.
    releaseSession();
    setPartial("");
    const configResult = await client.GET("/api/config");
    if (!configResult.data) {
      setVoice("off");
      setError(asApiError(configResult.response?.status ?? 0, configResult.error).message);
      return;
    }
    const tokenResult = await client.POST("/api/stt/token");
    if (!tokenResult.data) {
      setVoice("off");
      setError(asApiError(tokenResult.response?.status ?? 0, tokenResult.error).message);
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
      setVoice("live");
    } catch (caught) {
      setVoice("off");
      setError(permissionMessage(caught));
    }
  }

  // Sends the reviewed fields. A failure leaves the words on screen and does not mark the note done.
  async function submit() {
    if (submitting || finished || accepted) return;
    setSubmitting(true);
    setError(null);
    stopSession();
    try {
      const result = await client.POST("/api/encounters/{enc_id}/documentation", {
        params: { path: { enc_id: encounterId } },
        body: { fields },
      });
      if (!result.response || result.data === undefined) {
        const statusCode = result.response?.status ?? 0;
        setError(result.response ? asApiError(statusCode, result.error).message : "Documentation was not submitted.");
        return;
      }
      setAccepted(true);
      go?.("s-debrief", { encounterId });
    } catch {
      setError("Documentation was not submitted.");
    } finally {
      setSubmitting(false);
    }
  }

  const done = finished || accepted;
  const ready = template.fields.some((field) => (fields[field.id] ?? "").trim().length > 0);
  const activeLabel = template.fields.find((field) => field.id === activeField)?.label;

  return (
    <section aria-label="Documentation" className="rounded-2xl border border-line bg-card px-5 py-4">
      <h2 className="font-serif text-[22px] leading-snug">{template.label}</h2>
      <p className="mt-1 text-sm text-ink-soft">
        {done
          ? "This note was submitted."
          : "Dictate each field, read it back, then submit. This microphone is only for the note."}
      </p>
      {error ? <p className="mt-3 text-sm text-ink">{error}</p> : null}
      {voice === "live" && activeLabel ? <p className="mt-3 text-sm text-ink-soft">Dictating {activeLabel}</p> : null}
      {partial ? <p className="mt-1 text-sm text-ink-soft">{partial}</p> : null}
      <div className="mt-4 flex flex-col gap-4">
        {template.fields.map((field) => {
          const value = fields[field.id]?.trim() ?? "";
          return (
            <div key={field.id}>
              <div className="text-sm font-semibold">{field.label}</div>
              <div className="text-[12.5px] text-muted">{field.hint}</div>
              <p className="mt-1 text-[15px] leading-snug">{value || "Nothing dictated yet."}</p>
              {done ? null : (
                <button
                  type="button"
                  onClick={() => void dictate(field.id)}
                  disabled={voice === "connecting"}
                  className="mt-2 h-8 rounded-lg border border-line-2 bg-card px-3 text-[13px] font-medium text-ink disabled:text-muted"
                >
                  Dictate {field.label}
                </button>
              )}
            </div>
          );
        })}
      </div>
      {done ? (
        <button
          type="button"
          onClick={() => go?.("s-debrief", { encounterId })}
          className="mt-4 h-10 rounded-[10px] bg-panel px-4 text-sm font-medium text-white"
        >
          Open debrief
        </button>
      ) : (
        <div className="mt-4 flex flex-wrap gap-2">
          {voice === "live" ? (
            <button
              type="button"
              onClick={stopSession}
              className="h-10 rounded-[10px] border border-line-2 bg-card px-4 text-sm font-medium text-ink"
            >
              Stop dictation
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => void submit()}
            disabled={!ready || submitting}
            className="h-10 rounded-[10px] bg-panel px-4 text-sm font-medium text-white disabled:opacity-60"
          >
            {submitting ? "Submitting documentation" : "Submit documentation"}
          </button>
        </div>
      )}
    </section>
  );
}

// Starts from the saved note when one exists, so a refresh does not show a blank form.
function initialFields(template: DocumentationTemplate, saved: Record<string, string> | null): Record<string, string> {
  const fields: Record<string, string> = {};
  for (const field of template.fields) {
    fields[field.id] = saved?.[field.id] ?? "";
  }
  return fields;
}

// A denied prompt is named by the browser. Anything else means dictation did not connect.
function permissionMessage(error: unknown): string {
  if (typeof error === "object" && error !== null && "name" in error && error.name === "NotAllowedError") {
    return "Microphone permission was denied.";
  }
  return "The transcription service could not be reached.";
}
