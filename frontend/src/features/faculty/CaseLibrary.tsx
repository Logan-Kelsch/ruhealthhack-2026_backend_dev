import { useState } from "react";
import type { Go } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { Chevron, PlusIcon } from "../../components/Icons";
import { Card, Page, PrimaryButton, Title } from "../../components/ui";

type CaseRow = {
  name: string;
  learner: string;
  visits: number;
  status: "Published" | "Draft";
  tag: string;
  updated: string;
  who: "walter" | "alina" | "eli" | "generic";
};

const ALL: CaseRow[] = [
  { name: "Walter Greene, 72", learner: "Dietetics student", visits: 2, status: "Published", tag: "Typical", updated: "Oct 3", who: "walter" },
  { name: "Alina Reyes, 21", learner: "Third-year medical student", visits: 2, status: "Published", tag: "Typical", updated: "Sep 28", who: "alina" },
  { name: "Eli Brooks, 6", learner: "Physician assistant student", visits: 1, status: "Published", tag: "Typical", updated: "Sep 20", who: "eli" },
  { name: "Depression follow-up", learner: "Psychiatry clerkship", visits: 2, status: "Draft", tag: "Branching · decision tree", updated: "Today", who: "generic" },
];

const FILTERS = ["All", "Published", "Draft"] as const;
type Filter = (typeof FILTERS)[number];

// Faculty case list with a status filter. A draft opens the decision-tree tab in Studio.
export function CaseLibrary({ go }: { go: Go }) {
  const [filter, setFilter] = useState<Filter>("All");
  const rows = ALL.filter((row) => filter === "All" || row.status === filter);

  return (
    <Page>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <Title kicker="4 cases · 3 published">Cases</Title>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => go("f-import")}
            className="inline-flex h-10 items-center gap-2 rounded-[10px] border border-line-2 bg-white px-4 text-sm font-medium hover:bg-wash"
          >
            <DownloadIcon />
            Import sample patients
          </button>
          <PrimaryButton onClick={() => go("f-studio", { studioTab: "patient" })}>
            <PlusIcon />
            New case
          </PrimaryButton>
        </div>
      </header>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#eeeff5] px-3.5 py-3">
          <label className="flex h-9 max-w-[340px] min-w-[240px] flex-1 items-center gap-2 rounded-[9px] bg-wash px-3 text-muted">
            <SearchIcon />
            <input placeholder="Search cases" className="min-w-0 flex-1 bg-transparent text-sm text-ink outline-none" />
          </label>
          <div className="flex rounded-[9px] bg-[#f1f2f7] p-[3px]">
            {FILTERS.map((label) => {
              const on = filter === label;
              return (
                <button
                  key={label}
                  type="button"
                  onClick={() => setFilter(label)}
                  className={`flex h-[30px] items-center rounded-[7px] px-3.5 text-[13px] font-medium ${on ? "bg-white text-ink shadow-[0_1px_2px_rgba(20,27,77,.12)]" : "text-muted"}`}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>
        <div className="overflow-x-auto">
          <div className="min-w-[760px]">
            <div className="grid grid-cols-[minmax(220px,2fr)_minmax(160px,1.4fr)_80px_110px_110px_20px] gap-4 bg-[#fafafd] px-5 py-2.5 text-xs font-semibold tracking-[0.4px] text-muted uppercase">
              <span>Patient</span>
              <span>Learner</span>
              <span>Visits</span>
              <span>Status</span>
              <span>Updated</span>
              <span />
            </div>
            {rows.map((row) => {
              const draft = row.status === "Draft";
              return (
                <button
                  key={row.name}
                  type="button"
                  onClick={() => go("f-studio", { studioTab: draft ? "tree" : "patient" })}
                  className="grid w-full grid-cols-[minmax(220px,2fr)_minmax(160px,1.4fr)_80px_110px_110px_20px] items-center gap-4 border-t border-hair px-5 py-3.5 text-left text-sm hover:bg-[#fafafd]"
                >
                  <span className="flex min-w-0 items-center gap-3">
                    <Avatar who={row.who} size={40} />
                    <span className="min-w-0">
                      <span className="block text-[15px] font-semibold">{row.name}</span>
                      <span className="mt-0.5 block text-[12.5px] text-muted">{row.tag}</span>
                    </span>
                  </span>
                  <span className="text-ink-soft">{row.learner}</span>
                  <span className="tabular-nums">{row.visits}</span>
                  <span>
                    <span className={`inline-flex h-6 items-center gap-1.5 rounded-md px-2 text-xs font-semibold ${draft ? "bg-[#fdf1e3] text-warn" : "bg-[#e6f4ec] text-ok"}`}>
                      <span className="size-1.5 rounded-full bg-current" />
                      {row.status}
                    </span>
                  </span>
                  <span className="text-[13px] text-muted">{row.updated}</span>
                  <Chevron />
                </button>
              );
            })}
          </div>
        </div>
      </Card>
    </Page>
  );
}

function SearchIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-4-4" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 15V3M7 8l5-5 5 5M5 13v7h14v-7" />
    </svg>
  );
}
