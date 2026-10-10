import type { Go } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { Chevron, PlusIcon } from "../../components/Icons";
import { Card, GhostButton, Page, PrimaryButton, Title } from "../../components/ui";

const REVIEWS = [
  { initials: "14", who: "Student 14", caseName: "Walter Greene, visit 1", when: "Yesterday, 4:12 pm" },
  { initials: "3", who: "Student 3", caseName: "Walter Greene, visit 1", when: "Yesterday, 11:40 am" },
  { initials: "21", who: "Student 21", caseName: "Walter Greene, visit 2", when: "Oct 8" },
];

const ASSIGNMENTS = [
  { name: "Walter Greene · Dietetics cohort A", done: "18/24", pct: "75%", due: "Oct 17" },
  { name: "Alina Reyes · Medicine year 3", done: "10/24", pct: "42%", due: "Oct 24" },
];

// Faculty landing: review queue, assignment progress, and a short case list.
export function FacultyHome({ go }: { go: Go }) {
  const openStudio = () => go("f-studio", { studioTab: "patient" });
  const cases = [
    { name: "Walter Greene, 72", meta: "Published", who: "walter" as const },
    { name: "Alina Reyes, 21", meta: "Published", who: "alina" as const },
    { name: "Eli Brooks, 6", meta: "Published", who: "eli" as const },
  ];

  return (
    <Page>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <Title kicker="Friday, October 10">Good morning, Amara</Title>
        <div className="flex gap-2">
          <GhostButton onClick={() => go("f-import")}>Import patients</GhostButton>
          <PrimaryButton onClick={openStudio}>
            <PlusIcon />
            New case
          </PrimaryButton>
        </div>
      </header>

      <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]">
        <Stat label="Needs your review" value="3" note="visits flagged" accent />
        <Stat label="Visits completed" value="28" note="of 48 assigned" />
        <div className="rounded-2xl border border-line bg-white px-5 py-[18px]">
          <div className="text-[13px] text-ink-soft">Weakest rubric domain</div>
          <div className="mt-2 text-base leading-snug font-semibold">Professionalism, safety, and closure</div>
          <div className="mt-0.5 text-[13px] text-danger">Class average 1.8 of 4</div>
        </div>
      </div>

      <div className="grid items-start gap-4 [grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr))]">
        <Card>
          <div className="flex items-center justify-between px-5 py-4">
            <span className="text-[15px] font-semibold">Needs your review</span>
            <span className="text-[13px] text-muted">Scored 1 of 4 in a domain</span>
          </div>
          {REVIEWS.map((review) => (
            <div key={review.initials} className="grid grid-cols-[36px_minmax(0,1fr)_auto] items-center gap-3.5 border-t border-hair px-5 py-3.5">
              <div className="flex size-9 items-center justify-center rounded-full bg-[#eef0fd] text-xs font-bold text-indigo">
                {review.initials}
              </div>
              <div className="min-w-0">
                <div className="text-[14.5px] font-semibold">
                  {review.who} <span className="font-normal text-muted">· {review.caseName}</span>
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-2">
                  <span className="inline-flex h-[22px] items-center rounded-md bg-[#fdecea] px-2 text-xs font-semibold text-danger">
                    Safety & closure · 1/4
                  </span>
                  <span className="text-[12.5px] text-muted">{review.when}</span>
                </div>
              </div>
              <button type="button" className="h-[34px] rounded-[9px] border border-line-2 bg-white px-3.5 text-[13.5px] font-medium hover:bg-wash">
                Review
              </button>
            </div>
          ))}
        </Card>

        <div className="flex flex-col gap-4">
          <Card>
            <div className="flex items-center justify-between border-b border-[#eeeff5] px-5 py-4">
              <span className="text-[15px] font-semibold">Active assignments</span>
              <span className="text-[13px] text-muted">2</span>
            </div>
            {ASSIGNMENTS.map((item) => (
              <div key={item.name} className="flex flex-col gap-2 border-t border-hair px-5 py-3.5">
                <div className="flex justify-between gap-3">
                  <span className="text-[14.5px] font-medium">{item.name}</span>
                  <span className="text-[13px] whitespace-nowrap text-muted">Due {item.due}</span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#eceef5]">
                    <div className="h-full rounded-full bg-indigo" style={{ width: item.pct }} />
                  </div>
                  <span className="text-[13px] text-ink-soft tabular-nums">{item.done}</span>
                </div>
              </div>
            ))}
          </Card>

          <Card>
            <div className="flex items-center justify-between border-b border-[#eeeff5] px-5 py-4">
              <span className="text-[15px] font-semibold">Your cases</span>
              <button type="button" onClick={() => go("f-cases")} className="text-[13px] font-medium text-indigo hover:underline">
                View all
              </button>
            </div>
            {cases.map((item) => (
              <button
                key={item.name}
                type="button"
                onClick={openStudio}
                className="grid w-full grid-cols-[32px_minmax(0,1fr)_auto_16px] items-center gap-3 border-t border-hair px-5 py-[11px] text-left hover:bg-[#fafafd]"
              >
                <Avatar who={item.who} size={32} />
                <span className="text-[14.5px] font-medium">{item.name}</span>
                <span className="text-[12.5px] text-muted">{item.meta}</span>
                <Chevron />
              </button>
            ))}
          </Card>
        </div>
      </div>
    </Page>
  );
}

function Stat({ label, value, note, accent }: { label: string; value: string; note: string; accent?: boolean }) {
  return (
    <div className={`rounded-2xl border border-line bg-white px-5 py-[18px] ${accent ? "border-t-[3px] border-t-[#d4453c]" : ""}`}>
      <div className="text-[13px] text-ink-soft">{label}</div>
      <div className="mt-1.5 flex items-baseline gap-2">
        <span className="text-[34px] font-semibold tracking-[-1px]">{value}</span>
        <span className="text-[13px] text-muted">{note}</span>
      </div>
    </div>
  );
}
