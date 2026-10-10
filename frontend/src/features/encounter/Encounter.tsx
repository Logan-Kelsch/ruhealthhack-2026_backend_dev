import { useEffect, useRef, useState } from "react";
import type { Go, VisitNumber } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { Badge, CardHead, GhostButton, Wordmark } from "../../components/ui";
import {
  WALTER_ENCOUNTER_VITALS,
  WALTER_EXAMS,
  WALTER_GOAL,
  WALTER_MEDS,
  WALTER_ORDERS,
  WALTER_SCRIPT,
} from "../../mock/walter";

// Hands-free encounter. Lines appear on a timer. There is no text box.
// Mute pauses the clock and the script. End visit opens the debrief.
export function Encounter({ go, visit }: { go: Go; visit: VisitNumber }) {
  const [seconds, setSeconds] = useState(0);
  const [muted, setMuted] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [exams, setExams] = useState<number[]>([0]);
  const [ordered, setOrdered] = useState<Record<string, boolean>>({});
  const mutedRef = useRef(muted);
  mutedRef.current = muted;

  useEffect(() => {
    // The interval stays up for the whole visit. Mute is read from a ref so pausing does not reset the timer.
    const timer = window.setInterval(() => {
      if (!mutedRef.current) setSeconds((value) => value + 1);
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  const visitTwo = visit === 2;
  const shown = Math.min(WALTER_SCRIPT.length, 2 + Math.floor(seconds / 4));
  const lines = WALTER_SCRIPT.slice(0, shown);
  const lastSpeaker = WALTER_SCRIPT[shown - 1]?.[0];
  const walterTalking = !muted && shown < WALTER_SCRIPT.length && lastSpeaker === "You";
  // The Ibuprofen row lights up once the script line that mentions it has played.
  const advilLine = WALTER_SCRIPT.findIndex(([, text]) => text.includes("Advil"));
  const advilMentioned = shown > advilLine;
  // The prototype clock starts a little over a minute in, matching the recorded demo.
  const clockSeconds = seconds + 72;
  const clock = `${String(Math.floor(clockSeconds / 60)).padStart(2, "0")}:${String(clockSeconds % 60).padStart(2, "0")}`;
  const goal = WALTER_GOAL[visit];
  const vitals = WALTER_ENCOUNTER_VITALS[visit];

  return (
    <div className="flex min-h-full flex-col">
      <div className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-4 border-b border-ink/7 bg-card/70 px-6 py-3.5 backdrop-blur-xl">
        <div className="flex items-center gap-4">
          <Wordmark size="sm" />
          <span className="h-[22px] w-px bg-line-3" />
          <span className="text-sm font-semibold">{visitTwo ? "Visit 2 of 2" : "Visit 1 of 2"}</span>
          <span className="text-sm text-ink-soft tabular-nums">
            {clock} <span className="text-faint">/ 15:00</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setMuted((value) => !value)}
            className="inline-flex h-[38px] items-center gap-2 rounded-[10px] border border-line-2 bg-card px-3.5 text-[13.5px] font-medium"
          >
            <span className={`size-2 rounded-full ${muted ? "bg-inactive" : "rnd-blink bg-indigo"}`} />
            {muted ? "Muted" : "Listening"}
          </button>
          <button
            type="button"
            onClick={() => go("s-debrief", { visit })}
            className="h-[38px] rounded-[10px] bg-danger-strong px-4 text-[13.5px] font-semibold text-white hover:bg-[#a92f27]"
          >
            End visit
          </button>
        </div>
      </div>

      <div className="mx-auto grid w-full max-w-[1440px] flex-1 items-start gap-4 px-6 py-5 [grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr))]">
        <aside className="flex flex-col gap-3">
          <section className="rounded-2xl bg-panel px-[18px] py-4 text-white">
            <div className="text-[11.5px] font-semibold tracking-[0.6px] text-indigo-on-ink uppercase">Goal</div>
            <div className="mt-1 font-serif text-[19px] leading-snug">{goal}</div>
          </section>
          <section className="rounded-2xl border border-line bg-card px-[18px] py-3.5">
            <div className="text-[12.5px] text-muted">From primary care</div>
            <div className="mt-1 text-sm leading-snug">Heart failure, kidney disease and type 2 diabetes. Review sodium and diet.</div>
          </section>
          <section className="overflow-hidden rounded-2xl border border-line bg-card">
            <CardHead
              title="Exam log"
              className="px-[18px] py-3"
              aside={
                <GhostButton size="sm" onClick={() => setMenuOpen((open) => !open)}>
                  + Examine
                </GhostButton>
              }
            />
            {menuOpen ? (
              <div className="flex flex-col border-b border-hair-2 bg-raised">
                {WALTER_EXAMS.map((exam, index) =>
                  exams.includes(index) ? null : (
                    <button
                      key={exam.label}
                      type="button"
                      onClick={() => {
                        setExams([...exams, index]);
                        setMenuOpen(false);
                      }}
                      className="px-[18px] py-2.5 text-left text-[13.5px] text-indigo hover:bg-indigo-soft"
                    >
                      {exam.label}
                    </button>
                  ),
                )}
              </div>
            ) : null}
            {exams.map((index) => (
              <div key={WALTER_EXAMS[index].text} className="flex items-center gap-2.5 border-t border-hair px-[18px] py-[11px] text-sm first:border-t-0">
                <span className="size-1.5 rounded-full" style={{ background: WALTER_EXAMS[index].flag ? "#e08a3c" : "var(--color-inactive)" }} />
                {WALTER_EXAMS[index].text}
              </div>
            ))}
          </section>
        </aside>

        <section className="flex min-w-0 flex-col overflow-hidden rounded-2xl border border-line bg-card">
          <div className="flex items-center gap-3.5 border-b border-hair-2 px-5 py-4">
            <div className="relative size-[52px] shrink-0">
              <Avatar who="walter" size={52} />
              <span
                className="absolute -right-px -bottom-px size-3.5 rounded-full border-2 border-card"
                style={{ background: walterTalking ? "var(--color-indigo)" : "var(--color-line-4)" }}
              />
            </div>
            <div>
              <div className="font-serif text-2xl leading-none font-medium tracking-[-0.4px]">Walter Greene, 72</div>
              <div className="mt-0.5 text-[12.5px] text-muted">
                {walterTalking ? "Responding…" : muted ? "Paused while muted" : "Listening to you"}
              </div>
            </div>
          </div>
          <div className="flex flex-col gap-3 px-5 py-4">
            {lines.map(([who, text]) => {
              const student = who === "You";
              return (
                <div key={text} className={`flex flex-col gap-0.5 ${student ? "items-end" : "items-start"}`}>
                  <span className="px-1 text-[11.5px] font-semibold text-muted">{who}</span>
                  <div className={`max-w-[88%] rounded-[14px] px-3.5 py-2.5 text-[15px] leading-snug ${student ? "bg-panel text-white" : "bg-segment text-ink"}`}>
                    {text}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <aside className="flex flex-col gap-3">
          <section className="overflow-hidden rounded-2xl border border-line bg-card">
            <CardHead title="Vitals" underline={false} className="px-[18px] py-3" />
            <div className="grid grid-cols-3">
              {vitals.map((vital) => (
                <div key={vital.k} className="border-t border-r border-hair px-3.5 py-2.5">
                  <div className="text-[11.5px] text-muted">{vital.k}</div>
                  <div className={`mt-0.5 text-base font-semibold tabular-nums ${vital.tone === "danger" ? "text-danger" : "text-ink"}`}>
                    {vital.v}
                  </div>
                </div>
              ))}
            </div>
          </section>
          <section className="overflow-hidden rounded-2xl border border-line bg-card">
            <CardHead title="Medications" className="px-[18px] py-3" />
            {WALTER_MEDS.map((med) => {
              const mentioned = advilMentioned && med.id === "ibuprofen";
              return (
                <div key={med.name} className={`flex items-center justify-between gap-2 border-t border-hair px-[18px] py-[11px] first:border-t-0 ${mentioned ? "bg-warn-wash" : "bg-card"}`}>
                  <div>
                    <div className="text-sm font-semibold">{med.name}</div>
                    <div className="text-[12.5px] text-muted">{med.sub}</div>
                  </div>
                  {mentioned ? <Badge tone="warn">Mentioned</Badge> : null}
                </div>
              );
            })}
          </section>
          <section className="overflow-hidden rounded-2xl border border-line bg-card">
            <CardHead title="Orders" className="px-[18px] py-3" />
            {WALTER_ORDERS.map(({ id, name }) => {
              const ready = Boolean(ordered[id]);
              return (
                <div key={id} className="flex items-center gap-3 border-t border-hair px-[18px] py-2.5 first:border-t-0">
                  <div className={`h-8 w-11 shrink-0 rounded-md ${ready ? (id === "ecg" ? "bg-[#e7ebf8]" : "bg-[#1c2430]") : "bg-segment"}`} />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">{name}</div>
                    <div className={`text-xs ${ready ? "text-ok" : "text-muted"}`}>{ready ? "Result available" : "Not ordered"}</div>
                  </div>
                  {ready ? null : (
                    <GhostButton size="sm" onClick={() => setOrdered({ ...ordered, [id]: true })}>
                      Order
                    </GhostButton>
                  )}
                </div>
              );
            })}
          </section>
        </aside>
      </div>
    </div>
  );
}
