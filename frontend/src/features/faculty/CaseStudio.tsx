import { useEffect, useState, type ReactNode } from "react";
import type { Go, StudioTab } from "../../app/types";
import { PlusIcon } from "../../components/Icons";
import { BuildTag, Mark, TabNav } from "../../components/ui";
import { RUBRIC_DOMAINS } from "../../lib/rubric";
import { STUDIO_CASES, STUDIO_OBJECTIVES, STUDIO_SUGGESTED_FACTS, studioPatientColumns, type StudioItem } from "../../mock/studio";
import { DecisionTree } from "./DecisionTree";
import { DocDot, DocIcon } from "./ImportPatients";

type FactState = "pending" | "approved" | "dismissed";

const TABS: { id: StudioTab; label: string }[] = [
  { id: "patient", label: "Diagnoses and medicines" },
  { id: "objectives", label: "Learning objectives" },
  { id: "files", label: "Files and sources" },
  { id: "tree", label: "Decision tree" },
];

// Patient Studio. Publishing stays blocked until every check in the publish list is clear.
export function CaseStudio({ go, tab }: { go: Go; tab: StudioTab }) {
  const [current, setCurrent] = useState<StudioTab>(tab);
  const [facts, setFacts] = useState<Record<"a" | "b", FactState>>({ a: "pending", b: "pending" });
  const [drugFixed, setDrugFixed] = useState(false);
  const [checklist, setChecklist] = useState(false);

  // Follow the shell when another screen opens Studio on a chosen tab.
  // Local tab clicks update `current` and are not overwritten until `tab` changes again.
  useEffect(() => {
    setCurrent(tab);
  }, [tab]);

  const pendingFacts = Object.values(facts).filter((state) => state === "pending").length;
  const tree = current === "tree";
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
    <div className="rnd-enter flex flex-col gap-5 px-5 pt-5 pb-8">
      <header className="bg-banner relative flex min-h-[120px] items-center justify-between gap-4 overflow-hidden rounded-[14px] px-10 py-6">
        <div className="absolute inset-0 bg-gradient-to-r from-white/45 via-white/10 to-transparent" />
        <h1 className="relative m-0 font-serif text-[clamp(38px,3.6vw,56px)] leading-none font-normal tracking-[-1.2px] text-[#141a55]">{header.name}</h1>
        <div className="relative flex items-center gap-1 rounded-full bg-white/80 p-1 font-serif text-[18px] text-[#141a55] backdrop-blur-sm">
          <button type="button" onClick={() => go("f-cases")} className="h-9 rounded-full px-4 hover:bg-indigo-soft">
            All cases
          </button>
          <span className="pr-4">Patient Studio · Draft</span>
        </div>
      </header>

      <div className="relative flex flex-wrap items-end justify-between gap-4 px-3">
        <TabNav
          items={TABS.map((item) => ({ ...item, badge: badgeFor(item.id) || undefined }))}
          active={current}
          onChange={setCurrent}
        />
        <div className="relative flex items-center gap-2 pb-2">
          <button type="button" className="h-11 rounded-xl border border-line-2 bg-card px-4 font-serif text-[17px] hover:bg-wash" title="Runs the test students on this case (PRD S-14)">
            Preview as student
          </button>
          <button
            type="button"
            onClick={() => setChecklist((value) => !value)}
            aria-expanded={checklist}
            className={`h-11 rounded-xl px-5 font-serif text-[17px] text-white ${open ? "bg-inactive" : "bg-panel"}`}
          >
            {open ? `Publish · ${open} to fix` : "Publish"}
          </button>
          {checklist ? (
            <div className="absolute top-full right-0 z-20 mt-2 w-[320px] overflow-hidden rounded-[14px] border border-line bg-card shadow-[0_24px_50px_-24px_rgba(25,31,92,.45)]">
              <div className="border-b border-hair-2 px-[18px] py-3.5">
                <div className="font-serif text-[20px]">Ready to publish?</div>
                <div className="font-sans text-[12.5px] text-muted">
                  {open ? `${open} of ${checks.length} checks need attention` : "All checks passed"}
                </div>
              </div>
              {checks.map((check) => (
                <button
                  key={check.label}
                  type="button"
                  onClick={() => {
                    setCurrent(check.tab);
                    setChecklist(false);
                  }}
                  className="grid w-full grid-cols-[24px_minmax(0,1fr)] items-start gap-2.5 border-t border-hair px-[18px] py-2.5 text-left first:border-t-0 hover:bg-raised"
                >
                  <Mark tone={check.ok ? "ok" : "warn"}>{check.ok ? "✓" : "!"}</Mark>
                  <span>
                    <span className="block font-serif text-[16px]">{check.label}</span>
                    {check.ok ? null : <span className="block font-sans text-[12.5px] text-warn">{check.note}</span>}
                  </span>
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      {current === "patient" ? <PatientTab drugFixed={drugFixed} onFix={() => setDrugFixed(true)} /> : null}
      {current === "objectives" ? <ObjectivesTab /> : null}
      {current === "files" ? <FilesTab facts={facts} setFacts={setFacts} /> : null}
      {tree ? <DecisionTree /> : null}
    </div>
  );
}

function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-[14px] border border-line bg-card ${className}`}>{children}</section>;
}

const ROW_ICONS: Record<string, { tone: string; icon: ReactNode }> = {
  Diagnoses: { tone: "bg-indigo-soft text-indigo", icon: <DocIcon size={26} /> },
  Medicines: { tone: "bg-indigo-soft text-indigo", icon: <PillIcon /> },
  Allergies: { tone: "bg-danger-soft text-danger", icon: <WarnIcon /> },
};

function PatientTab({ drugFixed, onFix }: { drugFixed: boolean; onFix: () => void }) {
  const columns = studioPatientColumns(drugFixed);

  return (
    <Panel className="px-5 pt-6 pb-5">
      <div className="flex flex-wrap items-center justify-between gap-4 px-2 pb-5">
        <div className="flex flex-wrap items-center gap-4">
          <h2 className="m-0 font-serif text-[clamp(30px,2.8vw,44px)] font-normal tracking-[-1px]">Diagnoses, medicines and allergies</h2>
          <BuildTag kind="sample" feature="S-08" />
        </div>
        <label className="flex h-14 w-full max-w-[520px] items-center gap-3 rounded-xl border border-line-2 bg-card px-4 text-muted">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
            <circle cx="11" cy="11" r="7" />
            <path d="M20 20l-4-4" />
          </svg>
          <input placeholder="Search diagnoses or medicines" className="min-w-0 flex-1 bg-transparent font-serif text-[19px] text-ink outline-none placeholder:text-muted" />
        </label>
      </div>
      <div className="grid items-start gap-4 [grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr))]">
        {columns.map((column) => (
          <div key={column.title} className="rounded-[14px] border border-line px-4 pt-4 pb-2">
            <div className="flex items-center justify-between gap-3 border-b border-hair-2 pb-4">
              <span className="font-serif text-[clamp(24px,2vw,32px)] tracking-[-0.5px]">
                {column.title} ({column.count})
              </span>
              <button type="button" className="inline-flex h-11 items-center gap-2 rounded-[10px] border border-indigo-line bg-card px-4 font-serif text-[17px] whitespace-nowrap text-ink hover:bg-indigo-soft">
                <PlusIcon size={16} />
                {column.add}
              </button>
            </div>
            {column.items.map((item) => (
              <StudioRow key={item.name + item.sub} item={item} kind={column.title} onFix={onFix} />
            ))}
          </div>
        ))}
      </div>
    </Panel>
  );
}

function StudioRow({ item, kind, onFix }: { item: StudioItem; kind: string; onFix: () => void }) {
  const look = item.issue ? { tone: "bg-warn-pill text-[#e08a2e]", icon: <WarnIcon /> } : ROW_ICONS[kind];
  return (
    <div className={`-mx-2 my-1 grid grid-cols-[56px_minmax(0,1fr)_20px] items-center gap-4 rounded-xl border-t border-hair-2 px-2 py-3 first:border-t-0 ${item.issue ? "border-t-0 bg-warn-wash" : ""}`}>
      <span className={`flex size-14 items-center justify-center rounded-full ${look.tone}`}>{look.icon}</span>
      <div className="min-w-0">
        {item.code ? <div className="font-sans text-[15px] text-muted tabular-nums">{item.code}</div> : null}
        <div className="font-serif text-[21px] leading-snug">{item.name}</div>
        {item.sub ? <div className={`font-sans text-[15px] ${item.issue ? "text-warn" : "text-muted"}`}>{item.issue ? "Not found in RxNorm, worth review" : item.sub}</div> : null}
        {item.issue ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            <button type="button" onClick={onFix} className="h-8 rounded-lg border border-warn-line bg-card px-3 font-sans text-[13px] font-medium text-warn-deep">
              Replace with eplerenone
            </button>
            <button type="button" onClick={onFix} className="h-8 rounded-lg px-3 font-sans text-[13px] text-warn-deep">
              Keep as written
            </button>
          </div>
        ) : null}
      </div>
      <Kebab />
    </div>
  );
}

function ObjectivesTab() {
  return (
    <Panel className="px-6 pt-6 pb-6">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line-3 pb-3">
        <div>
          <h2 className="m-0 font-serif text-[clamp(34px,3vw,48px)] leading-none font-normal tracking-[-1px]">Learning objectives</h2>
          <div className="mt-2 font-serif text-[22px] text-ink">Walter Greene, 72</div>
        </div>
        <BuildTag kind="sample" feature="S-13" />
      </div>
      <div className="mt-5 grid items-start gap-5 [grid-template-columns:minmax(0,1.6fr)_minmax(300px,1fr)] max-lg:grid-cols-1">
        <div className="flex flex-col gap-4">
          {STUDIO_OBJECTIVES.map((item) => (
            <div key={item.n} className="grid grid-cols-[84px_minmax(0,1fr)] items-start gap-5 rounded-[14px] border border-line px-6 py-6">
              <DocDot size={84} />
              <div className="flex flex-col gap-4">
                <div className="font-serif text-[clamp(22px,2vw,30px)] leading-tight tracking-[-0.4px]">{item.text}</div>
                <div className="flex flex-wrap gap-2.5">
                  {item.facts.map((fact) => (
                    <span key={fact} className="inline-flex h-12 items-center gap-2.5 rounded-xl bg-indigo-soft px-4 font-serif text-[18px]">
                      <span className="text-indigo">
                        <DocIcon size={20} />
                      </span>
                      {fact}
                    </span>
                  ))}
                  {item.checks.map((check) => (
                    <span key={check} className="inline-flex h-12 items-center gap-2.5 rounded-xl bg-ok-soft px-4 font-serif text-[18px]">
                      <span className="flex size-7 items-center justify-center rounded-full bg-ok text-white">✓</span>
                      {check.charAt(0).toUpperCase() + check.slice(1)}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="rounded-[14px] border border-line px-6 py-6">
          <div className="font-serif text-[clamp(24px,2vw,32px)] leading-tight tracking-[-0.5px]">Rubric: official 7 domains, 1 to 4 each</div>
          <div className="mt-4">
            {RUBRIC_DOMAINS.map((label, index) => (
              <div key={label} className="grid grid-cols-[52px_minmax(0,1fr)] items-center gap-4 border-t border-hair-2 py-3 first:border-t-0">
                <span className="flex size-[52px] items-center justify-center rounded-full bg-indigo-soft font-serif text-[22px]">{index + 1}</span>
                <span className="font-serif text-[20px]">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Panel>
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
    <div className="flex flex-col gap-5">
      <Panel className="px-6 pt-5 pb-6">
        <div className="flex flex-wrap items-center gap-4 pb-4">
          <h2 className="m-0 font-serif text-[clamp(30px,2.6vw,42px)] font-normal tracking-[-1px]">Files and sources</h2>
          <BuildTag kind="sample" feature="S-09" />
        </div>
        <div className="grid gap-5 [grid-template-columns:repeat(auto-fit,minmax(min(100%,460px),1fr))]">
          <FileCard title="12-lead ECG" art={<EcgSketch />} />
          <FileCard title="Chest X-ray (PA view)" art={<XraySketch />} />
        </div>
      </Panel>
      <Panel className="px-6 pt-5 pb-6">
        <div className="flex flex-wrap items-center gap-4 pb-4">
          <h2 className="m-0 font-serif text-[clamp(30px,2.6vw,42px)] font-normal tracking-[-1px]">Knowledge sources</h2>
          <BuildTag kind="planned" feature="S-17" />
        </div>
        <div className="grid gap-5 [grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr))]">
          <div className="flex gap-5 rounded-[14px] border border-line px-5 py-6">
            <span className="flex size-[78px] shrink-0 items-center justify-center rounded-full bg-danger-soft font-sans text-[15px] font-bold text-danger">PDF</span>
            <div>
              <div className="font-serif text-[26px] leading-tight tracking-[-0.4px]">ADA Standards of Care in Diabetes</div>
              <div className="mt-4 font-serif text-[17px] text-indigo">PDF · uploaded by faculty</div>
              <div className="mt-1 font-serif text-[17px] text-indigo">American Diabetes Association</div>
            </div>
          </div>
          {STUDIO_SUGGESTED_FACTS.map((row) => {
            const state = facts[row.id];
            return (
              <div key={row.id} className={`flex gap-4 rounded-[14px] border px-5 py-5 ${state === "pending" ? "border-warn-line-soft bg-warn-wash/50" : "border-line"}`}>
                <span className="flex size-14 shrink-0 items-center justify-center rounded-full bg-warn-pill font-serif text-[30px] text-[#3a2a12]">?</span>
                <div className="flex min-w-0 flex-1 flex-col">
                  <div className="font-serif text-[17px]">
                    Suggested fact {state === "pending" ? "(awaiting approval)" : state === "approved" ? "(approved)" : "(dismissed)"}
                  </div>
                  <div className={`mt-1 font-serif text-[20px] leading-snug ${state === "dismissed" ? "text-faint line-through" : ""}`}>{row.text}</div>
                  <div className="mt-3 font-serif text-[16px]">Page {row.page}</div>
                  {state === "pending" ? (
                    <div className="mt-4 grid grid-cols-2 gap-2.5">
                      <button type="button" onClick={() => setFacts({ ...facts, [row.id]: "approved" })} className="h-11 rounded-[10px] border border-indigo-line bg-indigo-soft font-serif text-[18px] hover:bg-indigo-soft-2">
                        ✓ Approve
                      </button>
                      <button type="button" onClick={() => setFacts({ ...facts, [row.id]: "dismissed" })} className="h-11 rounded-[10px] border border-line-2 bg-card font-serif text-[18px] hover:bg-wash">
                        ✕ Dismiss
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </Panel>
    </div>
  );
}

// The pictures are drawn in code as placeholders, so the license stays unset until a real file is attached.
function FileCard({ title, art }: { title: string; art: ReactNode }) {
  return (
    <div className="grid grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] items-center gap-6 rounded-[14px] border border-line p-4">
      <div className="aspect-[16/10] overflow-hidden rounded-lg">{art}</div>
      <div className="flex flex-col gap-2.5 font-serif text-[17px]">
        <div className="mb-1 font-serif text-[clamp(22px,1.8vw,28px)] tracking-[-0.4px]">{title}</div>
        <div>
          License: <span className="text-indigo underline underline-offset-4">add license</span>
        </div>
        <div>
          Attribution: <span className="text-indigo underline underline-offset-4">add source</span>
        </div>
        <div>Release rule: Released when the student orders it</div>
        <div className="font-sans text-[12px] text-muted">Placeholder drawing until a licensed file is attached.</div>
      </div>
    </div>
  );
}

function EcgSketch() {
  const beats = Array.from({ length: 6 }, (_, i) => i * 54);
  const trace = (y: number) => beats.map((x) => `L${x + 18} ${y} l4 -3 4 3 l4 0 l3 6 l4 -34 l4 40 l3 -12 l6 0 l6 -6 l6 6`).join(" ");
  return (
    <svg viewBox="0 0 320 200" preserveAspectRatio="none" className="h-full w-full bg-[#fdf0f2]" aria-hidden>
      <defs>
        <pattern id="ecg-small" width="8" height="8" patternUnits="userSpaceOnUse">
          <path d="M8 0H0V8" fill="none" stroke="#f3c3cc" strokeWidth="0.5" />
        </pattern>
        <pattern id="ecg-big" width="40" height="40" patternUnits="userSpaceOnUse">
          <rect width="40" height="40" fill="url(#ecg-small)" />
          <path d="M40 0H0V40" fill="none" stroke="#eba1ae" strokeWidth="0.9" />
        </pattern>
      </defs>
      <rect width="320" height="200" fill="url(#ecg-big)" />
      <path d={`M0 70 ${trace(70)} L320 70`} fill="none" stroke="#2a2a3a" strokeWidth="1.3" />
      <path d={`M0 150 ${trace(150)} L320 150`} fill="none" stroke="#2a2a3a" strokeWidth="1.3" />
    </svg>
  );
}

function XraySketch() {
  return (
    <svg viewBox="0 0 320 200" preserveAspectRatio="xMidYMid slice" className="h-full w-full" aria-hidden>
      <defs>
        <radialGradient id="xr-bg" cx="50%" cy="45%" r="70%">
          <stop offset="0" stopColor="#3b4048" />
          <stop offset="1" stopColor="#0d1014" />
        </radialGradient>
        <filter id="xr-blur">
          <feGaussianBlur stdDeviation="3" />
        </filter>
      </defs>
      <rect width="320" height="200" fill="url(#xr-bg)" />
      <g filter="url(#xr-blur)">
        <ellipse cx="118" cy="105" rx="46" ry="74" fill="#14181e" />
        <ellipse cx="202" cy="105" rx="46" ry="74" fill="#14181e" />
        <rect x="150" y="10" width="20" height="190" fill="#8b9097" />
        <ellipse cx="180" cy="150" rx="40" ry="34" fill="#9aa0a6" opacity="0.8" />
        {[40, 62, 84, 106, 128].map((y) => (
          <path key={y} d={`M70 ${y} Q118 ${y - 18} 152 ${y + 4} M250 ${y} Q202 ${y - 18} 168 ${y + 4}`} stroke="#6d737b" strokeWidth="4" fill="none" />
        ))}
      </g>
    </svg>
  );
}

function PillIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden>
      <rect x="2.8" y="8.5" width="18.4" height="7" rx="3.5" transform="rotate(-45 12 12)" />
      <path d="M9.5 9.5l5 5" />
    </svg>
  );
}

function WarnIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinejoin="round" aria-hidden>
      <path d="M12 3.5L2.5 20h19z" />
      <path d="M12 10v4.5M12 17.2v.3" strokeLinecap="round" />
    </svg>
  );
}

function Kebab() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" className="text-indigo" aria-hidden>
      <circle cx="12" cy="5" r="1.9" />
      <circle cx="12" cy="12" r="1.9" />
      <circle cx="12" cy="19" r="1.9" />
    </svg>
  );
}
