import { useEffect, useState } from "react";
import { asApiError, api, type ApiClient, type PublicCase } from "../../api/client";
import type { components } from "../../api/schema";
import type { Go } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { GhostButton, Page, Title } from "../../components/ui";

type EncounterSummary = components["schemas"]["EncounterSummary"];
type EncounterList = components["schemas"]["EncounterList"];

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; cases: PublicCase[] };

type HistoryState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; list: EncounterList };

// Published cases and the student's saved encounters. There is no cohort list and no due date.
export function StudentHome({ go, client = api }: { go: Go; client?: ApiClient }) {
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<LoadState>({ kind: "loading" });
  const [history, setHistory] = useState<HistoryState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setLoad({ kind: "loading" });
    setHistory({ kind: "loading" });
    // Cases and encounters fail separately, so one outage does not hide the other list.
    client
      .GET("/api/cases")
      .then((result) => {
        if (cancelled) return;
        if (!result.response?.ok || !result.data) {
          const status = result.response?.status ?? 0;
          setLoad({ kind: "error", message: asApiError(status, result.error).message });
          return;
        }
        setLoad({ kind: "ready", cases: result.data });
      })
      .catch(() => {
        if (!cancelled) setLoad({ kind: "error", message: "Cases could not be loaded." });
      });
    client
      .GET("/api/encounters")
      .then((result) => {
        if (cancelled) return;
        if (!result.response?.ok || !result.data) {
          const status = result.response?.status ?? 0;
          setHistory({ kind: "error", message: asApiError(status, result.error).message });
          return;
        }
        setHistory({ kind: "ready", list: result.data });
      })
      .catch(() => {
        if (!cancelled) setHistory({ kind: "error", message: "Encounters could not be loaded." });
      });
    return () => {
      cancelled = true;
    };
  }, [client, attempt]);

  return (
    <Page>
      <Title>Your cases</Title>
      <CaseList
        load={load}
        onRetry={() => setAttempt((value) => value + 1)}
        onOpen={(row, visitId) => go("s-brief", { caseId: row.case_id, version: row.version, visitId })}
      />
      <section className="flex flex-col gap-3">
        <Title kicker={historyNote(history)}>Your encounters</Title>
        <HistoryList
          history={history}
          onRetry={() => setAttempt((value) => value + 1)}
          onOpen={(row) => go("s-debrief", { caseId: row.case_id, visitId: row.visit_id, encounterId: row.encounter_id })}
        />
      </section>
    </Page>
  );
}

// The history count. A capped list says how many saved encounters are not on the page.
function historyNote(history: HistoryState): string | undefined {
  if (history.kind !== "ready" || history.list.total === 0) return undefined;
  if (history.list.total > history.list.encounters.length) {
    return `Showing ${history.list.encounters.length} of ${history.list.total}`;
  }
  if (history.list.total === 1) return "1 saved encounter";
  return `${history.list.total} saved encounters`;
}

// Lists each published visit. Opening one goes to its briefing and does not start an encounter.
function CaseList({
  load,
  onRetry,
  onOpen,
}: {
  load: LoadState;
  onRetry: () => void;
  onOpen: (row: PublicCase, visitId: string) => void;
}) {
  if (load.kind === "loading") {
    return <p className="text-sm text-muted">Loading published cases</p>;
  }
  if (load.kind === "error") {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-sm text-ink">{load.message}</p>
        <GhostButton onClick={onRetry}>Retry</GhostButton>
      </div>
    );
  }
  if (load.cases.length === 0) {
    return <p className="text-sm text-muted">No published cases</p>;
  }
  return (
    <div className="grid gap-5 [grid-template-columns:repeat(auto-fill,minmax(min(100%,520px),1fr))]">
      {load.cases.map((row) => (
        <section
          key={row.case_id}
          className="overflow-hidden rounded-[14px] border border-line bg-card shadow-[0_10px_30px_-24px_rgba(25,31,92,.35)]"
        >
          <div className="bg-banner h-[58px]" aria-hidden />
          <div className="-mt-8 flex items-end gap-5 px-7">
            <span className="rounded-full bg-card p-1.5">
              <Avatar who="generic" size={104} />
            </span>
            <div className="min-w-0 pb-2">
              <div className="font-serif text-[clamp(28px,2.4vw,38px)] leading-none tracking-[-0.8px]">
                {row.patient.name}
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-3 px-7 pt-5 pb-6">
            {row.visits.map((visit) => (
              <button
                key={visit.id}
                type="button"
                onClick={() => onOpen(row, visit.id)}
                className="inline-flex h-12 items-center gap-2 rounded-xl border border-indigo-line bg-indigo-soft px-5 font-serif text-[19px] text-ink hover:bg-indigo-soft-2"
              >
                {visit.label}
                <span aria-hidden>→</span>
              </button>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

// Saved encounters for this student. Opening one shows that encounter's debrief, and does not start another.
function HistoryList({
  history,
  onRetry,
  onOpen,
}: {
  history: HistoryState;
  onRetry: () => void;
  onOpen: (row: EncounterSummary) => void;
}) {
  if (history.kind === "loading") {
    return <p className="text-sm text-muted">Loading your encounters</p>;
  }
  if (history.kind === "error") {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-sm text-ink">{history.message}</p>
        <GhostButton onClick={onRetry}>Retry</GhostButton>
      </div>
    );
  }
  if (history.list.encounters.length === 0) {
    return <p className="text-sm text-muted">No saved encounters</p>;
  }
  return (
    <div className="flex flex-col gap-2">
      {history.list.encounters.map((row) => (
        <button
          key={row.encounter_id}
          type="button"
          onClick={() => onOpen(row)}
          className="rounded-[14px] border border-line bg-card px-6 py-4 text-left shadow-[0_10px_30px_-24px_rgba(25,31,92,.35)] hover:bg-raised"
        >
          <div className="font-serif text-[21px]">
            {row.student_name.trim() || "Unnamed student"}{" "}
            <span className="font-normal text-muted">· {row.patient_name.trim() || row.case_id}</span>
          </div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 font-sans text-[14px] text-ink-soft">
            <span>{row.visit_label.trim() || row.visit_id}</span>
            <span>{statusLabel(row.status)}</span>
            {row.review_flag ? <span className="font-semibold text-ink">Needs review</span> : null}
          </div>
        </button>
      ))}
    </div>
  );
}

// The stored status, in words. Color is not the only signal.
function statusLabel(status: EncounterSummary["status"]): string {
  if (status === "active") return "In progress";
  if (status === "ended") return "Ended";
  if (status === "complete") return "Complete";
  const unreachable: never = status;
  return unreachable;
}

