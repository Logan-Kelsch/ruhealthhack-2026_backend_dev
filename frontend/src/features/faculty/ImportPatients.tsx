import { useState } from "react";
import type { Go } from "../../app/types";
import { BuildTag, Page } from "../../components/ui";
import { SAMPLE_PATIENTS } from "../../mock/faculty";
import { PersonDot } from "./FacultyHome";

// Sample-patient importer. Opening a row shows the consistency notes for that profile.
export function ImportPatients({ go }: { go: Go }) {
  const [open, setOpen] = useState<string | null>("Walter Greene");

  return (
    <Page>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="m-0 font-serif text-[clamp(40px,4vw,54px)] leading-none font-normal tracking-[-1.2px]">Import sample patients</h1>
          <p className="mt-2.5 font-serif text-[19px] text-ink-soft">These sample profiles are ready to explore in Studio.</p>
        </div>
        <BuildTag kind="sample" feature="S-16, S-12" />
      </header>

      <div className="overflow-hidden rounded-[14px] border border-line bg-card">
        {SAMPLE_PATIENTS.map((item) => {
          const expanded = open === item.name;
          const count = item.flags.length;
          return (
            <div key={item.name} className={`border-t border-hair-2 first:border-t-0 ${expanded ? "bg-raised" : ""}`}>
              <button
                type="button"
                onClick={() => setOpen(expanded ? null : item.name)}
                aria-expanded={expanded}
                className="grid w-full grid-cols-[44px_minmax(0,1fr)_24px] items-center gap-5 px-5 py-2.5 text-left hover:bg-raised"
              >
                <PersonDot size={44} />
                <span className="flex flex-wrap items-center gap-x-5 gap-y-1">
                  <span className="font-serif text-[clamp(20px,1.7vw,26px)] tracking-[-0.3px]">{item.name}</span>
                  <span className="font-serif text-[20px] text-ink-soft">{item.age}</span>
                  {count ? (
                    <span className="inline-flex h-9 items-center rounded-full bg-warn-pill px-4 font-serif text-[17px] text-warn-deep">
                      {count} worth review
                    </span>
                  ) : null}
                </span>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className={`text-ink-soft transition-transform ${expanded ? "rotate-180" : ""}`} aria-hidden>
                  <path d="M6 9l6 6 6-6" />
                </svg>
              </button>
              {expanded ? (
                <div className="grid items-center gap-4 px-5 pb-4 pl-[84px] [grid-template-columns:minmax(0,1fr)_auto]">
                  {count ? (
                    <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(260px,1fr))]">
                      {item.flags.map((flag) => (
                        <div key={flag} className="flex items-center gap-4 rounded-xl border border-line bg-card px-4 py-3">
                          <DocDot />
                          <span className="font-serif text-[17px] leading-snug">{flag}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="font-serif text-[18px] text-ok">{item.summary} No inconsistencies found.</div>
                  )}
                  <button
                    type="button"
                    onClick={() => go("f-studio", { studioTab: "patient" })}
                    className="inline-flex h-14 items-center gap-3 rounded-xl border border-indigo-line bg-card px-7 font-serif text-[20px] text-ink hover:bg-indigo-soft"
                  >
                    <DocIcon />
                    Open in Studio
                  </button>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </Page>
  );
}

export function DocIcon({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinejoin="round" strokeLinecap="round" aria-hidden>
      <path d="M6 3h8l4.5 4.5V21H6z" />
      <path d="M14 3v4.5h4.5M9 12h6M9 15.5h6" />
    </svg>
  );
}

export function DocDot({ size = 40 }: { size?: number }) {
  return (
    <span className="flex shrink-0 items-center justify-center rounded-full bg-indigo-soft text-indigo" style={{ width: size, height: size }}>
      <DocIcon size={size * 0.5} />
    </span>
  );
}
