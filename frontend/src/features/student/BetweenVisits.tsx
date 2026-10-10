import type { ReactNode } from "react";
import type { Go } from "../../app/types";
import { BuildTag, Page, Title } from "../../components/ui";
import { WALTER_BETWEEN_VISITS_EVENTS } from "../../mock/walter";
import { DocIcon } from "../faculty/ImportPatients";

const EVENT_LOOK: { tone: string; icon: ReactNode }[] = [
  { tone: "bg-indigo-soft text-indigo", icon: <PillIcon /> },
  { tone: "bg-warn-pill text-[#b5651d]", icon: <ForkIcon /> },
  { tone: "bg-danger-soft text-danger", icon: <FootIcon /> },
];

// What changed between visits, based on the plan from visit 1. This is the doorway into visit 2.
export function BetweenVisits({ go }: { go: Go }) {
  return (
    <Page>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Title>What happened after your visit</Title>
          <p className="mt-3 max-w-[720px] font-serif text-[19px] leading-snug text-ink-soft">
            You agreed with Walter to cut back on canned soups and stop the Advil. These changes follow from that, and he will bring them up in visit 2.
          </p>
        </div>
        <BuildTag kind="sample" feature="L-04" />
      </div>

      <div className="overflow-x-auto pb-2">
        <div className="relative mx-auto grid min-w-[1040px] grid-cols-[200px_1fr_1fr_1fr_200px] gap-x-5 pt-6">
          <span className="absolute top-[78px] right-[210px] left-[190px] h-[2px] bg-indigo-line" aria-hidden />
          <span className="absolute top-[71px] right-[198px] border-y-8 border-l-[14px] border-y-transparent border-l-indigo-line" aria-hidden />
          <Stop title="Visit 1" />
          {WALTER_BETWEEN_VISITS_EVENTS.map((event, index) => (
            <div key={event.text} className="relative flex flex-col items-center pt-[42px]">
              <span className="z-10 size-4 rounded-full border-2 border-indigo-line bg-card" />
              <span className="h-[38px] w-[2px] bg-indigo-line" />
              <span className="-mt-1 size-2 rounded-full bg-indigo-line" />
              <div className="mt-1 flex w-full items-center gap-4 rounded-[14px] border border-line bg-card px-5 py-5 shadow-[0_10px_30px_-24px_rgba(25,31,92,.4)]">
                <span className={`flex size-14 shrink-0 items-center justify-center rounded-full ${EVENT_LOOK[index % 3].tone}`}>{EVENT_LOOK[index % 3].icon}</span>
                <span>
                  <span className="block font-serif text-[20px] leading-tight">{event.text}</span>
                  <span className={`mt-1 block font-sans text-[13px] ${event.tone === "ok" ? "text-ok" : "text-warn"}`}>{event.tag}</span>
                </span>
              </div>
            </div>
          ))}
          <Stop title="Visit 2" sub="3 months later" />
        </div>
      </div>

      <div className="flex justify-center pt-6">
        <button
          type="button"
          onClick={() => go("s-brief", { visit: 2 })}
          className="inline-flex h-[64px] items-center gap-4 rounded-xl border-[1.5px] border-indigo bg-indigo-soft px-16 font-serif text-[24px] hover:bg-indigo-soft-2"
        >
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinejoin="round" strokeLinecap="round" aria-hidden>
            <path d="M5 21V4M5 4h11l-2 4 2 4H5" />
          </svg>
          Start visit 2
        </button>
      </div>
    </Page>
  );
}

function Stop({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="z-10 flex h-[106px] items-center gap-5 self-start rounded-[14px] border border-line bg-card px-4 shadow-[0_10px_30px_-24px_rgba(25,31,92,.4)]">
      <span className="flex size-14 shrink-0 items-center justify-center rounded-full bg-indigo-soft text-indigo">
        <DocIcon size={28} />
      </span>
      <span>
        <span className="block font-serif text-[26px] leading-tight">{title}</span>
        {sub ? <span className="block font-sans text-[15px]">{sub}</span> : null}
      </span>
    </div>
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

function ForkIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" aria-hidden>
      <path d="M6 3v6a2 2 0 0 0 4 0V3M8 11v10M16 21V3c-2 1.5-3 4-3 7h3" />
    </svg>
  );
}

function FootIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinejoin="round" aria-hidden>
      <path d="M9 3v10.5c0 1-1.5 2-3.5 3S4 20 6 20.5h11c1.5 0 2-1.5 1-2.5-2-2-4.5-2.5-5-4V3" />
    </svg>
  );
}
