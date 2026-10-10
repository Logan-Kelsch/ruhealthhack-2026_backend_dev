import type { Go } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { ArrowRight, Chevron } from "../../components/Icons";
import { Card, Page, Title } from "../../components/ui";

// Student landing. The next assigned visit is Walter Greene.
export function StudentHome({ go }: { go: Go }) {
  const assigned = [
    { name: "Alina Reyes, 21", meta: "Visit 1 of 2 · Student health clinic", due: "Oct 24", who: "alina" as const },
    { name: "Eli Brooks, 6", meta: "Visit 1 of 1 · Pediatric clinic", due: "Nov 1", who: "eli" as const },
  ];

  return (
    <Page width="max-w-[1100px]">
      <header>
        <Title kicker="Friday, October 10">Good afternoon, Jordan</Title>
      </header>
      <section className="overflow-hidden rounded-[20px] border border-line bg-white">
        <div className="flex items-center gap-2 bg-ink px-6 py-3 text-[12.5px] font-semibold tracking-[0.3px] text-white">
          <span className="size-1.5 rounded-full bg-[#8fb0ff]" />
          Up next · due in 7 days
        </div>
        <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-6 p-6">
          <Avatar who="walter" size={96} />
          <div className="min-w-0">
            <div className="font-serif text-[32px] leading-tight font-medium tracking-[-0.6px]">Walter Greene, 72</div>
            <div className="mt-1.5 text-[15px] text-ink-soft">Assess diet and medicines; agree on one change.</div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {["Visit 1 of 2", "Nutrition clinic", "About 15 min"].map((chip) => (
                <span key={chip} className="inline-flex h-6 items-center rounded-md bg-chip px-2 text-[12.5px] text-ink-soft">
                  {chip}
                </span>
              ))}
            </div>
          </div>
          <button
            type="button"
            onClick={() => go("s-brief", { visit: 1 })}
            className="inline-flex h-12 items-center gap-2.5 rounded-xl bg-ink px-[22px] text-[15px] font-semibold text-white hover:bg-indigo"
          >
            Begin visit
            <ArrowRight />
          </button>
        </div>
      </section>

      <div className="grid items-start gap-4 [grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr))]">
        <Card>
          <div className="border-b border-[#eeeff5] px-5 py-4 text-[15px] font-semibold">Assigned</div>
          {assigned.map((item) => (
            <div key={item.name} className="grid grid-cols-[36px_minmax(0,1fr)_auto] items-center gap-3 border-t border-hair px-5 py-3">
              <Avatar who={item.who} size={36} />
              <div>
                <div className="text-[14.5px] font-semibold">{item.name}</div>
                <div className="mt-0.5 text-[12.5px] text-muted">{item.meta}</div>
              </div>
              <span className="text-[12.5px] text-ink-soft">{item.due}</span>
            </div>
          ))}
        </Card>
        <Card>
          <div className="border-b border-[#eeeff5] px-5 py-4 text-[15px] font-semibold">Recent feedback</div>
          <button
            type="button"
            onClick={() => go("s-debrief", { visit: 1 })}
            className="grid w-full grid-cols-[minmax(0,1fr)_auto_16px] items-center gap-3 border-t border-hair px-5 py-3.5 text-left hover:bg-[#fafafd]"
          >
            <div>
              <div className="text-[14.5px] font-semibold">Practice · Dominic Rivera, 22</div>
              <div className="mt-0.5 text-[13px] text-ink-soft">Try next: ask him to say the plan back</div>
            </div>
            <span className="text-[13px] font-semibold tabular-nums">19/28</span>
            <Chevron />
          </button>
        </Card>
      </div>
    </Page>
  );
}
