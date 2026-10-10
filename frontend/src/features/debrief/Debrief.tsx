import { useState, type ReactNode } from "react";
import type { Go, VisitNumber } from "../../app/types";
import { ArrowRight } from "../../components/Icons";
import { BigMark, BuildTag, Page, PrimaryButton, TabNav, type TabItem } from "../../components/ui";
import { RUBRIC_DOMAINS } from "../../lib/rubric";
import {
  DEBRIEF_IMPROVEMENTS,
  DEBRIEF_NEXT_STEP,
  DEBRIEF_NOTE_CHECK,
  DEBRIEF_SAFETY_CHECK,
  DEBRIEF_STRENGTHS,
  DEBRIEF_TRANSCRIPT,
  DEBRIEF_TRUST,
  RUBRIC_SCORES,
} from "../../mock/debrief";
import { DocIcon } from "../faculty/ImportPatients";

type TabId = "next" | "scores" | "trust" | "transcript";

const TABS: TabItem<TabId>[] = [
  { id: "next", label: "Next time" },
  { id: "scores", label: "Scores" },
  { id: "trust", label: "Trust" },
  { id: "transcript", label: "Transcript" },
];

// After the visit: one next step, the 7-domain scores, how trust moved, and the transcript those cite.
export function Debrief({ go, visit }: { go: Go; visit: VisitNumber }) {
  const [tab, setTab] = useState<TabId>("next");
  const visitTwo = visit === 2;

  return (
    <Page>
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-line-3">
        <div>
          <h1 className="m-0 font-serif text-[clamp(40px,4vw,58px)] leading-none font-normal tracking-[-1.2px]">Walter Greene, 72</h1>
          <div className="mt-4 -mb-px">
            <TabNav items={TABS} active={tab} onChange={setTab} />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-4 pb-3">
          <BuildTag kind="sample" feature="F-01, F-05" />
          <PrimaryButton size="lg" onClick={() => go(visitTwo ? "s-home" : "s-between")}>
            {visitTwo ? "Back to home" : "See what happened next"}
            <ArrowRight />
          </PrimaryButton>
        </div>
      </header>

      {tab === "next" ? <NextTime /> : null}
      {tab === "scores" ? <Scores /> : null}
      {tab === "trust" ? <Trust /> : null}
      {tab === "transcript" ? <Transcript /> : null}
    </Page>
  );
}

