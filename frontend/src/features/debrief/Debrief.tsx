import { useState } from "react";
import type { Go, VisitNumber } from "../../app/types";
import { ArrowRight } from "../../components/Icons";
import { Page, Title } from "../../components/ui";

const RUBRIC: [string, number][] = [
  ["Opening and purpose", 3],
  ["Rapport, respect, and empathy", 3],
  ["Information gathering", 3],
  ["Listening and response to cues", 2],
  ["Explanation and shared decisions", 2],
  ["Clinical reasoning and synthesis", 3],
  ["Professionalism, safety, and closure", 1],
];

const TABS = [
  ["next", "Next time"],
  ["scores", "Scores"],
  ["transcript", "Transcript"],
] as const;

type TabId = (typeof TABS)[number][0];

const TRANSCRIPT: [string, string, string][] = [
  ["00:04", "Walter", "Morning. The doctor said I should come talk about my salt."],
  ["00:11", "You", "Thanks for coming in, Mr. Greene. I’m Jordan, a dietetics student. What would you like to get out of today?"],
  ["00:20", "Walter", "You look like a kid."],
  ["01:02", "You", "What do you enjoy about dinner club?"],
  ["01:09", "Walter", "Seeing the guys. We do the diner Tuesdays and Fridays."],
  ["03:40", "You", "Are you taking anything for pain right now?"],
  ["03:44", "Walter", "Advil for my back, a couple times a week."],
];

// After the visit: one next step, the 7-domain scores, and the transcript those scores cite.
export function Debrief({ go, visit }: { go: Go; visit: VisitNumber }) {
  const [tab, setTab] = useState<TabId>("next");
  const visitTwo = visit === 2;
  const total = RUBRIC.reduce((sum, [, score]) => sum + score, 0);

  return (
    <Page width="max-w-[1180px]">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <Title kicker={`${visitTwo ? "Visit 2 feedback" : "Visit 1 feedback"} · 14 min · just now`}>Walter Greene, 72</Title>
        <button
          type="button"
          onClick={() => go(visitTwo ? "s-home" : "s-between")}
          className="inline-flex h-11 items-center gap-2.5 rounded-xl bg-ink px-5 text-[14.5px] font-semibold text-white hover:bg-indigo"
        >
          {visitTwo ? "Back to home" : "See what happened next"}
          <ArrowRight />
        </button>
      </header>

      <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]">
        <div className="rounded-2xl border border-line bg-white px-5 py-[18px]">
          <div className="text-[13px] text-ink-soft">Rubric total</div>
          <div className="mt-1.5 flex items-baseline gap-1.5">
            <span className="text-[34px] font-semibold tracking-[-1px]">{total}</span>
            <span className="text-sm text-muted">/ 28</span>
          </div>
        </div>
        <div className="rounded-2xl border border-line border-t-[3px] border-t-ok bg-white px-5 py-[18px]">
          <div className="text-[13px] text-ink-soft">Safety check</div>
          <div className="mt-2 text-[15px] leading-snug font-semibold">Ibuprofen risk found and explained</div>
        </div>
        <div className="rounded-2xl border border-line border-t-[3px] border-t-danger-strong bg-white px-5 py-[18px]">
          <div className="text-[13px] text-ink-soft">Note check</div>
          <div className="mt-2 text-[15px] leading-snug font-semibold">1 claim never said in the visit</div>
          <div className="mt-0.5 text-[13px] text-danger">“Eats breakfast daily”</div>
        </div>
      </div>

      <nav className="flex gap-6 border-b border-[#e3e4ee]">
        {TABS.map(([id, label]) => {
          const on = tab === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`-mb-px border-b-2 px-px pb-3 text-sm ${on ? "border-ink font-semibold text-ink" : "border-transparent font-medium text-muted"}`}
            >
              {label}
            </button>
          );
        })}
      </nav>

      {tab === "next" ? <NextTime /> : null}
      {tab === "scores" ? <Scores /> : null}
      {tab === "transcript" ? <Transcript /> : null}
    </Page>
  );
}

function NextTime() {
  return (
    <div className="flex flex-col gap-3.5">
      <section className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-4 rounded-2xl border border-[#dde1fa] bg-[#eef0fd] px-[22px] py-[18px]">
        <span className="flex size-10 items-center justify-center rounded-xl bg-ink text-white">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" aria-hidden>
            <path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z" />
          </svg>
        </span>
        <div>
          <div className="text-xs font-semibold tracking-[0.6px] text-indigo uppercase">Try this next time</div>
          <div className="mt-0.5 font-serif text-[22px] leading-snug">Ask Walter to say the plan back in his own words.</div>
        </div>
      </section>
      <div className="grid items-start gap-3.5 [grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr))]">
        <NoteList title="What you did well" tone="ok" items={["Followed up on the dinner club", "Asked about over-the-counter pain medicine", "Summarized what matters to him"]} />
        <NoteList title="What to improve" tone="warn" items={["Explain salt in plain words", "Check understanding with teach-back", "Ask about money for groceries"]} />
      </div>
    </div>
  );
}

function NoteList({ title, tone, items }: { title: string; tone: "ok" | "warn"; items: string[] }) {
  const ok = tone === "ok";
  return (
    <section className="overflow-hidden rounded-2xl border border-line bg-white">
      <div className="border-b border-[#eeeff5] px-[18px] py-3.5 text-[15px] font-semibold">{title}</div>
      {items.map((item) => (
        <div key={item} className="grid grid-cols-[20px_1fr] items-start gap-3 border-t border-hair px-[18px] py-3 text-[14.5px] leading-snug">
          <span className={`mt-px flex size-5 items-center justify-center rounded-full text-[11px] font-bold ${ok ? "bg-[#e6f4ec] text-ok" : "bg-[#fdecea] text-danger"}`}>
            {ok ? "✓" : "!"}
          </span>
          {item}
        </div>
      ))}
    </section>
  );
}

function Scores() {
  return (
    <section className="overflow-hidden rounded-2xl border border-line bg-white">
      {RUBRIC.map(([label, score]) => (
        <div key={label} className="grid grid-cols-[minmax(0,1fr)_minmax(120px,220px)_36px] items-center gap-5 border-t border-hair px-5 py-[13px] first:border-t-0">
          <span className="text-[14.5px]">{label}</span>
          <div className="grid grid-cols-4 gap-[3px]">
            {[1, 2, 3, 4].map((pip) => (
              <span
                key={pip}
                className="h-1.5 rounded-full"
                style={{ background: pip <= score ? (score === 1 ? "#e2685f" : "#2b3ab8") : "#eceef5" }}
              />
            ))}
          </div>
          <span className={`text-right text-[14.5px] font-semibold tabular-nums ${score === 1 ? "text-danger" : "text-ink"}`}>
            {score}/4
          </span>
        </div>
      ))}
    </section>
  );
}

function Transcript() {
  return (
    <section className="overflow-hidden rounded-2xl border border-line bg-white">
      {TRANSCRIPT.map(([time, who, text]) => (
        <div key={time} className="grid grid-cols-[52px_64px_minmax(0,1fr)] items-baseline gap-3 border-t border-hair px-5 py-3 first:border-t-0">
          <span className="text-[12.5px] text-muted tabular-nums">{time}</span>
          <span className="text-[13px] font-semibold text-ink-soft">{who}</span>
          <span className="text-[14.5px] leading-snug">{text}</span>
        </div>
      ))}
    </section>
  );
}
