import { useEffect, useState } from "react";
import { asApiError, api, type ApiClient, type PublicCase } from "../../api/client";
import type { Go } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { Card, GhostButton, Page, Title } from "../../components/ui";
import { portraitFor } from "./portrait";

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; cases: PublicCase[] };

// Published cases a student can open. There is no cohort list and no due date on this screen.
export function StudentHome({ go, client = api }: { go: Go; client?: ApiClient }) {
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setLoad({ kind: "loading" });
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
    </Page>
  );
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
