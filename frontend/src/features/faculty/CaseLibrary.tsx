import { useEffect, useState } from "react";
import { asApiError, api, type ApiClient, type StudioCaseSummary } from "../../api/client";
import type { Go } from "../../app/types";
import { Avatar, type Portrait } from "../../components/Avatar";
import { Chevron, PlusIcon } from "../../components/Icons";
import { Badge, Card, GhostButton, Page, PageHeader, PrimaryButton } from "../../components/ui";

const FILTERS = ["All", "Published", "Draft"] as const;
type Filter = (typeof FILTERS)[number];

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; cases: StudioCaseSummary[] };

// Faculty case list. Rows come from saved cases; a failed load does not invent sample patients.
export function CaseLibrary({ go, client = api }: { go: Go; client?: ApiClient }) {
  const [filter, setFilter] = useState<Filter>("All");
  const [query, setQuery] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setLoad({ kind: "loading" });
    client
      .GET("/api/studio/cases")
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

  const cases = load.kind === "ready" ? load.cases : [];
  const visible = cases.filter((row) => matchesFilter(row.status, filter) && matchesQuery(row, query));
  const published = cases.filter((row) => row.status === "published").length;

  return (
    <Page>
      <PageHeader kicker={kicker(load, published)} title="Cases">
        <div className="flex gap-2">
          <GhostButton onClick={() => go("f-import")}>
            <DownloadIcon />
            Import sample set
          </GhostButton>
          <PrimaryButton onClick={() => go("f-studio", { studioTab: "patient" })}>
            <PlusIcon />
            New case
          </PrimaryButton>
        </div>
      </PageHeader>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hair-2 px-3.5 py-3">
          <label className="flex h-9 max-w-[340px] min-w-[240px] flex-1 items-center gap-2 rounded-[9px] bg-wash px-3 text-muted">
            <SearchIcon />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search cases"
              className="min-w-0 flex-1 bg-transparent text-sm text-ink outline-none"
            />
          </label>
          <div className="flex rounded-[9px] bg-segment p-[3px]">
            {FILTERS.map((label) => {
              const on = filter === label;
              return (
                <button
                  key={label}
                  type="button"
                  onClick={() => setFilter(label)}
                  className={`flex h-[30px] items-center rounded-[7px] px-3.5 text-[13px] font-medium ${on ? "bg-card text-ink shadow-[0_1px_2px_rgba(20,27,77,.12)]" : "text-muted"}`}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>
        <LibraryBody
          load={load}
          visible={visible}
          onRetry={() => setAttempt((value) => value + 1)}
          onSelect={(row) =>
            go("f-studio", {
              studioTab: row.status === "draft" ? "tree" : "patient",
              caseId: row.case_id,
              version: row.version,
            })
          }
        />
      </Card>
    </Page>
  );
}

// The table, or the loading, empty, and error copy. Sample patients are never drawn here.
function LibraryBody({
  load,
  visible,
  onRetry,
  onSelect,
}: {
  load: LoadState;
  visible: StudioCaseSummary[];
  onRetry: () => void;
  onSelect: (row: StudioCaseSummary) => void;
}) {
  if (load.kind === "loading") {
    return <p className="px-5 py-8 text-sm text-muted">Loading saved cases</p>;
  }
  if (load.kind === "error") {
    return (
      <div className="flex flex-col items-start gap-3 px-5 py-8">
        <p className="text-sm text-ink">{load.message}</p>
        <GhostButton onClick={onRetry}>Retry</GhostButton>
      </div>
    );
  }
  if (load.cases.length === 0) {
    return <p className="px-5 py-8 text-sm text-muted">No saved cases</p>;
  }
  if (visible.length === 0) {
    return <p className="px-5 py-8 text-sm text-muted">No cases match this filter.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <div className="min-w-[760px]">
        <div className="grid grid-cols-[minmax(200px,1.6fr)_minmax(180px,1.6fr)_110px_110px_130px_20px] gap-4 bg-raised px-5 py-2.5 text-xs font-semibold tracking-[0.4px] text-muted uppercase">
          <span>Patient</span>
          <span>Title</span>
          <span>Version</span>
          <span>Status</span>
          <span>Updated</span>
          <span />
        </div>
        {visible.map((row) => (
          <button
            key={row.case_id}
            type="button"
            onClick={() => onSelect(row)}
            className="grid w-full grid-cols-[minmax(200px,1.6fr)_minmax(180px,1.6fr)_110px_110px_130px_20px] items-center gap-4 border-t border-hair px-5 py-3.5 text-left text-sm hover:bg-raised"
          >
            <span className="flex min-w-0 items-center gap-3">
              <Avatar who={portraitFor(row.case_id)} size={40} />
              <span className="min-w-0">
                <span className="block text-[15px] font-semibold">{row.patient}</span>
                <span className="mt-0.5 block text-[12.5px] text-muted">{subtitle(row)}</span>
              </span>
            </span>
            <span className="truncate text-ink-soft">{row.title}</span>
            <span className="tabular-nums">Version {row.version}</span>
            <span>
              <Badge tone={statusTone(row.status)} dot>
                {statusLabel(row.status)}
              </Badge>
            </span>
            <span className="text-[13px] text-muted">{formatUpdated(row.updated_at)}</span>
            <Chevron />
          </button>
        ))}
      </div>
    </div>
  );
}

// The line above the title. Counts come from the response, not a hard-coded total.
function kicker(load: LoadState, published: number): string {
  switch (load.kind) {
    case "loading":
      return "Loading cases";
    case "error":
      return "Cases unavailable";
    case "ready": {
      const count = load.cases.length;
      const noun = count === 1 ? "case" : "cases";
      return `${count} ${noun} · ${published} published`;
    }
    default: {
      const unreachable: never = load;
      return unreachable;
    }
  }
}

// Archived cases stay in All. Published and Draft use the saved status values.
function matchesFilter(status: StudioCaseSummary["status"], filter: Filter): boolean {
  switch (filter) {
    case "All":
      return true;
    case "Published":
      return status === "published";
    case "Draft":
      return status === "draft";
    default: {
      const unreachable: never = filter;
      return unreachable;
    }
  }
}

// Search only the fields the summary actually returns.
function matchesQuery(row: StudioCaseSummary, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return [row.patient, row.title, row.case_id].some((value) => value.toLowerCase().includes(needle));
}

// A draft shows how many publish blockers it has. A golden case says so in words, not only by color.
function subtitle(row: StudioCaseSummary): string {
  const blockers = row.blockers ?? [];
  if (blockers.length === 1) return "1 publish blocker";
  if (blockers.length > 1) return `${blockers.length} publish blockers`;
  if (row.golden) return "Golden case";
  return row.case_id;
}

// Status text is the signal. The badge color repeats it and is not the only cue.
function statusLabel(status: StudioCaseSummary["status"]): string {
  switch (status) {
    case "draft":
      return "Draft";
    case "published":
      return "Published";
    case "archived":
      return "Archived";
    default: {
      const unreachable: never = status;
      return unreachable;
    }
  }
}

// Badge color follows the same three statuses as the label.
function statusTone(status: StudioCaseSummary["status"]): "ok" | "warn" | "neutral" {
  switch (status) {
    case "published":
      return "ok";
    case "draft":
      return "warn";
    case "archived":
      return "neutral";
    default: {
      const unreachable: never = status;
      return unreachable;
    }
  }
}

// The three golden cases keep their drawn portraits. Every other saved case uses the generic face.
function portraitFor(caseId: string): Portrait {
  if (caseId === "walter_greene") return "walter";
  if (caseId === "alina_reyes") return "alina";
  if (caseId === "eli_brooks") return "eli";
  return "generic";
}

// Show the saved timestamp as a date. Values without a zone are UTC, matching the API.
function formatUpdated(value: string | null): string {
  if (!value) return "Not yet saved";
  const hasZone = value.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(value);
  const date = new Date(hasZone ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

// Magnifying glass for the search field. Decorative, so it is hidden from assistive tech.
function SearchIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-4-4" />
    </svg>
  );
}

// Download mark on the import button. Decorative, so it is hidden from assistive tech.
function DownloadIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 15V3M7 8l5-5 5 5M5 13v7h14v-7" />
    </svg>
  );
}
