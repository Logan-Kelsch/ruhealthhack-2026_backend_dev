import { useEffect, useState } from "react";
import { asApiError, api, type ApiClient, type PublicCase } from "../../api/client";
import type { Go } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { GhostButton, Page, Title } from "../../components/ui";
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
    <Page>
      <Title kicker={kicker(load)}>Your cases</Title>
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
    <div className="grid gap-5 [grid-template-columns:repeat(auto-fill,minmax(min(100%,520px),1fr))]">
      {load.cases.map((row) => (
        <section
          key={row.case_id}
          className="overflow-hidden rounded-[14px] border border-line bg-card shadow-[0_10px_30px_-24px_rgba(25,31,92,.35)]"
        >
          <div className="bg-banner h-[58px]" aria-hidden />
          <div className="-mt-8 flex items-end gap-5 px-7">
            <span className="rounded-full bg-card p-1.5">
              <Avatar who={portraitFor(row.patient)} size={104} />
            </span>
            <div className="min-w-0 pb-2">
              <div className="font-serif text-[clamp(28px,2.4vw,38px)] leading-none tracking-[-0.8px]">
                {row.patient.name}, {row.patient.age}
              </div>
              <div className="mt-2 font-serif text-[19px] text-ink-soft">{row.title}</div>
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
