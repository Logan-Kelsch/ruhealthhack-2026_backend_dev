import type { ReactNode } from "react";
import type { Go } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { Chevron } from "../../components/Icons";
import { BuildTag, Card, CardHead, Page, Title } from "../../components/ui";
import { RECENT_FEEDBACK, STUDENT_VISITS, UP_NEXT } from "../../mock/student";

// Student landing. The next assigned visit is Walter Greene.
export function StudentHome({ go }: { go: Go }) {
  return (
    <Page>
      <Title>Good afternoon, Jordan</Title>

      <section className="overflow-hidden rounded-[14px] border border-line bg-card shadow-[0_10px_30px_-24px_rgba(25,31,92,.35)]">
        <div className="bg-banner flex items-center justify-between gap-4 px-8 py-4">
          <span className="rounded-full bg-white/80 px-4 py-1.5 font-serif text-[17px] text-[#141a55] backdrop-blur-sm">{UP_NEXT.banner}</span>
          <BuildTag kind="planned" feature="D-01 assignments" className="bg-white/85" />
        </div>
        <div className="grid items-center gap-x-8 gap-y-5 px-8 py-7 [grid-template-columns:auto_minmax(0,1fr)_auto] max-md:grid-cols-1">
          <Avatar who={UP_NEXT.who} size={128} />
          <div className="min-w-0">
            <div className="font-serif text-[clamp(32px,3vw,46px)] leading-none tracking-[-1px]">{UP_NEXT.name}</div>
            <div className="mt-3 font-serif text-[21px] text-ink-soft">{UP_NEXT.summary}</div>
            <div className="mt-4 flex flex-wrap gap-2">
              {UP_NEXT.chips.map((chip) => (
                <span key={chip} className="inline-flex h-10 items-center rounded-full bg-indigo-soft px-4 font-serif text-[17px]">
                  {chip}
                </span>
              ))}
            </div>
          </div>
          <button
            type="button"
            onClick={() => go("s-brief", { visit: 1 })}
            className="h-[60px] rounded-xl bg-bright px-10 font-serif text-[24px] text-white shadow-[0_14px_30px_-16px_rgba(74,95,217,.9)] hover:bg-indigo"
          >
            Begin visit →
          </button>
        </div>
      </section>

      <div className="grid items-start gap-5 [grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr))]">
        <Card>
          <CardHead title="Assigned" underline={false} aside={<Count>{STUDENT_VISITS.length} visits</Count>} />
          <div className="px-6 pb-3">
            {STUDENT_VISITS.map((item) => (
              <div key={item.name} className="grid grid-cols-[56px_minmax(0,1fr)_auto] items-center gap-4 border-t border-hair-2 py-3.5">
                <Avatar who={item.who} size={56} />
                <div>
                  <div className="font-serif text-[22px] leading-tight">{item.name}</div>
                  <div className="mt-0.5 font-serif text-[16px] text-ink-soft">{item.meta}</div>
                </div>
                <span className="font-serif text-[17px] text-ink-soft">Due {item.due}</span>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <CardHead title="Recent feedback" underline={false} aside={<BuildTag kind="sample" feature="F-05" />} />
          <div className="px-6 pb-3">
            <button
              type="button"
              onClick={() => go("s-debrief", { visit: 1 })}
              className="grid w-full grid-cols-[minmax(0,1fr)_auto_20px] items-center gap-4 border-t border-hair-2 py-4 text-left hover:bg-raised"
            >
              <div>
                <div className="font-serif text-[22px] leading-tight">{RECENT_FEEDBACK.who}</div>
                <div className="mt-1 font-serif text-[17px] text-indigo">{RECENT_FEEDBACK.next}</div>
              </div>
              <span className="font-serif text-[18px] tabular-nums">{RECENT_FEEDBACK.score.replace("/", " of ")}</span>
              <Chevron className="text-ink-soft" />
            </button>
          </div>
        </Card>
      </div>
    </Page>
  );
}

function Count({ children }: { children: ReactNode }) {
  return <span className="font-serif text-[18px] whitespace-nowrap">{children}</span>;
}
