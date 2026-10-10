import { useEffect, useState } from "react";
import { asApiError, api, type ApiClient, type StudioCaseSummary } from "../../api/client";
import type { Go } from "../../app/types";
import { Avatar, type Portrait } from "../../components/Avatar";
import { PlusIcon } from "../../components/Icons";
import { GhostButton, Page, PageHeader, SoftButton } from "../../components/ui";

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
        <div className="flex flex-wrap items-center gap-4">
          <SoftButton size="lg" onClick={() => go("f-studio", { studioTab: "patient" })} className="shadow-[0_10px_24px_-16px_rgba(74,95,217,.7)]">
            <PlusIcon size={20} />
            New case
          </SoftButton>
          <GhostButton onClick={() => go("f-import")} className="h-14 rounded-xl px-7 text-[20px]">
            <DownloadIcon />
            Import sample set
          </GhostButton>
        </div>
      </PageHeader>

      <div className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex h-11 max-w-[380px] min-w-[240px] flex-1 items-center gap-2 rounded-xl border border-line bg-card px-4 text-muted">
            <SearchIcon />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search cases"
              className="min-w-0 flex-1 bg-transparent font-serif text-[17px] text-ink outline-none"
            />
          </label>
          <div className="flex rounded-xl border border-line bg-card p-1">
            {FILTERS.map((label) => {
              const on = filter === label;
              return (
                <button
                  key={label}
                  type="button"
                  onClick={() => setFilter(label)}
                  className={`flex h-9 items-center rounded-[9px] px-4 font-serif text-[17px] ${on ? "bg-indigo-soft text-ink" : "text-ink-soft hover:text-ink"}`}
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
      </div>
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
    <div className="grid gap-5 [grid-template-columns:repeat(auto-fill,minmax(min(100%,400px),1fr))]">
      {visible.map((row) => {
        const draft = row.status === "draft";
        return (
          <button
            key={row.case_id}
            type="button"
            onClick={() => onSelect(row)}
            className="group flex flex-col rounded-[14px] border border-line bg-card px-6 pt-6 pb-5 text-left shadow-[0_10px_30px_-24px_rgba(25,31,92,.35)] transition-shadow hover:shadow-[0_18px_40px_-24px_rgba(25,31,92,.45)]"
          >
            <span className="flex items-center gap-6 pb-6">
              <Avatar who={portraitFor(row.case_id)} size={120} />
              <span className="min-w-0">
                <span className="block font-serif text-[clamp(24px,2vw,32px)] leading-tight tracking-[-0.5px]">{row.patient}</span>
                <span className="mt-1.5 block font-serif text-[19px] text-ink-soft">{row.title}</span>
                <span className="mt-2 block font-serif text-[17px] text-ink-soft">
                  <span className="tabular-nums">Version {row.version}</span>
                  <span className="px-1.5 text-faint">·</span>
                  {formatUpdated(row.updated_at)}
                </span>
              </span>
            </span>
            <span className="flex items-center justify-between gap-3 border-t border-hair-2 pt-4">
              <span
                className={`inline-flex h-10 items-center rounded-full px-5 font-serif text-[18px] ${draft ? "bg-warn-soft text-warn-deep" : row.status === "published" ? "bg-indigo-soft text-ink" : "bg-raised text-ink-soft"}`}
              >
                {statusLabel(row.status)}
              </span>
              <span className="truncate font-sans text-[13px] text-ink-soft">{subtitle(row)}</span>
              <span className="font-serif text-[19px] text-indigo underline underline-offset-4 group-hover:text-ink">Edit</span>
            </span>
          </button>
        );
      })}
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
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 15V3M7 8l5-5 5 5M5 13v7h14v-7" />
    </svg>
  );
}
