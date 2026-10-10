import { useEffect, useState } from "react";
import type { Go } from "../../app/types";
import { MicIcon } from "../../components/Icons";
import { GhostButton, Mark, PrimaryButton, Wordmark } from "../../components/ui";

const WORDS = ["Testing", "Testing, one", "Testing, one, two", "Testing, one, two, three"];

// Practice screen before the visit. The level moves on a timer so the student can see the mic is live.
// There is no text box: the encounter itself stays hands-free.
export function MicCheck({ go }: { go: Go }) {
  const [tick, setTick] = useState(0);
  const [muted, setMuted] = useState(false);

  useEffect(() => {
    const timer = window.setInterval(() => setTick((value) => value + 1), 220);
    return () => window.clearInterval(timer);
  }, []);

  const level = muted ? 0 : 0.3 + 0.6 * Math.abs(Math.sin(tick * 0.7)) * (0.7 + 0.3 * Math.sin(tick * 2.3));
  const heard = muted ? "Muted" : WORDS[Math.min(3, Math.floor(tick / 8) % 6)];

  return (
    <div className="flex min-h-full flex-col">
      <div className="flex items-center justify-between px-8 py-5">
        <Wordmark size="sm" />
        <GhostButton size="sm" onClick={() => go("s-brief")}>
          Back to briefing
        </GhostButton>
      </div>
      <div className="flex flex-1 items-center justify-center px-8 pt-5 pb-12">
        <section className="flex w-full max-w-[480px] flex-col items-center gap-[22px] rounded-[20px] border border-line bg-card px-8 py-8 text-center">
          <div>
            <h1 className="m-0 font-serif text-[30px] font-medium tracking-[-0.6px]">Mic check</h1>
            <p className="mt-1.5 text-[14.5px] text-ink-soft">Say a few words. You should see the level move.</p>
          </div>
          <div className="relative flex size-[140px] items-center justify-center">
            <div className={`absolute inset-0 rounded-full bg-indigo-soft-2 ${muted ? "" : "rnd-pulse"}`} />
            <div className={`relative flex size-24 items-center justify-center rounded-full text-white ${muted ? "bg-inactive" : "bg-ink"}`}>
              <MicIcon size={36} />
            </div>
          </div>
          <div className="flex w-full flex-col gap-2">
            <div className="flex h-2 gap-[3px]">
              {Array.from({ length: 16 }, (_, index) => {
                const on = index / 16 < level;
                const hot = on && index > 12;
                return <span key={index} className={`flex-1 rounded-sm ${on ? (hot ? "bg-danger-bright" : "bg-indigo") : "bg-track"}`} />;
              })}
            </div>
            <div className="min-h-[22px] text-[15px] font-medium">“{heard}”</div>
          </div>
          <div className="flex w-full flex-col rounded-xl border border-hair-2 text-left">
            <CheckRow mark="✓" tone="ok">
              Microphone detected
            </CheckRow>
            <CheckRow mark="i" tone="info" border>
              Headphones recommended, so the patient’s voice doesn’t echo
            </CheckRow>
            <button type="button" onClick={() => setMuted((value) => !value)} className="flex items-center gap-3 border-t border-hair px-3.5 py-3 text-left text-sm">
              <span className={`relative h-5 w-[34px] shrink-0 rounded-full transition-colors ${muted ? "bg-ink" : "bg-line-4"}`}>
                <span className={`absolute top-0.5 size-4 rounded-full bg-white shadow-[0_1px_2px_rgba(0,0,0,.25)] transition-[left] ${muted ? "left-4" : "left-0.5"}`} />
              </span>
              {muted ? "Muted. Tap to unmute." : "You can mute any time"}
            </button>
          </div>
          <PrimaryButton size="lg" block onClick={() => go("s-encounter")}>
            I’m ready, start the visit
          </PrimaryButton>
          <div className="text-[12.5px] text-muted">There is no typing during the visit.</div>
        </section>
      </div>
    </div>
  );
}

function CheckRow({
  mark,
  tone,
  border,
  children,
}: {
  mark: string;
  tone: "ok" | "info";
  border?: boolean;
  children: string;
}) {
  return (
    <div className={`flex items-center gap-3 px-3.5 py-3 text-sm ${border ? "border-t border-hair" : ""}`}>
      <Mark tone={tone}>{mark}</Mark>
      {children}
    </div>
  );
}
