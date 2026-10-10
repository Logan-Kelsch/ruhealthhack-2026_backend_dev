import { useState } from "react";
import type { Go } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { Badge, BackLink, Page, PrimaryButton, Title } from "../../components/ui";
import { SAMPLE_PATIENTS } from "../../mock/faculty";

// Sample-patient importer. Selecting a name shows the consistency notes for that profile.
export function ImportPatients({ go }: { go: Go }) {
  const [selected, setSelected] = useState("Walter Greene");
  const patient = SAMPLE_PATIENTS.find((item) => item.name === selected) ?? SAMPLE_PATIENTS[0];
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
        <section className="max-w-[380px] min-w-[280px] flex-1 overflow-hidden rounded-2xl border border-line bg-card">
          <div className="border-b border-hair-2 px-5 py-3.5 text-[13px] text-muted">8 patients</div>
          {SAMPLE_PATIENTS.map((item) => {
            const on = item.name === selected;
            const count = item.flags.length;
            return (
              <button
                key={item.name}
                type="button"
                onClick={() => setSelected(item.name)}
                className={`grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-t border-hair px-5 py-3 text-left first:border-t-0 hover:bg-raised ${on ? "bg-indigo-soft shadow-[inset_3px_0_0_var(--color-indigo)]" : "bg-card"}`}
              >
                <span className={`text-[14.5px] ${on ? "font-semibold" : "font-medium"}`}>
                  {item.name} <span className="font-normal text-muted">{item.age}</span>
                </span>
                <Badge tone={count ? "warn" : "neutral"}>{count ? `${count} to review` : "Ready"}</Badge>
              </button>
            );
          })}
        </section>

        <section className="min-w-0 flex-[2] overflow-hidden rounded-2xl border border-line bg-card">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-hair-2 px-6 py-5">
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
              <div className="flex flex-col overflow-hidden rounded-xl border border-warn-line">
                {patient.flags.map((flag) => (
                  <div key={flag} className="grid grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-3 border-t border-warn-line-soft bg-warn-wash px-4 py-3 first:border-t-0">
                    <span className="flex size-7 items-center justify-center rounded-full bg-warn-pill text-sm font-bold text-warn">!</span>
                    <span className="text-[14.5px]">{flag}</span>
                    <span className="text-[12.5px] font-medium text-warn">Fix in Studio</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex items-center gap-3 rounded-xl bg-ok-wash px-4 py-3.5 text-[14.5px] text-ok">
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
