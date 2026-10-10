import { useEffect, useState } from "react";
import type { Go, StudioTab } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { PlusIcon } from "../../components/Icons";
import { Badge, BackLink, CardHead, GhostButton, Mark, PrimaryButton, TabNav } from "../../components/ui";
import { RUBRIC_DOMAINS } from "../../lib/rubric";
import { STUDIO_CASES, STUDIO_OBJECTIVES, STUDIO_SUGGESTED_FACTS, studioPatientColumns } from "../../mock/studio";
import { DecisionTree } from "./DecisionTree";

type FactState = "pending" | "approved" | "dismissed";

const TABS: { id: StudioTab; label: string }[] = [
  { id: "patient", label: "Patient" },
  { id: "objectives", label: "Learning objectives" },
  { id: "files", label: "Files and sources" },
  { id: "tree", label: "Decision tree" },
];

// Patient Studio. The publish button stays quiet until the checklist on the right is clear.
export function CaseStudio({ go, tab }: { go: Go; tab: StudioTab }) {
  const [current, setCurrent] = useState<StudioTab>(tab);
  const [facts, setFacts] = useState<Record<"a" | "b", FactState>>({ a: "pending", b: "pending" });
  const [drugFixed, setDrugFixed] = useState(false);

  // Follow the shell when another screen opens Studio on a chosen tab.
  // Local tab clicks update `current` and are not overwritten until `tab` changes again.
  useEffect(() => {
    setCurrent(tab);
  }, [tab]);

  const pendingFacts = Object.values(facts).filter((state) => state === "pending").length;
  const active = current;
  const tree = active === "tree";
  const header = tree ? STUDIO_CASES.tree : STUDIO_CASES.patient;
  const checks = [
    { label: "Patient profile", ok: true, note: "", tab: "patient" as const },
    { label: "Medicines recognized", ok: drugFixed, note: "Epirocil not found in RxNorm", tab: "patient" as const },
    { label: "Learning objectives", ok: true, note: "", tab: "objectives" as const },
    { label: "Rubric attached", ok: true, note: "", tab: "objectives" as const },
    { label: "Suggested facts reviewed", ok: pendingFacts === 0, note: pendingFacts ? `${pendingFacts} awaiting approval` : "", tab: "files" as const },
    { label: "Every path has an outcome", ok: true, note: "", tab: "tree" as const },
  ];
  const open = checks.filter((check) => !check.ok).length;

  function badgeFor(id: StudioTab) {
    if (id === "patient" && !drugFixed) return "1";
    if (id === "files" && pendingFacts) return String(pendingFacts);
    return "";
  }

  return (
    <div className="mx-auto flex max-w-[1320px] flex-col gap-5 px-10 pt-7 pb-12">
      <header className="flex flex-col gap-3.5">
        <BackLink label="Cases" onClick={() => go("f-cases")} />
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <Avatar who={header.who} size={52} />
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="m-0 font-serif text-[34px] leading-none font-medium tracking-[-0.7px]">{header.name}</h1>
                <Badge tone="warn" dot>
                  Draft
                </Badge>
              </div>
              <div className="mt-1 text-[13px] text-muted">{header.meta} · Saved 2 min ago</div>
            </div>
          </div>
          <div className="flex gap-2">
            <GhostButton>Preview as student</GhostButton>
            <button
              type="button"
              className={`h-10 rounded-[10px] px-[18px] text-sm font-medium text-white ${open ? "cursor-not-allowed bg-inactive" : "bg-panel"}`}
            >
              {open ? `Publish · ${open} to fix` : "Publish"}
            </button>
          </div>
        </div>
        <TabNav
          items={TABS.map((item) => ({ ...item, badge: badgeFor(item.id) || undefined }))}
          active={active}
          onChange={setCurrent}
        />
      </header>

      <div className="flex flex-wrap items-start gap-5">
        <div className="min-w-0 flex-[1_1_560px]">
          {active === "patient" ? <PatientTab drugFixed={drugFixed} onFix={() => setDrugFixed(true)} /> : null}
          {active === "objectives" ? <ObjectivesTab /> : null}
          {active === "files" ? <FilesTab facts={facts} setFacts={setFacts} /> : null}
          {active === "tree" ? <DecisionTree /> : null}
        </div>
        <aside className="sticky top-5 max-w-[340px] min-w-[260px] flex-[1_1_260px] overflow-hidden rounded-2xl border border-line bg-card">
          <div className="border-b border-hair-2 px-[18px] py-4">
            <div className="text-[15px] font-semibold">Ready to publish?</div>
            <div className="mt-0.5 text-[12.5px] text-muted">
              {open ? `${open} of ${checks.length} checks need attention` : "All checks passed"}
            </div>
            <div className="mt-3 flex gap-[3px]">
              {checks.map((check) => (
                <span key={check.label} className={`h-1 flex-1 rounded-sm ${check.ok ? "bg-[#4caf7f]" : "bg-[#efb26f]"}`} />
              ))}
            </div>
          </div>
          {checks.map((check) => (
            <button
              key={check.label}
              type="button"
              onClick={() => setCurrent(check.tab)}
              className="grid w-full grid-cols-[22px_minmax(0,1fr)] items-start gap-2.5 border-t border-hair px-[18px] py-[11px] text-left first:border-t-0 hover:bg-raised"
            >
              <Mark tone={check.ok ? "ok" : "warn"} className="mt-px">
                {check.ok ? "✓" : "!"}
              </Mark>
              <span>
                <span className="block text-[13.5px] font-medium">{check.label}</span>
                {check.ok ? null : <span className="mt-0.5 block text-[12.5px] text-warn">{check.note}</span>}
              </span>
            </button>
          ))}
        </aside>
      </div>
    </div>
  );
}

