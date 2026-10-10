import { useEffect, useRef, useState, type ReactNode } from "react";
import type { Go, VisitNumber } from "../../app/types";
import { PatientCall } from "../../components/PatientCall";
import { BuildTag, Wordmark } from "../../components/ui";
import {
  WALTER_ENCOUNTER_VITALS,
  WALTER_EXAMS,
  WALTER_GOAL,
  WALTER_MEDS,
  WALTER_ORDERS,
  WALTER_SCRIPT,
} from "../../mock/walter";

const VITAL_UNITS: Record<string, string> = { BP: " mmHg", HR: " bpm", RR: " /min", Temp: "C" };

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
  const transcript = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // The interval stays up for the whole visit. Mute is read from a ref so pausing does not reset the timer.
    const timer = window.setInterval(() => {
      if (!mutedRef.current) setSeconds((value) => value + 1);
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  // The first lines wait for the call-connect animation to finish.
  const shown = Math.min(WALTER_SCRIPT.length, seconds < 3 ? 0 : 1 + Math.floor((seconds - 3) / 4));
  const lines = WALTER_SCRIPT.slice(0, shown);

  useEffect(() => {
    transcript.current?.scrollTo({ top: transcript.current.scrollHeight, behavior: "smooth" });
  }, [shown]);

  // Walter "speaks" for the first two seconds after one of his lines appears.
  const walterTalking = !muted && shown > 0 && WALTER_SCRIPT[shown - 1][0] === "Walter" && (seconds - 3) % 4 < 2;
  // The Ibuprofen row lights up once the script line that mentions it has played.
  const advilLine = WALTER_SCRIPT.findIndex(([, text]) => text.includes("Advil"));
  const advilMentioned = shown > advilLine;
  const clock = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  const vitals = WALTER_ENCOUNTER_VITALS[visit];

  return (
    <div className="relative flex h-full min-h-[700px] flex-col overflow-hidden text-ink">
      <div className="bg-world absolute inset-0" />

      <header className="relative flex items-center justify-between gap-4 px-[clamp(24px,3vw,48px)] pt-5 pb-3">
        <div className="flex items-center gap-5">
          <Wordmark size="md" />
          <span className="rounded-full bg-white/75 px-4 py-1.5 font-serif text-[17px] backdrop-blur-sm">
            {visit === 2 ? "Visit 2 of 2" : "Visit 1 of 2"}
          </span>
        </div>
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => setMuted((value) => !value)}
            aria-pressed={muted}
            className="inline-flex h-[54px] items-center gap-3 rounded-full border border-indigo-line/50 bg-white/85 px-6 font-serif text-[20px] backdrop-blur-sm hover:bg-white"
          >
            <span className={`size-3.5 rounded-full ${muted ? "bg-inactive" : "rnd-blink bg-bright"}`} />
            {muted ? "Muted" : "Listening"}
          </button>
          <button
            type="button"
            onClick={() => go("s-debrief", { visit })}
            className="h-[54px] rounded-full bg-danger-strong px-8 font-serif text-[20px] text-white shadow-[0_10px_24px_-14px_rgba(217,70,62,.9)] hover:bg-[#c23a33]"
          >
            End visit
          </button>
        </div>
      </header>

      <div className="relative grid min-h-0 flex-1 gap-[clamp(16px,2.4vw,40px)] px-[clamp(24px,3vw,48px)] pt-2 pb-6 [grid-template-columns:minmax(280px,0.9fr)_minmax(0,1.45fr)_minmax(280px,0.9fr)] max-xl:[grid-template-columns:minmax(260px,1fr)_minmax(0,1.5fr)]">
        <Glass className="flex flex-col gap-5 overflow-auto">
          <div className="rounded-xl bg-indigo-soft px-5 py-4 font-serif text-[20px] leading-snug">{WALTER_GOAL[visit]}</div>
          <div className="border-t border-hair-2 pt-4">
            <h3 className="m-0 font-serif text-[23px] leading-tight font-normal">From primary care: nutrition counseling</h3>
            <div className="mt-3 rounded-xl bg-wash px-5 py-3.5">
              <div className="font-serif text-[19px]">PCP (primary care provider)</div>
              <div className="mt-1 font-serif text-[16.5px] leading-snug text-ink-soft">Heart failure, kidney disease and type 2 diabetes. Review sodium and diet.</div>
            </div>
          </div>
          <div className="border-t border-hair-2 pt-4">
            <div className="flex items-center justify-between">
              <h3 className="m-0 font-serif text-[26px] font-normal">Exam log</h3>
              <button
                type="button"
                onClick={() => setMenuOpen((open) => !open)}
                aria-expanded={menuOpen}
                aria-label="Examine"
                className="flex size-10 items-center justify-center rounded-full bg-indigo-soft text-[22px] hover:bg-indigo-soft-2"
              >
                +
              </button>
            </div>
            <p className="mt-1 mb-0 font-sans text-[13px] text-muted">Say what you are examining, or pick it here.</p>
            {menuOpen ? (
              <div className="mt-3 flex flex-col overflow-hidden rounded-xl border border-line bg-card">
                {WALTER_EXAMS.map((exam, index) =>
                  exams.includes(index) ? null : (
                    <button
                      key={exam.label}
                      type="button"
                      onClick={() => {
                        setExams([...exams, index]);
                        setMenuOpen(false);
                      }}
                      className="border-t border-hair px-4 py-2.5 text-left font-serif text-[17px] text-indigo first:border-t-0 hover:bg-indigo-soft"
                    >
                      {exam.label}
                    </button>
                  ),
                )}
              </div>
            ) : null}
            <div className="mt-3 flex flex-col gap-2.5">
              {exams.map((index) => (
                <div
                  key={WALTER_EXAMS[index].text}
                  className={`rounded-xl px-5 py-3.5 font-serif text-[18px] ${WALTER_EXAMS[index].flag ? "border-l-4 border-apricot bg-warn-wash" : "bg-wash"}`}
                >
                  {WALTER_EXAMS[index].text}
                </div>
              ))}
            </div>
          </div>
        </Glass>

        <div className="flex min-h-0 min-w-0 flex-col items-center">
          <div className="w-full max-w-[720px]">
            <PatientCall speaking={walterTalking} muted={muted} clock={clock} />
          </div>
          <h2 className="mt-4 mb-2 font-serif text-[clamp(30px,2.6vw,42px)] leading-none font-normal tracking-[-0.8px]">Walter Greene, 72</h2>
          <div ref={transcript} className="flex min-h-0 w-full max-w-[600px] flex-1 flex-col gap-2 overflow-auto px-1 pb-2 [mask-image:linear-gradient(transparent,black_24px)]">
            {lines.map(([who, text]) => {
              const student = who === "You";
              return (
                <div key={text} className="rnd-line flex flex-col items-start gap-1 pt-2">
                  <span className="px-3 font-serif text-[16px] text-ink-soft">{student ? "Student" : "Walter"}</span>
                  <div className={`max-w-[92%] rounded-xl px-5 py-2.5 font-serif text-[19px] leading-snug ${student ? "bg-bubble-student" : "bg-bubble-patient"}`}>{text}</div>
                </div>
              );
            })}
            {shown ? null : <div className="pt-6 text-center font-serif text-[18px] text-ink-soft">Say hello when the call connects.</div>}
          </div>
          <BuildTag kind="planned" feature="E-03 voice in, sample script shown" className="mt-1" />
        </div>

        <Glass className="flex flex-col gap-4 overflow-auto max-xl:col-span-2">
          <h3 className="m-0 border-b border-hair-2 pb-3 font-serif text-[34px] leading-none font-normal">Chart</h3>
          <div>
            <h4 className="m-0 mb-2 font-serif text-[24px] font-normal">Vitals</h4>
            <div className="rounded-xl bg-wash px-5 py-1.5">
              {vitals.map((vital) => (
                <div key={vital.k} className="grid grid-cols-[90px_1fr] border-t border-hair-2 py-2 font-serif text-[17px] first:border-t-0">
                  <span>{vital.k}</span>
                  <span className={`tabular-nums ${vital.tone === "danger" ? "text-danger" : ""}`}>
                    {vital.v}
                    {VITAL_UNITS[vital.k] ?? ""}
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div className="border-t border-hair-2 pt-3">
            <h4 className="m-0 mb-2 font-serif text-[24px] font-normal">Medications</h4>
            <div className="flex flex-col gap-2">
              {WALTER_MEDS.map((med) => {
                const mentioned = advilMentioned && med.id === "ibuprofen";
                return (
                  <div
                    key={med.name}
                    className={`rounded-xl border px-5 py-2.5 transition-colors duration-500 ${mentioned ? "border-l-4 border-apricot border-y-transparent border-r-transparent bg-warn-wash" : "border-line bg-card"}`}
                  >
                    <div className="font-serif text-[18px]">{med.name}</div>
                    <div className="font-serif text-[15px] text-ink-soft">
                      {med.sub.toLowerCase()}
                      {mentioned ? " · Walter mentioned this" : ""}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="border-t border-hair-2 pt-3">
            <h4 className="m-0 mb-2 font-serif text-[24px] font-normal">Orders</h4>
            {WALTER_ORDERS.map(({ id, name }) => {
              const ready = Boolean(ordered[id]);
              return (
                <div key={id} className="flex items-center justify-between gap-3 py-1.5 font-serif text-[17px]">
                  <span>
                    {name}
                    <span className={`block text-[14px] ${ready ? "text-ok" : "text-muted"}`}>{ready ? "Result in chart" : "Ask for it out loud, or order here"}</span>
                  </span>
                  {ready ? null : (
                    <button type="button" onClick={() => setOrdered({ ...ordered, [id]: true })} className="h-9 rounded-lg border border-indigo-line bg-card px-4 hover:bg-indigo-soft">
                      Order
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </Glass>
      </div>
    </div>
  );
}

function Glass({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`min-h-0 rounded-[18px] border border-white/80 bg-card/90 px-6 py-5 shadow-[0_24px_60px_-34px_rgba(25,31,92,.45)] backdrop-blur-md ${className}`}>
      {children}
    </section>
  );
}
