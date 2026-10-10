import type { ReactNode } from "react";
import type { Go, VisitNumber } from "../../app/types";
import { MicIcon } from "../../components/Icons";
import { WALTER_BRIEFING_FACTS, WALTER_BRIEFING_VITALS, WALTER_GOAL } from "../../mock/walter";
import { DocIcon } from "../faculty/ImportPatients";

// Doorway briefing before the microphone check, shown over the clinic street.
// Visit 2 uses the follow-up goal, the student's own note and the new vitals.
export function Briefing({ go, visit }: { go: Go; visit: VisitNumber }) {
  const visitTwo = visit === 2;
  const facts = WALTER_BRIEFING_FACTS[visit];
  const fact = (key: string) => facts.find((item) => item.k === key)?.v ?? "";
  const carried = facts[2];

  return (
    <div className="rnd-enter flex min-h-full items-start justify-center px-[clamp(16px,4vw,64px)] pt-2 pb-10">
      <section className="w-full max-w-[1100px] rounded-[18px] border border-white/80 bg-card/92 p-[clamp(16px,1.8vw,26px)] shadow-[0_30px_80px_-40px_rgba(25,31,92,.6)] backdrop-blur-md">
        <header className="bg-banner flex min-h-[136px] flex-wrap items-center justify-between gap-4 rounded-[14px] px-[clamp(20px,3vw,40px)] py-6">
          <h1 className="m-0 font-serif text-[clamp(38px,4vw,62px)] leading-none font-normal tracking-[-1.4px] text-[#141a55]">Walter Greene, 72</h1>
          <span className="rounded-full border border-indigo-line/60 bg-white/80 px-6 py-2.5 font-sans text-[19px] text-[#141a55] backdrop-blur-sm">
            {visitTwo ? "Visit 2 · 3 months later" : "Visit 1 · New referral"}
          </span>
        </header>

        <div className="mt-4 grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr))]">
          <Tile icon={<PinIcon />} title="Setting">
            {fact("Setting")}
          </Tile>
          <Tile icon={<PersonIcon />} title="Your role">
            {fact("Your role")}
          </Tile>
          <Tile icon={<TargetIcon />} title="Goal">
            {WALTER_GOAL[visit]}
          </Tile>
          <Tile icon={<DocIcon size={26} />} title={`${carried.k}:`}>
            {carried.v}
          </Tile>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-x-10 gap-y-4 rounded-[14px] border border-line px-7 py-5">
          <div className="flex items-center gap-6">
            <IconDot>
              <HeartIcon />
            </IconDot>
            <span className="font-serif text-[26px] tracking-[-0.3px]">Doorway vitals</span>
          </div>
          <div className="flex flex-1 flex-wrap">
            {WALTER_BRIEFING_VITALS[visit].map((vital) => (
              <div key={vital.k} className="min-w-[96px] flex-1 border-l border-line px-5 first:border-l-0">
                <div className="font-sans text-[15px] text-ink-soft">{vital.k}</div>
                <div className={`font-serif text-[28px] tabular-nums ${vital.tone === "danger" ? "text-danger" : ""}`}>
                  {vital.v}
                  {vital.k === "Temp" ? " C" : ""}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-4 flex items-center justify-center gap-5 rounded-[14px] bg-indigo-soft/80 px-6 py-3.5 font-sans text-[17px]">
          <span className="flex size-12 items-center justify-center rounded-full bg-card text-ink">
            <MicIcon size={24} />
          </span>
          Your microphone stays on during the visit. Audio is recorded for feedback.
        </div>

        <div className="mt-5 flex justify-center">
          <button
            type="button"
            onClick={() => go("s-mic", { visit })}
            className="inline-flex h-[64px] w-full max-w-[480px] items-center justify-center gap-4 rounded-xl bg-panel font-serif text-[28px] text-white shadow-[0_16px_34px_-18px_rgba(37,45,120,.9)] hover:bg-ink"
          >
            Start visit
            <span aria-hidden>→</span>
          </button>
        </div>
      </section>
    </div>
  );
}

function Tile({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div className="flex items-center gap-6 rounded-[14px] border border-line px-7 py-5">
      <IconDot>{icon}</IconDot>
      <div>
        <div className="font-serif text-[26px] leading-tight tracking-[-0.3px]">{title}</div>
        <div className="mt-1 font-sans text-[18px] leading-snug text-ink">{children}</div>
      </div>
    </div>
  );
}

function IconDot({ children }: { children: ReactNode }) {
  return <span className="flex size-[60px] shrink-0 items-center justify-center rounded-full bg-indigo-soft text-ink">{children}</span>;
}

function PinIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M12 2.5a7 7 0 0 0-7 7c0 5 7 12 7 12s7-7 7-12a7 7 0 0 0-7-7zm0 9.6a2.6 2.6 0 1 1 0-5.2 2.6 2.6 0 0 1 0 5.2z" />
    </svg>
  );
}

function PersonIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <circle cx="12" cy="8" r="4.2" />
      <path d="M3.8 21c0-4.6 3.7-7.6 8.2-7.6s8.2 3 8.2 7.6z" />
    </svg>
  );
}

function TargetIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.4" fill="currentColor" />
    </svg>
  );
}

function HeartIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" aria-hidden>
      <path d="M12 20s-7.5-4.6-7.5-10.1A4.3 4.3 0 0 1 12 7.3a4.3 4.3 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z" />
    </svg>
  );
}
