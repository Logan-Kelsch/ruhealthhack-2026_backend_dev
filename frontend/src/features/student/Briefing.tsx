import type { Go, VisitNumber } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { ArrowRight } from "../../components/Icons";
import { BackLink, Card, Page } from "../../components/ui";

// Doorway briefing before the microphone check. Visit 2 uses the follow-up goal and vitals.
export function Briefing({ go, visit }: { go: Go; visit: VisitNumber }) {
  const visitTwo = visit === 2;
  const facts = [
    { k: "Setting", v: "Outpatient nutrition clinic" },
    { k: "Your role", v: "Dietetics student" },
    visitTwo
      ? { k: "Your note from visit 1", v: "Excessive sodium intake related to frequent restaurant meals and canned soups." }
      : { k: "From primary care", v: "Heart failure, kidney disease and type 2 diabetes. Review sodium and diet." },
  ];
  const vitals = [
    { k: "BP", v: visitTwo ? "146/88" : "158/92", note: "Elevated", color: "#b42b24" },
    { k: "HR", v: "78", note: "bpm", color: "#141b4d" },
    { k: "RR", v: "18", note: "/min", color: "#141b4d" },
    { k: "Temp", v: "37.0", note: "°C", color: "#141b4d" },
    { k: "SpO₂", v: "96%", note: "Room air", color: "#141b4d" },
  ];

  return (
    <Page width="max-w-[820px]">
      <BackLink
        label={visitTwo ? "What happened after visit 1" : "Home"}
        onClick={() => go(visitTwo ? "s-between" : "s-home")}
      />
      <header className="flex items-center gap-[18px]">
        <Avatar who="walter" size={72} />
        <div>
          <div className="text-[13px] font-semibold text-indigo">{visitTwo ? "Visit 2 · 3 months later" : "Visit 1 · New referral"}</div>
          <h1 className="m-0 mt-0.5 font-serif text-[38px] leading-none font-medium tracking-[-0.8px]">Walter Greene, 72</h1>
        </div>
      </header>
      <section className="rounded-2xl bg-ink px-6 py-5 text-white">
        <div className="text-xs font-semibold tracking-[0.6px] text-[#a9b6ff] uppercase">Your goal</div>
        <div className="mt-1.5 font-serif text-2xl leading-snug text-pretty">
          {visitTwo ? "Review what changed since the first visit and adjust the plan." : "Assess diet and medicines; agree on one change."}
        </div>
      </section>
      <Card>
        {facts.map((fact) => (
          <div key={fact.k} className="grid grid-cols-[160px_minmax(0,1fr)] gap-4 border-t border-hair px-5 py-3.5 first:border-t-0">
            <span className="text-[13px] text-muted">{fact.k}</span>
            <span className="text-[14.5px] leading-snug">{fact.v}</span>
          </div>
        ))}
      </Card>
      <Card>
        <div className="border-b border-[#eeeff5] px-5 py-3.5 text-[15px] font-semibold">Doorway vitals</div>
        <div className="grid [grid-template-columns:repeat(auto-fit,minmax(110px,1fr))]">
          {vitals.map((vital) => (
            <div key={vital.k} className="border-r border-hair px-5 py-3.5">
              <div className="text-[12.5px] text-muted">{vital.k}</div>
              <div className="mt-1 text-[22px] font-semibold tracking-[-0.4px] tabular-nums" style={{ color: vital.color }}>
                {vital.v}
              </div>
              <div className="mt-0.5 text-xs" style={{ color: vital.color }}>
                {vital.note}
              </div>
            </div>
          ))}
        </div>
      </Card>
      <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
        <div className="flex items-center gap-2.5 text-[13px] text-ink-soft">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
            <rect x="9" y="3" width="6" height="11" rx="3" />
            <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
          </svg>
          Your mic stays on during the visit. Audio is recorded for feedback.
        </div>
        <button
          type="button"
          onClick={() => go("s-mic", { visit })}
          className="inline-flex h-12 items-center gap-2.5 rounded-xl bg-ink px-[22px] text-[15px] font-semibold text-white hover:bg-indigo"
        >
          Continue to mic check
          <ArrowRight />
        </button>
      </div>
    </Page>
  );
}
