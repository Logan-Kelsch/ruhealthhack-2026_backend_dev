import type { MouseEvent, ReactNode } from "react";
import type { Go } from "../../app/types";
import { useModeSwitch, type Role } from "../../components/ModeTransition";
import { Wordmark } from "../../components/ui";

// Role picker. Teaching opens the faculty home; learning opens the student home.
export function Welcome({ go }: { go: Go }) {
  const switchMode = useModeSwitch();

  function pick(role: Role) {
    return (event: MouseEvent<HTMLButtonElement>) => {
      const box = event.currentTarget.getBoundingClientRect();
      switchMode(role, { x: box.left + box.width / 2, y: box.top + box.height / 2 }, () =>
        go(role === "faculty" ? "f-home" : "s-home"),
      );
    };
  }

  return (
    <div className="relative h-full overflow-auto">
      <div className="bg-painting absolute inset-0" />
      <div
        className="absolute inset-0"
        style={{ background: "radial-gradient(ellipse 60% 55% at 50% 50%, rgba(255,253,250,.92), rgba(255,253,250,.55) 60%, transparent 85%)" }}
      />
      <div className="relative flex min-h-full flex-col items-center justify-center gap-12 px-8 py-12 text-center text-ink">
        <div className="flex flex-col items-center gap-4">
          <Wordmark size={Math.round(Math.min(148, Math.max(80, window.innerWidth * 0.085)))} />
          <div className="font-serif text-[clamp(22px,2.5vw,38px)] tracking-[-0.4px] text-ink">
            Practice patient conversations out loud.
          </div>
        </div>
        <div className="grid w-full max-w-[960px] justify-center gap-[clamp(20px,3vw,48px)] [grid-template-columns:repeat(auto-fit,minmax(280px,450px))]">
          <RoleCard
            title="I teach"
            body="Build patients, assign cases, see where your class struggles."
            icon={<TeachIcon />}
            onClick={pick("faculty")}
          />
          <RoleCard
            title="I’m a student"
            body="Talk with your patient, then see what you found and missed."
            icon={<LearnIcon />}
            onClick={pick("student")}
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
  onClick: (event: MouseEvent<HTMLButtonElement>) => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex flex-col items-center gap-3 rounded-[18px] border border-indigo-line/40 bg-card/85 px-8 pt-8 pb-9 text-center shadow-[0_24px_60px_-34px_rgba(25,31,92,.45)] backdrop-blur-sm transition-[transform,box-shadow] duration-300 hover:-translate-y-1 hover:shadow-[0_30px_70px_-30px_rgba(25,31,92,.5)]"
    >
      <span
        className="flex size-[132px] items-center justify-center rounded-full text-[#1f2a9c] transition-transform duration-500 group-hover:scale-105"
        style={{ background: "radial-gradient(circle at 50% 45%, rgba(255,255,255,.7), transparent 60%), url(/assets/bloom.jpg) 30% 20% / 500% auto" }}
      >
        {icon}
      </span>
      <span className="mt-2 font-serif text-[clamp(32px,2.8vw,46px)] leading-none tracking-[-0.8px]">{title}</span>
      <span className="max-w-[340px] font-serif text-[clamp(17px,1.4vw,22px)] leading-snug text-ink">{body}</span>
    </button>
  );
}

function TeachIcon() {
  return (
    <svg width="72" height="72" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M12 4L1.5 9.2 12 14.4l8.6-4.3v5.6h1.6V9.2z" />
      <path d="M5.6 12.6v3.6c0 .6 2.9 2.8 6.4 2.8s6.4-2.2 6.4-2.8v-3.6L12 15.8z" />
    </svg>
  );
}

function LearnIcon() {
  return (
    <svg width="66" height="66" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" aria-hidden>
      <path d="M12 6.2C10 4.8 7 4.3 3 4.3v13.6c4 0 7 .5 9 1.9 2-1.4 5-1.9 9-1.9V4.3c-4 0-7 .5-9 1.9zM12 6.2v13.6" />
    </svg>
  );
}
