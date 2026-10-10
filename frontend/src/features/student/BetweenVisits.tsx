import type { Go } from "../../app/types";
import { ArrowRight } from "../../components/Icons";

const EVENTS = [
  { text: "Stopped the Advil", tag: "Followed plan", color: "#1f7a50", bg: "#e6f4ec" },
  { text: "Same dinner-club meals twice a week", tag: "No change", color: "#9a5212", bg: "#fdf1e3" },
  { text: "Ankle swelling about the same", tag: "No change", color: "#9a5212", bg: "#fdf1e3" },
];

// What changed between visits, based on the plan from visit 1. This is the doorway into visit 2.
export function BetweenVisits({ go }: { go: Go }) {
  return (
    <div className="mx-auto flex max-w-[720px] flex-col gap-7 px-10 pt-10 pb-14">
      <header>
        <div className="mb-1.5 text-[13px] text-muted">Walter Greene, 72 · 3 months pass</div>
        <h1 className="m-0 font-serif text-[38px] leading-none font-medium tracking-[-0.8px]">What happened after your visit</h1>
        <p className="mt-2.5 text-[15px] leading-normal text-ink-soft">
          These changes follow from what you asked and agreed on in visit 1. Walter will bring them up in visit 2.
        </p>
      </header>
      <section className="rounded-2xl border border-line bg-white px-6 py-2">
        <div className="grid grid-cols-[24px_minmax(0,1fr)] gap-4 py-3.5">
          <div className="flex flex-col items-center">
            <span className="mt-0.5 size-3.5 rounded-full bg-ink" />
            <span className="mt-1 w-0.5 flex-1 bg-[#e3e4ee]" />
          </div>
          <div>
            <div className="text-[15px] font-semibold">Visit 1</div>
            <div className="mt-0.5 text-[13px] text-muted">Agreed: cut back on canned soups and stop the Advil</div>
          </div>
        </div>
        {EVENTS.map((event) => (
          <div key={event.text} className="grid grid-cols-[24px_minmax(0,1fr)_auto] items-start gap-4 py-3">
            <div className="flex flex-col items-center self-stretch">
              <span className="mt-1 size-2.5 rounded-full border-2 bg-white" style={{ borderColor: event.color }} />
              <span className="mt-1 w-0.5 flex-1 bg-[#e3e4ee]" />
            </div>
            <div className="text-[15px] leading-snug">{event.text}</div>
            <span className="inline-flex h-[22px] items-center rounded-md px-2 text-xs font-semibold" style={{ background: event.bg, color: event.color }}>
              {event.tag}
            </span>
          </div>
        ))}
        <div className="grid grid-cols-[24px_minmax(0,1fr)] gap-4 py-3.5">
          <div className="flex justify-center">
            <span className="mt-0.5 size-3.5 rounded-full border-2 border-ink bg-white" />
          </div>
          <div>
            <div className="text-[15px] font-semibold">Visit 2</div>
            <div className="mt-0.5 text-[13px] text-muted">3 months later · ready when you are</div>
          </div>
        </div>
      </section>
      <button
        type="button"
        onClick={() => go("s-brief", { visit: 2 })}
        className="inline-flex h-12 w-fit items-center gap-2.5 self-start rounded-xl bg-ink px-[22px] text-[15px] font-semibold text-white hover:bg-indigo"
      >
        Start visit 2
        <ArrowRight />
      </button>
    </div>
  );
}