function Box({ title, children, className = "" }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-[14px] border border-line bg-card px-6 pt-5 pb-4 ${className}`}>
      <h2 className="m-0 font-serif text-[clamp(26px,2.2vw,34px)] font-normal tracking-[-0.5px]">{title}</h2>
      {children}
    </section>
  );
}

function NextTime() {
  return (
    <div className="flex flex-col gap-5">
      <div className="grid items-stretch gap-5 [grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr))]">
        <NoteList title="What you did well" ok items={DEBRIEF_STRENGTHS} />
        <NoteList title="What to improve" ok={false} items={DEBRIEF_IMPROVEMENTS} />
        <Box title="Next attempt suggestion">
          <div className="mt-4 flex items-center gap-5 rounded-xl bg-indigo-soft px-5 py-5">
            <span className="flex size-[64px] shrink-0 items-center justify-center rounded-full bg-indigo-soft-2 text-indigo">
              <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" aria-hidden>
                <path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z" />
              </svg>
            </span>
            <span className="font-serif text-[21px] leading-snug">{DEBRIEF_NEXT_STEP}</span>
          </div>
        </Box>
      </div>
      <div className="grid items-stretch gap-5 [grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr))]">
        <Box title="Safety check">
          <div className="mt-4 flex items-center gap-6 rounded-xl bg-ok-soft/70 px-5 py-5">
            <span className="flex size-[64px] shrink-0 items-center justify-center rounded-full bg-ok-soft">
              <span className="flex size-10 items-center justify-center rounded-full bg-ok text-[22px] text-white">✓</span>
            </span>
            <span className="font-serif text-[21px] leading-snug">{DEBRIEF_SAFETY_CHECK}</span>
          </div>
        </Box>
        <Box title="Note check">
          <div className="mt-4 flex items-center gap-6 rounded-xl bg-danger-soft/70 px-5 py-5">
            <span className="flex size-[64px] shrink-0 items-center justify-center rounded-full bg-danger-soft text-danger">
              <DocIcon size={30} />
            </span>
            <span className="font-serif text-[21px] leading-snug">
              {DEBRIEF_NOTE_CHECK.title}
              <br />
              {DEBRIEF_NOTE_CHECK.quote}
            </span>
          </div>
        </Box>
      </div>
    </div>
  );
}

function NoteList({ title, ok, items }: { title: string; ok: boolean; items: string[] }) {
  return (
    <Box title={title}>
      <div className="mt-3">
        {items.map((item) => (
          <div key={item} className="grid grid-cols-[56px_1fr] items-center gap-5 border-t border-hair-2 py-3.5">
            <BigMark tone={ok ? "ok" : "danger"} />
            <span className="font-serif text-[20px] leading-snug">{item}</span>
          </div>
        ))}
      </div>
    </Box>
  );
}

function Scores() {
  const total = RUBRIC_SCORES.reduce((sum, score) => sum + score, 0);
  const review = RUBRIC_SCORES[5] === 1 || RUBRIC_SCORES[6] === 1;
  return (
    <Box title="Official 7-domain rubric">
      <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="font-serif text-[44px] leading-none tabular-nums">{total}</span>
        <span className="font-serif text-[20px] text-ink-soft">of {RUBRIC_DOMAINS.length * 4}</span>
        <span className="font-sans text-[14px] text-muted">A discussion aid, not a pass/fail grade.</span>
        {review ? <span className="rounded-full bg-danger-soft px-3 py-1 font-sans text-[13px] text-danger">Flagged for faculty review</span> : null}
      </div>
      <div className="mt-4">
        {RUBRIC_DOMAINS.map((label, index) => {
          const score = RUBRIC_SCORES[index];
          return (
            <div key={label} className="grid grid-cols-[48px_minmax(0,1fr)_minmax(120px,240px)_52px] items-center gap-5 border-t border-hair-2 py-3">
              <span className="flex size-12 items-center justify-center rounded-full bg-indigo-soft font-serif text-[20px]">{index + 1}</span>
              <span className="font-serif text-[19px]">{label}</span>
              <div className="grid grid-cols-4 gap-1">
                {[1, 2, 3, 4].map((pip) => (
                  <span key={pip} className="h-2 rounded-full" style={{ background: pip <= score ? (score === 1 ? "var(--color-danger-bright)" : "var(--color-indigo)") : "var(--color-track)" }} />
                ))}
              </div>
              <span className={`text-right font-serif text-[19px] tabular-nums ${score === 1 ? "text-danger" : ""}`}>{score} of 4</span>
            </div>
          );
        })}
      </div>
    </Box>
  );
}

// Trust stays hidden during the visit (PRD E-12) and is shown here, one quoted span per change.
function Trust() {
  const W = 760;
  const H = 180;
  const end = 260;
  let level = 2;
  const points = [{ x: 0, y: level }, ...DEBRIEF_TRUST.map((event) => ({ x: event.seconds, y: (level += event.change) }))];
  const x = (seconds: number) => 30 + (seconds / end) * (W - 60);
  const y = (value: number) => H - 24 - (value / 5) * (H - 48);
  const line = points.map((point, index) => `${index ? "L" : "M"}${x(point.x)} ${y(point.y)}`).join(" ") + ` L${x(end)} ${y(level)}`;

  return (
    <Box title="How Walter’s trust moved">
      <div className="mt-1 flex items-center gap-3">
        <BuildTag kind="sample" feature="F-04" />
        <span className="font-sans text-[14px] text-muted">Hidden during the visit. Each change quotes what caused it.</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-4 w-full" aria-hidden>
        <line x1="30" x2={W - 30} y1={H - 24} y2={H - 24} stroke="var(--color-line)" />
        <path d={line} fill="none" stroke="var(--color-indigo)" strokeWidth="3" strokeLinejoin="round" />
        {DEBRIEF_TRUST.map((event, index) => (
          <circle key={event.time} cx={x(event.seconds)} cy={y(points[index + 1].y)} r="7" fill={event.change > 0 ? "var(--color-ok)" : "var(--color-danger-bright)"} stroke="white" strokeWidth="2.5" />
        ))}
      </svg>
      <div className="mt-2">
        {DEBRIEF_TRUST.map((event) => (
          <div key={event.time} className="grid grid-cols-[64px_44px_minmax(0,1fr)] items-baseline gap-4 border-t border-hair-2 py-3">
            <span className="font-sans text-[14px] text-muted tabular-nums">{event.time}</span>
            <span className={`font-serif text-[19px] ${event.change > 0 ? "text-ok" : "text-danger"}`}>{event.change > 0 ? "+1" : "−1"}</span>
            <span>
              <span className="block font-serif text-[19px]">{event.label}</span>
              <span className="block font-serif text-[17px] text-ink-soft italic">“{event.quote}”</span>
            </span>
          </div>
        ))}
      </div>
    </Box>
  );
}

function Transcript() {
  return (
    <Box title="Transcript">
      <div className="mt-3">
        {DEBRIEF_TRANSCRIPT.map(([time, who, text]) => (
          <div key={time} className="grid grid-cols-[64px_84px_minmax(0,1fr)] items-baseline gap-4 border-t border-hair-2 py-3">
            <span className="font-sans text-[14px] text-muted tabular-nums">{time}</span>
            <span className="font-serif text-[17px] text-ink-soft">{who === "You" ? "Student" : who}</span>
            <span className="font-serif text-[19px] leading-snug">{text}</span>
          </div>
        ))}
      </div>
    </Box>
  );
}
