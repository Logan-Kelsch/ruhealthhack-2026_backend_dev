import type { Go } from "../../app/types";
import { ArrowRight } from "../../components/Icons";
import { Badge, PrimaryButton, Title } from "../../components/ui";

const EVENTS = [
  { text: "Stopped the Advil", tag: "Followed plan", tone: "ok" as const },
  { text: "Same dinner-club meals twice a week", tag: "No change", tone: "warn" as const },
  { text: "Ankle swelling about the same", tag: "No change", tone: "warn" as const },
];

// What changed between visits, based on the plan from visit 1. This is the doorway into visit 2.
export function BetweenVisits({ go }: { go: Go }) {
  return (
    <div className="mx-auto flex max-w-[720px] flex-col gap-7 px-10 pt-10 pb-14">
      <header>
        <Title kicker="Walter Greene, 72 · 3 months pass">What happened after your visit</Title>
        <p className="mt-2.5 text-[15px] leading-normal text-ink-soft">
          These changes follow from what you asked and agreed on in visit 1. Walter will bring them up in visit 2.
        </p>
      </header>
      <section className="rounded-2xl border border-line bg-card px-6 py-2">
        <div className="grid grid-cols-[24px_minmax(0,1fr)] gap-4 py-3.5">
          <div className="flex flex-col items-center">
            <span className="mt-0.5 size-3.5 rounded-full bg-ink" />
            <span className="mt-1 w-0.5 flex-1 bg-line-3" />
          </div>
          <div>
            <div className="text-[15px] font-semibold">Visit 1</div>
            <div className="mt-0.5 text-[13px] text-muted">Agreed: cut back on canned soups and stop the Advil</div>
          </div>
        </div>
        {EVENTS.map((event) => (
          <div key={event.text} className="grid grid-cols-[24px_minmax(0,1fr)_auto] items-start gap-4 py-3">
            <div className="flex flex-col items-center self-stretch">
              <span className={`mt-1 size-2.5 rounded-full border-2 bg-card ${event.tone === "ok" ? "border-ok" : "border-warn"}`} />
              <span className="mt-1 w-0.5 flex-1 bg-line-3" />
            </div>
            <div className="text-[15px] leading-snug">{event.text}</div>
            <Badge tone={event.tone}>{event.tag}</Badge>
          </div>
        ))}
        <div className="grid grid-cols-[24px_minmax(0,1fr)] gap-4 py-3.5">
          <div className="flex justify-center">
            <span className="mt-0.5 size-3.5 rounded-full border-2 border-ink bg-card" />
          </div>
          <div>
            <div className="text-[15px] font-semibold">Visit 2</div>
            <div className="mt-0.5 text-[13px] text-muted">3 months later · ready when you are</div>
          </div>
        </div>
      </section>
      <PrimaryButton size="lg" className="w-fit self-start" onClick={() => go("s-brief", { visit: 2 })}>
        Start visit 2
        <ArrowRight />
      </PrimaryButton>
    </div>
  );
}
