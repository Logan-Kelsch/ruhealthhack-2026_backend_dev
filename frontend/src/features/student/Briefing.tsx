import type { Go, VisitNumber } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { ArrowRight, MicIcon } from "../../components/Icons";
import { BackLink, Card, CardHead, Page, PrimaryButton } from "../../components/ui";

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
    { k: "BP", v: visitTwo ? "146/88" : "158/92", note: "Elevated", tone: "danger" },
    { k: "HR", v: "78", note: "bpm", tone: "ink" },
    { k: "RR", v: "18", note: "/min", tone: "ink" },
    { k: "Temp", v: "37.0", note: "°C", tone: "ink" },
    { k: "SpO₂", v: "96%", note: "Room air", tone: "ink" },
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
        <div className="text-xs font-semibold tracking-[0.6px] text-indigo-on-ink uppercase">Your goal</div>
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
        <CardHead title="Doorway vitals" className="px-5 py-3.5" />
        <div className="grid [grid-template-columns:repeat(auto-fit,minmax(110px,1fr))]">
          {vitals.map((vital) => (
            <div key={vital.k} className="border-r border-hair px-5 py-3.5">
              <div className="text-[12.5px] text-muted">{vital.k}</div>
              <div className={`mt-1 text-[22px] font-semibold tracking-[-0.4px] tabular-nums ${vital.tone === "danger" ? "text-danger" : "text-ink"}`}>
                {vital.v}
              </div>
              <div className={`mt-0.5 text-xs ${vital.tone === "danger" ? "text-danger" : "text-ink"}`}>
                {vital.note}
              </div>
            </div>
          ))}
        </div>
      </Card>
      <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
        <div className="flex items-center gap-2.5 text-[13px] text-ink-soft">
          <MicIcon />
          Your mic stays on during the visit. Audio is recorded for feedback.
        </div>
        <PrimaryButton size="lg" onClick={() => go("s-mic", { visit })}>
          Continue to mic check
          <ArrowRight />
        </PrimaryButton>
      </div>
    </Page>
  );
}
