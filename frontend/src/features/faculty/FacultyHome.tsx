import { useEffect, useState } from "react";
import { asApiError, api, type ApiClient } from "../../api/client";
import type { components } from "../../api/schema";
import type { Go } from "../../app/types";
import { PlusIcon } from "../../components/Icons";
import { GhostButton, Page, PageHeader, PrimaryButton } from "../../components/ui";

type EncounterSummary = components["schemas"]["EncounterSummary"];
type EncounterList = components["schemas"]["EncounterList"];

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; list: EncounterList };

// Faculty landing. Counts and flags come from saved encounters, not from a cohort.
export function FacultyHome({ go, client = api }: { go: Go; client?: ApiClient }) {
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setLoad({ kind: "loading" });
    client
      .GET("/api/encounters")
      .then((result) => {
        if (cancelled) return;
        if (!result.response?.ok || !result.data) {
          const status = result.response?.status ?? 0;
          setLoad({ kind: "error", message: asApiError(status, result.error).message });
          return;
        }
        // A 200 that is not an encounter list is a failure, not an empty class.
        if (!Array.isArray(result.data.encounters)) {
          setLoad({ kind: "error", message: "Encounters could not be loaded." });
          return;
        }
        setLoad({ kind: "ready", list: result.data });
      })
      .catch(() => {
        if (!cancelled) setLoad({ kind: "error", message: "Encounters could not be loaded." });
      });
    return () => {
      cancelled = true;
    };
  }, [client, attempt]);

  return (
    <Page width="max-w-[1180px]">
      <StartPanel
        onNew={() => go("f-studio", { studioTab: "patient" })}
        onImport={() => go("f-import")}
        onLibrary={() => go("f-cases")}
      />
      <section className="flex flex-col gap-4">
        <PageHeader kicker={kicker(load)} title="Saved encounters" />
        <EncounterListView load={load} onRetry={() => setAttempt((value) => value + 1)} onReview={(encounterId) => go("f-review", { encounterId })} />
      </section>
    </Page>
  );
}

// Building a case is the first thing faculty do, so it leads the page and says what happens next.
function StartPanel({ onNew, onImport, onLibrary }: { onNew: () => void; onImport: () => void; onLibrary: () => void }) {
  return (
    <section className="overflow-hidden rounded-[22px] border border-white/80 bg-card/95 shadow-[0_24px_60px_-36px_rgba(25,31,92,.55)]">
      <div className="bg-banner h-2" aria-hidden />
      <div className="flex flex-col gap-7 px-[clamp(22px,3vw,44px)] pt-8 pb-9">
        <div>
          <h1 className="m-0 font-serif text-[clamp(34px,3.2vw,48px)] leading-[1.05] font-normal tracking-[-1px]">Build a case</h1>
          <p className="mt-2 max-w-[640px] font-sans text-[16.5px] leading-snug text-ink-soft">
            Describe a patient in your own words. Rounds suggests the details, you check every one, and learners only hear what you approved.
          </p>
        </div>
        <ol className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr))]">
          {START_STEPS.map((step, index) => (
            <li key={step.title} className="flex gap-3.5 rounded-[16px] bg-wash px-4 py-4">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-card font-sans text-[14px] font-semibold text-ink shadow-[0_4px_10px_-6px_rgba(25,31,92,.5)]">
                {index + 1}
              </span>
              <span>
                <span className="block font-serif text-[19px] leading-tight">{step.title}</span>
                <span className="mt-1 block font-sans text-[13.5px] leading-snug text-ink-soft">{step.detail}</span>
              </span>
            </li>
          ))}
        </ol>
        <div className="flex flex-wrap items-center gap-3">
          <PrimaryButton size="lg" onClick={onNew}>
            <PlusIcon />
            New case
          </PrimaryButton>
          <GhostButton onClick={onLibrary}>Open case library</GhostButton>
          <GhostButton onClick={onImport}>Import sample set</GhostButton>
        </div>
      </div>
    </section>
  );
}

const START_STEPS = [
  { title: "Describe the patient", detail: "A few sentences, plus any notes on what learners should catch." },
  { title: "Check the details", detail: "Suggested history, vitals with their sources, and learning goals. Change anything." },
  { title: "Publish", detail: "Approve each item, then learners can start the visit by voice." },
];

// The kicker is the real count. A capped list says so instead of pretending the page is complete.
function kicker(load: LoadState): string | undefined {
  if (load.kind !== "ready" || load.list.total === 0) return undefined;
  return listNote(load.list);
}

// total is every match. The sentence changes when the page does not include all of them.
function listNote(list: EncounterList): string {
  if (list.total > list.encounters.length) {
    return `Showing ${list.encounters.length} of ${list.total}`;
  }
  if (list.total === 1) return "1 saved encounter";
  return `${list.total} saved encounters`;
}

// Loading, empty, and error each have their own sentence so a failure is not an empty class.
function EncounterListView({
  load,
  onRetry,
  onReview,
}: {
  load: LoadState;
  onRetry: () => void;
  onReview: (encounterId: string) => void;
}) {
  if (load.kind === "loading") {
    return <p className="text-sm text-muted">Loading saved encounters</p>;
  }
  if (load.kind === "error") {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-sm text-ink">{load.message}</p>
        <GhostButton onClick={onRetry}>Retry</GhostButton>
      </div>
    );
  }
  if (load.list.encounters.length === 0) {
    return <p className="text-sm text-muted">No saved encounters</p>;
  }
  return (
    <div className="flex flex-col gap-2">
      {load.list.encounters.map((row) => (
        <EncounterRow key={row.encounter_id} row={row} onReview={onReview} />
      ))}
    </div>
  );
}

// One saved visit. The status and the review flag are words, not only a color.
function EncounterRow({ row, onReview }: { row: EncounterSummary; onReview: (encounterId: string) => void }) {
  const who = row.student_name.trim() || "Unnamed student";
  const patient = row.patient_name.trim() || row.case_id;
  const visit = row.visit_label.trim() || row.visit_id;
  return (
    <div
      className={`flex flex-wrap items-center justify-between gap-3 rounded-[14px] border px-6 py-4 shadow-[0_10px_30px_-24px_rgba(25,31,92,.35)] ${
        row.review_flag ? "border-warn-line bg-warn-wash" : "border-line bg-card"
      }`}
    >
      <div className="min-w-0">
        <div className="font-serif text-[21px]">
          {who} <span className="text-muted">· {patient}</span>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 font-sans text-[14px] text-ink-soft">
          <span>{visit}</span>
          <span>{statusLabel(row.status)}</span>
          {row.review_flag ? <span className="font-semibold text-warn-deep">Needs review</span> : null}
          {typeof row.rubric_total === "number" ? <span>{row.rubric_total} / 28</span> : null}
        </div>
      </div>
      <GhostButton onClick={() => onReview(row.encounter_id)}>Review</GhostButton>
    </div>
  );
}

// The stored status, in words a faculty member can read without the color.
function statusLabel(status: EncounterSummary["status"]): string {
  if (status === "active") return "In progress";
  if (status === "ended") return "Ended";
  if (status === "complete") return "Complete";
  const unreachable: never = status;
  return unreachable;
}
