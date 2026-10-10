import type { ReactNode } from "react";
import type { Go } from "../../app/types";

// Role picker. Teaching opens the faculty home; learning opens the student home.
export function Welcome({ go }: { go: Go }) {
  return (
    <div className="relative h-full overflow-auto">
      <div className="absolute inset-0 bg-painting" />
      <div className="relative flex min-h-full flex-col items-center justify-center gap-11 px-8 py-12 text-center text-ink">
        <div className="flex flex-col items-center gap-3.5">
          <div className="font-serif text-[clamp(72px,10vw,132px)] leading-[0.9] font-medium tracking-[-3px]">Rounds</div>
          <div className="font-serif text-[clamp(20px,2.2vw,28px)] text-indigo">
            Practice patient conversations out loud.
          </div>
        </div>
        <div className="grid w-full max-w-[760px] justify-center gap-4 [grid-template-columns:repeat(auto-fit,minmax(260px,360px))]">
          <RoleCard
            title="I teach"
            body="Build patients, assign cases, see where your class struggles."
            icon={<TeachIcon />}
            onClick={() => go("f-home")}
          />
          <RoleCard
            title="I’m a student"
            body="Talk with your patient, then see what you found and missed."
            icon={<LearnIcon />}
            onClick={() => go("s-home")}
          />
        </div>
      </div>
    </div>
  );
}

function RoleCard({
  title,
  body,
  icon,
  onClick,
}: {
  title: string;
  body: string;
  icon: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col items-start gap-2.5 rounded-[20px] border border-white/90 bg-white/90 p-6 text-left shadow-[0_20px_50px_-24px_rgba(20,27,77,.35)] transition-transform hover:-translate-y-0.5"
    >
      <span className="flex size-11 items-center justify-center rounded-xl bg-ink text-white">{icon}</span>
      <span className="mt-1.5 font-serif text-[28px] font-medium tracking-[-0.4px]">{title}</span>
      <span className="text-[14.5px] leading-snug text-ink-soft">{body}</span>
    </button>
  );
}

function TeachIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M12 3L1 9l11 6 9-4.9V17h2V9z" />
      <path d="M5 13.2v3.6c0 .5 3 2.7 7 2.7s7-2.2 7-2.7v-3.6l-7 3.8z" />
    </svg>
  );
}

function LearnIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" aria-hidden>
      <path d="M12 6c-2-1.5-5-2-9-2v14c4 0 7 .5 9 2 2-1.5 5-2 9-2V4c-4 0-7 .5-9 2zM12 6v14" />
    </svg>
  );
}