function PatientTab({ drugFixed, onFix }: { drugFixed: boolean; onFix: () => void }) {
  const columns = studioPatientColumns(drugFixed);

  return (
    <div className="grid items-start gap-3.5 [grid-template-columns:repeat(auto-fit,minmax(260px,1fr))]">
      {columns.map((column) => (
        <section key={column.title} className="overflow-hidden rounded-2xl border border-line bg-card">
          <div className="flex items-center justify-between border-b border-hair-2 px-4 py-3.5">
            <span className="text-[15px] font-semibold">
              {column.title} <span className="font-normal text-muted">{column.count}</span>
            </span>
            <button type="button" title={column.add} className="flex size-7 items-center justify-center rounded-lg border border-line-2 bg-card hover:bg-wash" aria-label={column.add}>
              <PlusIcon size={13} />
            </button>
          </div>
          {column.items.map((item) => (
            <div key={item.name + item.sub} className={`border-t border-hair px-4 py-3 first:border-t-0 ${item.issue ? "bg-warn-wash" : "bg-card"}`}>
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-[14.5px] font-semibold">{item.name}</span>
                {item.code ? <span className="text-xs text-muted tabular-nums">{item.code}</span> : null}
              </div>
              {item.sub ? (
                <div className={`mt-0.5 text-[13px] ${item.issue ? "text-warn" : item.danger ? "text-danger" : item.muted ? "text-muted" : "text-ink-soft"}`}>
                  {item.sub}
                </div>
              ) : null}
              {item.issue ? (
                <div className="mt-2.5 flex gap-1.5">
                  <button type="button" onClick={onFix} className="h-7 rounded-[7px] border border-[#e7c9a6] bg-card px-2.5 text-[12.5px] font-medium text-warn-deep dark:border-[#5a4426]">
                    Replace with eplerenone
                  </button>
                  <button type="button" onClick={onFix} className="h-7 rounded-[7px] px-2.5 text-[12.5px] text-warn-deep">
                    Keep as written
                  </button>
                </div>
              ) : null}
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}

function ObjectivesTab() {
  return (
    <div className="grid items-start gap-3.5 [grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr))]">
      <section className="overflow-hidden rounded-2xl border border-line bg-card">
        <CardHead
          title="Learning objectives"
          className="px-[18px] py-3.5"
          aside={<GhostButton size="sm">Add</GhostButton>}
        />
        {STUDIO_OBJECTIVES.map((item) => (
          <div key={item.n} className="grid grid-cols-[28px_minmax(0,1fr)] gap-3.5 border-t border-hair px-[18px] py-4 first:border-t-0">
            <span className="flex size-7 items-center justify-center rounded-lg bg-indigo-soft text-[13px] font-bold text-indigo">{item.n}</span>
            <div className="flex flex-col gap-2.5">
              <div className="text-[15px] leading-snug font-semibold">{item.text}</div>
              <div className="flex flex-wrap gap-1.5">
                {item.facts.map((fact) => (
                  <span key={fact} className="inline-flex h-[26px] items-center rounded-[7px] bg-chip px-2.5 text-[12.5px] text-ink-soft">
                    {fact}
                  </span>
                ))}
                {item.checks.map((check) => (
                  <span key={check} className="inline-flex h-[26px] items-center gap-1 rounded-[7px] bg-ok-soft px-2.5 text-[12.5px] font-medium text-ok">
                    ✓ Scored: {check}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </section>
      <section className="overflow-hidden rounded-2xl border border-line bg-card">
        <div className="border-b border-hair-2 px-[18px] py-3.5">
          <div className="text-[15px] font-semibold">Rubric</div>
          <div className="mt-0.5 text-[12.5px] text-muted">Official 7 domains · scored 1 to 4</div>
        </div>
        {RUBRIC_DOMAINS.map((label, index) => (
          <div key={label} className="grid grid-cols-[22px_minmax(0,1fr)] items-center gap-3 border-t border-hair px-[18px] py-2.5 text-sm first:border-t-0">
            <span className="text-[12.5px] text-muted tabular-nums">{index + 1}</span>
            <span>{label}</span>
          </div>
        ))}
      </section>
    </div>
  );
}

function FilesTab({
  facts,
  setFacts,
}: {
  facts: Record<"a" | "b", FactState>;
  setFacts: (next: Record<"a" | "b", FactState>) => void;
}) {
  return (
    <div className="flex flex-col gap-3.5">
      <section className="overflow-hidden rounded-2xl border border-line bg-card">
        <CardHead
          title="Suggested facts"
          className="px-[18px] py-3.5"
          aside={<span className="text-[12.5px] text-muted">From ADA Standards of Care in Diabetes, 2026</span>}
        />
        {STUDIO_SUGGESTED_FACTS.map((row) => {
          const state = facts[row.id];
          return (
            <div key={row.id} className={`grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-hair px-[18px] py-3.5 first:border-t-0 ${state === "pending" ? "bg-warn-wash" : "bg-card"}`}>
              <div>
                <div className={`text-[14.5px] leading-snug ${state === "dismissed" ? "text-faint" : "text-ink"}`}>{row.text}</div>
                <div className="mt-0.5 text-[12.5px] text-muted">
                  Page {row.page} · {state === "approved" ? "Approved" : state === "dismissed" ? "Dismissed" : "Awaiting approval"}
                </div>
              </div>
              {state === "pending" ? (
                <div className="flex gap-1.5">
                  <GhostButton size="sm" onClick={() => setFacts({ ...facts, [row.id]: "dismissed" })}>
                    Dismiss
                  </GhostButton>
                  <PrimaryButton size="sm" onClick={() => setFacts({ ...facts, [row.id]: "approved" })}>
                    Approve
                  </PrimaryButton>
                </div>
              ) : null}
            </div>
          );
        })}
      </section>
      <div className="grid gap-3.5 [grid-template-columns:repeat(auto-fit,minmax(260px,1fr))]">
        <FileCard title="12-lead ECG" kind="ecg" />
        <FileCard title="Chest X-ray, PA view" kind="xray" />
        <section className="flex flex-col gap-2.5 rounded-2xl border border-line bg-card p-4">
          <div className="flex size-10 items-center justify-center rounded-[10px] bg-danger-soft text-[11px] font-bold text-danger">PDF</div>
          <div className="text-[15px] leading-snug font-semibold">ADA Standards of Care in Diabetes, 2026</div>
          <div className="text-[13px] text-muted">184 pages · American Diabetes Association</div>
          <div className="mt-auto text-[12.5px] text-ink-soft">Knowledge source</div>
        </section>
      </div>
    </div>
  );
}

function FileCard({ title, kind }: { title: string; kind: "ecg" | "xray" }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-line bg-card">
      <div className={`h-[150px] ${kind === "ecg" ? "bg-[linear-gradient(#f7f8fc,#eef1f8)]" : "bg-[#111820]"}`}>
        {kind === "ecg" ? <EcgSketch /> : <XraySketch />}
      </div>
      <div className="flex flex-col gap-1.5 px-4 py-3.5">
        <div className="text-[15px] font-semibold">{title}</div>
        <div className="grid grid-cols-[90px_1fr] gap-x-2 gap-y-1 text-[13px]">
          <span className="text-muted">License</span>
          <span className="text-indigo">CC BY 4.0</span>
          <span className="text-muted">Attribution</span>
          <span className="text-indigo">Add source</span>
          <span className="text-muted">Released</span>
          <span>When the student orders it</span>
        </div>
      </div>
    </section>
  );
}

function EcgSketch() {
  return (
    <svg viewBox="0 0 320 150" className="h-full w-full" aria-hidden>
      <path d="M0 78 H40 l8 -28 10 56 8 -40 12 12 H320" fill="none" stroke="#2b3ab8" strokeWidth="2" />
      <path d="M0 40 H320 M0 110 H320" stroke="#d5d8ea" strokeWidth="1" />
    </svg>
  );
}

function XraySketch() {
  return (
    <svg viewBox="0 0 320 150" className="h-full w-full" aria-hidden>
      <ellipse cx="160" cy="78" rx="46" ry="58" fill="#2a3440" />
      <ellipse cx="160" cy="70" rx="18" ry="28" fill="#1a222b" />
      <path d="M114 78c18 8 74 8 92 0" fill="none" stroke="#8aa0b4" strokeWidth="3" />
    </svg>
  );
}
