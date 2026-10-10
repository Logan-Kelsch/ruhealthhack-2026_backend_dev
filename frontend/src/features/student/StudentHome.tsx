import { useEffect, useState } from "react";
import { asApiError, api, type ApiClient, type PublicCase } from "../../api/client";
import type { components } from "../../api/schema";
import type { Go } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { Card, GhostButton, Page, Title } from "../../components/ui";
import { portraitFor } from "./portrait";

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
    <Page width="max-w-[1100px]">
      <Title kicker={kicker(load)}>Cases</Title>
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

// The count is the number of published cases. It is not a date or an assignment.
function kicker(load: LoadState): string | undefined {
  if (load.kind === "ready") return `${load.cases.length} published`;
  return undefined;
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
    <div className="flex flex-col gap-4">
      {load.cases.map((row) => (
        <Card key={row.case_id}>
          <div className="flex items-center gap-4 p-5">
            <Avatar who={portraitFor(row.patient)} size={64} />
            <div className="min-w-0">
              <div className="font-serif text-[28px] leading-tight font-medium tracking-[-0.4px]">
                {row.patient.name}, {row.patient.age}
              </div>
              <div className="mt-1 text-[15px] text-ink-soft">{row.title}</div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 border-t border-hair px-5 py-3">
            {row.visits.map((visit) => (
              <GhostButton key={visit.id} onClick={() => onOpen(row, visit.id)}>
                {visit.label}
              </GhostButton>
            ))}
          </div>
        </Card>
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
          className="rounded-2xl border border-line bg-card px-5 py-4 text-left"
        >
          <div className="text-[15px] font-semibold">
            {row.student_name.trim() || "Unnamed student"}{" "}
            <span className="font-normal text-muted">· {row.patient_name.trim() || row.case_id}</span>
          </div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-sm text-ink-soft">
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
