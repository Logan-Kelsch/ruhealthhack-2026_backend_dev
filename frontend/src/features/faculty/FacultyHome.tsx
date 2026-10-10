import type { Go } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { Chevron, PlusIcon } from "../../components/Icons";
import { Badge, Card, CardHead, GhostButton, Page, PageHeader, PrimaryButton, StatCard } from "../../components/ui";
import { ASSIGNMENTS, FACULTY_CASES, FACULTY_STATS, REVIEW_QUEUE, WEAKEST_DOMAIN } from "../../mock/faculty";

// Faculty landing: review queue, assignment progress, and a short case list.
export function FacultyHome({ go }: { go: Go }) {
  const openStudio = () => go("f-studio", { studioTab: "patient" });

  return (
    <Page>
      <PageHeader kicker="Friday, October 10" title="Good morning, Amara">
        <div className="flex gap-2">
          <GhostButton onClick={() => go("f-import")}>Import sample set</GhostButton>
          <PrimaryButton onClick={openStudio}>
            <PlusIcon />
            New case
          </PrimaryButton>
        </div>
      </PageHeader>

      <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]">
        {FACULTY_STATS.map((stat) => (
          <StatCard key={stat.label} label={stat.label} accent={stat.accent}>
            <div className="mt-1.5 flex items-baseline gap-2">
              <span className="text-[34px] font-semibold tracking-[-1px]">{stat.value}</span>
              <span className="text-[13px] text-muted">{stat.note}</span>
            </div>
          </StatCard>
        ))}
        <StatCard label={WEAKEST_DOMAIN.label}>
          <div className="mt-2 text-base leading-snug font-semibold">{WEAKEST_DOMAIN.title}</div>
          <div className="mt-0.5 text-[13px] text-danger">{WEAKEST_DOMAIN.note}</div>
        </StatCard>
      </div>

      <div className="grid items-start gap-4 [grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr))]">
        <Card>
          <CardHead title="Needs your review" aside={<span className="text-[13px] text-muted">Scored 1 of 4 in a domain</span>} />
          {REVIEW_QUEUE.map((review) => (
            <div key={review.initials} className="grid grid-cols-[36px_minmax(0,1fr)_auto] items-center gap-3.5 border-t border-hair px-5 py-3.5 first:border-t-0">
              <div className="flex size-9 items-center justify-center rounded-full bg-indigo-soft text-xs font-bold text-indigo">
                {review.initials}
              </div>
              <div className="min-w-0">
                <div className="text-[14.5px] font-semibold">
                  {review.who} <span className="font-normal text-muted">· {review.caseName}</span>
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-2">
                  <Badge tone="danger">Safety & closure · 1/4</Badge>
                  <span className="text-[12.5px] text-muted">{review.when}</span>
                </div>
              </div>
              <GhostButton size="sm">Review</GhostButton>
            </div>
          ))}
        </Card>

        <div className="flex flex-col gap-4">
          <Card>
            <CardHead title="Active assignments" aside={<span className="text-[13px] text-muted">2</span>} />
            {ASSIGNMENTS.map((item) => (
              <div key={item.name} className="flex flex-col gap-2 border-t border-hair px-5 py-3.5 first:border-t-0">
                <div className="flex justify-between gap-3">
                  <span className="text-[14.5px] font-medium">{item.name}</span>
                  <span className="text-[13px] whitespace-nowrap text-muted">Due {item.due}</span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-track">
                    <div className="h-full rounded-full bg-indigo" style={{ width: item.pct }} />
                  </div>
                  <span className="text-[13px] text-ink-soft tabular-nums">{item.done}</span>
                </div>
              </div>
            ))}
          </Card>

          <Card>
            <CardHead
              title="Your cases"
              aside={
                <button type="button" onClick={() => go("f-cases")} className="text-[13px] font-medium text-indigo hover:underline">
                  View all
                </button>
              }
            />
            {FACULTY_CASES.map((item) => (
              <button
                key={item.name}
                type="button"
                onClick={openStudio}
                className="grid w-full grid-cols-[32px_minmax(0,1fr)_auto_16px] items-center gap-3 border-t border-hair px-5 py-[11px] text-left first:border-t-0 hover:bg-raised"
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
