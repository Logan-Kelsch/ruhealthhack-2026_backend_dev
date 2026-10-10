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
    <Page>
      <PageHeader kicker={kicker(load)} title="Saved encounters">
        <div className="flex gap-2">
          <GhostButton onClick={() => go("f-import")}>Import sample set</GhostButton>
          <PrimaryButton onClick={() => go("f-studio", { studioTab: "patient" })}>
            <PlusIcon />
            New case
          </PrimaryButton>
        </div>
      </PageHeader>
      <EncounterListView load={load} onRetry={() => setAttempt((value) => value + 1)} onReview={(encounterId) => go("f-review", { encounterId })} />
    </Page>
  );
}

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
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-card px-5 py-4">
      <div className="min-w-0">
        <div className="text-[15px] font-semibold">
          {who} <span className="font-normal text-muted">· {patient}</span>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-soft">
          <span>{visit}</span>
          <span>{statusLabel(row.status)}</span>
          {row.review_flag ? <span className="font-semibold text-ink">Needs review</span> : null}
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
