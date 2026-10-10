import type { ReactNode } from "react";
import type { Go } from "../../app/types";
import { Chevron } from "../../components/Icons";
import { BigMark, BuildTag, Card, CardHead, Page, SoftButton, Title } from "../../components/ui";
import { ASSIGNMENTS, FACULTY_CASES, REVIEW_QUEUE } from "../../mock/faculty";

// Faculty landing: visits flagged for review, assignment progress, and the case list.
export function FacultyHome({ go }: { go: Go }) {
  return (
    <Page>
      <Title>Good morning</Title>

      <div className="grid items-start gap-5 [grid-template-columns:repeat(auto-fit,minmax(min(100%,460px),1fr))]">
        <Card>
          <CardHead
            title="Needs your review"
            underline={false}
            aside={<Aside tag={<BuildTag kind="sample" feature="F-01" />}>{REVIEW_QUEUE.length} visits</Aside>}
          />
          <div className="px-6 pb-3">
            {REVIEW_QUEUE.map((review) => (
              <div key={review.initials} className="grid grid-cols-[56px_minmax(0,1fr)_auto] items-center gap-5 border-t border-hair-2 py-5 first:border-t-0">
                <BigMark tone="danger" />
                <div className="min-w-0">
                  <div className="font-serif text-[clamp(20px,1.8vw,28px)] leading-tight tracking-[-0.4px]">
                    {review.who} · Walter Greene, 72
                  </div>
                  <div className="mt-1 font-serif text-[17px] leading-snug text-indigo">
                    Professionalism, safety, and closure scored 1
                  </div>
                </div>
                <SoftButton className="w-[150px] justify-center">Review</SoftButton>
              </div>
            ))}
          </div>
        </Card>

        <div className="flex flex-col gap-5">
          <Card>
            <CardHead
              title="Active assignments"
              underline={false}
              aside={<Aside tag={<BuildTag kind="planned" feature="D-01" />}>{ASSIGNMENTS.length} assignments</Aside>}
            />
            <div className="px-6 pb-5">
              {ASSIGNMENTS.map((item, index) => (
                <div key={item.name} className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-x-6 border-t border-hair-2 py-3.5 first:border-t-0">
                  <div className="font-serif text-[19px]">{item.name.replace(" · ", ", ")}</div>
                  <div className="row-span-2 font-serif text-[18px] whitespace-nowrap text-ink">{item.done.replace("/", " of ")} done</div>
                  <div className="mt-2 h-3 overflow-hidden rounded-full bg-track">
                    <div className="h-full rounded-full" style={{ width: item.pct, background: index === 0 ? "#6170dc" : "#8aa2f0" }} />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <CardHead
              title="Your cases"
              underline={false}
              aside={<Aside tag={<BuildTag kind="sample" feature="S-15" />}>{FACULTY_CASES.length} cases</Aside>}
            />
            <div className="px-6 pb-3">
              {FACULTY_CASES.map((item) => (
                <button
                  key={item.name}
                  type="button"
                  onClick={() => go("f-studio", { studioTab: "patient" })}
                  className="grid w-full grid-cols-[52px_minmax(0,1fr)_20px] items-center gap-4 border-t border-hair-2 py-3 text-left first:border-t-0 hover:bg-raised"
                >
                  <PersonDot />
                  <span className="font-serif text-[22px] tracking-[-0.3px]">{item.name}</span>
                  <Chevron className="text-ink-soft" />
                </button>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </Page>
  );
}

function Aside({ tag, children }: { tag: ReactNode; children: ReactNode }) {
  return (
    <span className="flex items-center gap-3">
      {tag}
      <span className="font-serif text-[18px] whitespace-nowrap text-ink">{children}</span>
    </span>
  );
}

export function PersonDot({ size = 52 }: { size?: number }) {
  return (
    <span className="flex shrink-0 items-center justify-center rounded-full bg-indigo-soft text-indigo" style={{ width: size, height: size }}>
      <svg width={size * 0.46} height={size * 0.46} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
        <circle cx="12" cy="8" r="4.2" />
        <path d="M3.8 21c0-4.6 3.7-7.6 8.2-7.6s8.2 3 8.2 7.6z" />
      </svg>
    </span>
  );
}
