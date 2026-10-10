import { useRef, useState } from "react";
import { asApiError, api, type ApiClient, type StudioCaseSummary } from "../../api/client";
import type { Go } from "../../app/types";
import { Badge, BackLink, GhostButton, Page, PrimaryButton, Title } from "../../components/ui";

type ImportState =
  | { kind: "ready" }
  | { kind: "importing" }
  | { kind: "done"; count: number; cases: StudioCaseSummary[] }
  | { kind: "error"; message: string };

// Faculty import the bundled sponsor sample set. One request creates every draft.
export function ImportPatients({ go, client = api }: { go: Go; client?: ApiClient }) {
  const [state, setState] = useState<ImportState>({ kind: "ready" });
  // Blocks a second click while the first request is still out. A retry of an uncertain import would duplicate drafts.
  const inFlight = useRef(false);

  return (
    <Page>
      <header>
        <BackLink label="Cases" onClick={() => go("f-cases")} />
        <div className="mt-2.5">
          <Title>Import sample set</Title>
        </div>
        <p className="mt-3 max-w-[680px] font-serif text-[19px] leading-snug text-ink-soft">
          This imports the full sponsor sample set as drafts. Each case needs faculty review before it can be published.
        </p>
      </header>

      <section className="overflow-hidden rounded-[14px] border border-line bg-card shadow-[0_10px_30px_-24px_rgba(25,31,92,.35)]" aria-live="polite">
        <div className="bg-banner h-[52px]" aria-hidden />
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-hair-2 px-7 py-6">
          <div>
            <div className="font-serif text-[28px] tracking-[-0.4px]">Sponsor sample set</div>
            <p className="mt-1 max-w-[560px] font-serif text-[18px] text-ink-soft">{statusLine(state)}</p>
          </div>
          <ImportAction state={state} onImport={() => void importSampleSet(client, inFlight, setState)} />
        </div>
        <ImportResult state={state} onViewCases={() => go("f-cases")} />
      </section>
    </Page>
  );
}

// Sends the bulk import once. A failure stays on screen and does not start another request.
async function importSampleSet(
  client: ApiClient,
  inFlight: { current: boolean },
  setState: (state: ImportState) => void,
) {
  if (inFlight.current) return;
  inFlight.current = true;
  setState({ kind: "importing" });
  try {
    const result = await client.POST("/api/studio/import/vhs");
    if (!result.response?.ok || result.data == null) {
      const status = result.response?.status ?? 0;
      setState({ kind: "error", message: asApiError(status, result.error).message });
      return;
    }
    setState({ kind: "done", count: result.data.count, cases: result.data.cases });
  } catch {
    // The request may have reached the server. Do not send it again from here.
    setState({ kind: "error", message: "The sample set could not be imported." });
  } finally {
    inFlight.current = false;
  }
}

// The button for the current step. Import stays disabled while the request is running.
function ImportAction({ state, onImport }: { state: ImportState; onImport: () => void }) {
  switch (state.kind) {
    case "done":
      return null;
    case "error":
      return <GhostButton onClick={onImport}>Try again</GhostButton>;
    case "ready":
    case "importing":
      return (
        <PrimaryButton size="lg" onClick={onImport} disabled={state.kind === "importing"}>
          Import sample set
        </PrimaryButton>
      );
    default: {
      const unreachable: never = state;
      return unreachable;
    }
  }
}

// The short line under the heading. It names the step without inventing a result count.
function statusLine(state: ImportState): string {
  switch (state.kind) {
    case "ready":
      return "Every profile in the sample set is saved together.";
    case "importing":
      return "Importing the sample set.";
    case "done":
      return "These drafts came back from the import. Open Cases to see the saved records.";
    case "error":
      return "The import did not finish.";
    default: {
      const unreachable: never = state;
      return unreachable;
    }
  }
}

// Returned drafts, or the error. Nothing here is filled in from sample fixtures.
function ImportResult({ state, onViewCases }: { state: ImportState; onViewCases: () => void }) {
  switch (state.kind) {
    case "done": {
      const noun = state.count === 1 ? "case" : "cases";
      return (
        <div className="flex flex-col gap-3 px-7 py-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="font-serif text-[24px]">
                Imported {state.count} {noun}
              </div>
              <div className="mt-0.5 text-[13px] text-muted">Needs faculty review</div>
            </div>
            <GhostButton onClick={onViewCases}>View cases</GhostButton>
          </div>
          <div className="overflow-hidden rounded-xl border border-line">
            {state.cases.map((row) => (
              <div
                key={row.case_id}
                className="flex items-center justify-between gap-3 border-t border-hair px-4 py-3 first:border-t-0"
              >
                <span className="font-serif text-[19px]">{row.patient}</span>
                <Badge tone="warn" dot>
                  Draft
                </Badge>
              </div>
            ))}
          </div>
        </div>
      );
    }
    case "error":
      return <p className="px-7 py-6 font-serif text-[18px] text-ink">{state.message}</p>;
    case "ready":
    case "importing":
      return null;
    default: {
      const unreachable: never = state;
      return unreachable;
    }
  }
}
