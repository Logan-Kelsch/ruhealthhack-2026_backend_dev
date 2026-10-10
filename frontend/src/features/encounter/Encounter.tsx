import { useEffect, useState } from "react";
import { asApiError, api, type ApiClient, type PublicChartEntry, type PublicEncounter } from "../../api/client";
import type { StudentRoute } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { CardHead, GhostButton, Wordmark } from "../../components/ui";
import { portraitFor } from "../student/portrait";

type LoadState =
  | { kind: "missing" }
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; encounter: PublicEncounter };

// The live visit. Speech is not connected, so the microphone stays unavailable and nothing is typed.
export function Encounter({ route, client = api }: { route: StudentRoute; client?: ApiClient }) {
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
    // Refresh reads the saved encounter. It does not call the start route.
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
  return <EncounterLayout encounter={load.encounter} />;
}

// Patient in the center, transcript under the patient, notes on the left, chart on the right.
function EncounterLayout({ encounter }: { encounter: PublicEncounter }) {
  const chart = encounter.chart ?? [];
  const notes = chart.filter((item) => item.kind === "artifact");
  const exams = chart.filter((item) => item.kind === "exam");
  const released = chart.filter((item) => item.kind !== "artifact" && item.kind !== "exam");
  const patient = encounter.patient;

  return (
    <div className="flex min-h-full flex-col">
      <div className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-4 border-b border-ink/7 bg-card/70 px-6 py-3.5 backdrop-blur-xl">
        <div className="flex items-center gap-4">
          <Wordmark size="sm" />
          <span className="h-[22px] w-px bg-line-3" />
          <span className="text-sm font-semibold">{encounter.visit_label}</span>
          <span className="text-sm text-ink-soft">{timingLabel(encounter.started_at, encounter.ended_at)}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled
            className="inline-flex h-[38px] items-center gap-2 rounded-[10px] border border-line-2 bg-card px-3.5 text-[13.5px] font-medium text-muted"
          >
            <span className="size-2 rounded-full bg-inactive" />
            Microphone unavailable
          </button>
          <button
            type="button"
            disabled
            className="h-[38px] rounded-[10px] bg-segment px-4 text-[13.5px] font-semibold text-muted"
          >
            End visit unavailable
          </button>
        </div>
      </div>

      <div className="mx-auto grid w-full max-w-[1440px] flex-1 items-start gap-4 px-6 py-5 lg:grid-cols-[280px_minmax(0,1fr)_300px]">
        <aside aria-label="Visit notes" className="flex flex-col gap-3">
          <section className="rounded-2xl bg-panel px-[18px] py-4 text-white">
            <div className="text-[11.5px] font-semibold tracking-[0.6px] text-indigo-on-ink uppercase">Goal</div>
            <div className="mt-1 font-serif text-[19px] leading-snug">{encounter.briefing.goal}</div>
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
                <div className="mt-1 text-[12.5px] text-muted">Microphone unavailable</div>
              </div>
            </div>
          </section>
          <section aria-label="Transcript" className="flex flex-col gap-3 rounded-2xl border border-line bg-card px-5 py-4">
            {(encounter.transcript ?? []).length === 0 ? <p className="text-sm text-muted">No transcript yet.</p> : null}
            {(encounter.transcript ?? []).map((line) => (
              <div key={line.turn} className="flex flex-col gap-2">
                <TurnLine who="Student" text={line.student_text} align="end" />
                <TurnLine who={patient.speaker || patient.name} text={line.reply_text} align="start" />
                {line.is_last ? <div className="text-[11.5px] font-semibold text-muted">Latest turn</div> : null}
              </div>
            ))}
          </section>
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

// Shows the saved start or end time. There is no running clock while the microphone is off.
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
