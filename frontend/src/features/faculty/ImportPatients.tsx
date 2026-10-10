import { useState } from "react";
import type { Go } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { BackLink, Page, PrimaryButton, Title } from "../../components/ui";

type Patient = {
  name: string;
  age: number;
  summary: string;
  flags: string[];
};

const PATIENTS: Patient[] = [
  { name: "Dominic Rivera", age: 22, summary: "College athlete with low energy during training season.", flags: [] },
  { name: "Yvette Armstrong", age: 64, summary: "Newly diagnosed celiac disease, lives with her daughter.", flags: ["Gluten-free diet started before biopsy date"] },
  { name: "Nisha Patel", age: 29, summary: "Gestational diabetes at 28 weeks, vegetarian.", flags: [] },
  { name: "Omar Sinclair", age: 45, summary: "Six months after bariatric surgery. Protein and supplements.", flags: ["B12 listed twice with different doses"] },
  { name: "Marcus Ramirez", age: 59, summary: "COPD with unintended weight loss.", flags: [] },
  {
    name: "Walter Greene",
    age: 72,
    summary: "Heart failure, kidney disease and type 2 diabetes.",
    flags: [
      "Notes say high sodium, but the lab shows Na 136",
      "Widowed, but one line mentions his kids",
      "Unknown drug name: Epirocil",
      "Weight change described two different ways",
    ],
  },
  { name: "Wyatt Nelson", age: 18, summary: "Type 1 diabetes, moving out for college.", flags: [] },
  { name: "Vladko Bareche", age: 31, summary: "Crohn’s disease flare, low-residue diet questions.", flags: [] },
];

// Sample-patient importer. Selecting a name shows the consistency notes for that profile.
export function ImportPatients({ go }: { go: Go }) {
  const [selected, setSelected] = useState("Walter Greene");
  const patient = PATIENTS.find((item) => item.name === selected) ?? PATIENTS[0];
  const flagCount = patient.flags.length;

  return (
    <Page>
      <header>
        <BackLink label="Cases" onClick={() => go("f-cases")} />
        <div className="mt-2.5">
          <Title>Import sample patients</Title>
        </div>
        <p className="mt-2 max-w-[620px] text-[15px] text-ink-soft">
          Ready-made profiles you can open in Studio. We check each one for inconsistencies before you publish.
        </p>
      </header>

      <div className="flex flex-wrap items-start gap-4">
        <section className="max-w-[380px] min-w-[280px] flex-1 overflow-hidden rounded-2xl border border-line bg-white">
          <div className="border-b border-[#eeeff5] px-5 py-3.5 text-[13px] text-muted">8 patients</div>
          {PATIENTS.map((item) => {
            const on = item.name === selected;
            const count = item.flags.length;
            return (
              <button
                key={item.name}
                type="button"
                onClick={() => setSelected(item.name)}
                className={`grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-t border-hair px-5 py-3 text-left hover:bg-[#fafafd] ${on ? "bg-[#f6f7fe] shadow-[inset_3px_0_0_#2b3ab8]" : "bg-white"}`}
              >
                <span className={`text-[14.5px] ${on ? "font-semibold" : "font-medium"}`}>
                  {item.name} <span className="font-normal text-muted">{item.age}</span>
                </span>
                <span className={`inline-flex h-[22px] items-center rounded-md px-2 text-xs font-semibold ${count ? "bg-[#fdf1e3] text-warn" : "bg-[#f1f2f7] text-muted"}`}>
                  {count ? `${count} to review` : "Ready"}
                </span>
              </button>
            );
          })}
        </section>

        <section className="min-w-0 flex-[2] overflow-hidden rounded-2xl border border-line bg-white">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#eeeff5] px-6 py-5">
            <div className="flex items-center gap-3.5">
              <Avatar who={patient.name === "Walter Greene" ? "walter" : "generic"} size={48} />
              <div>
                <div className="font-serif text-[26px] leading-tight font-medium tracking-[-0.4px]">
                  {patient.name}, {patient.age}
                </div>
                <div className="mt-0.5 text-[13.5px] text-ink-soft">{patient.summary}</div>
              </div>
            </div>
            <PrimaryButton onClick={() => go("f-studio", { studioTab: "patient" })}>Open in Studio</PrimaryButton>
          </div>
          <div className="flex flex-col gap-3 px-6 py-5">
            <div className="flex items-center justify-between">
              <span className="text-[15px] font-semibold">Worth reviewing</span>
              <span className="text-[13px] text-muted">
                {flagCount ? `${flagCount} ${flagCount === 1 ? "issue" : "issues"}` : "All clear"}
              </span>
            </div>
            {flagCount > 0 ? (
              <div className="flex flex-col overflow-hidden rounded-xl border border-[#f3dcc2]">
                {patient.flags.map((flag) => (
                  <div key={flag} className="grid grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-3 border-t border-[#f6e6d3] bg-[#fffaf4] px-4 py-3 first:border-t-0">
                    <span className="flex size-7 items-center justify-center rounded-full bg-[#fde6cc] text-sm font-bold text-warn">!</span>
                    <span className="text-[14.5px]">{flag}</span>
                    <span className="text-[12.5px] font-medium text-warn">Fix in Studio</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex items-center gap-3 rounded-xl bg-[#f1f9f4] px-4 py-3.5 text-[14.5px] text-ok">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M5 12.5l4.5 4.5L19 7.5" />
                </svg>
                No inconsistencies found.
              </div>
            )}
          </div>
        </section>
      </div>
    </Page>
  );
}
