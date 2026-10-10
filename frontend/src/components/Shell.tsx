import { useEffect, useState, type ReactNode } from "react";
import type { Go, ScreenId } from "../app/types";
import { useModeSwitch, type Role } from "./ModeTransition";
import { DawnDisc, Wordmark } from "./ui";

type RailKey = "home" | "insights" | "cases" | "people" | "settings";

type NavDef = {
  key: RailKey;
  label: string;
  // Missing target means the item is planned but has no screen or backend yet.
  target?: ScreenId;
  planned?: string;
};

// The rail keeps the same five places in both modes, like the references.
// Student mode drops the people icon: a student has no roster to manage.
const FACULTY_NAV: NavDef[] = [
  { key: "home", label: "Home", target: "f-home" },
  { key: "insights", label: "Class insights", planned: "Class gaps across a cohort (PRD D-02)" },
  { key: "cases", label: "Cases", target: "f-cases" },
  { key: "people", label: "Cohorts", planned: "Cohorts and assignments (PRD D-01)" },
  { key: "settings", label: "Settings", planned: "Account and course settings" },
];

const STUDENT_NAV: NavDef[] = [
  { key: "home", label: "Home", target: "s-home" },
  { key: "insights", label: "My progress", planned: "Progress across visits (PRD D-03)" },
  { key: "cases", label: "My visits", target: "s-between" },
  { key: "settings", label: "Settings", planned: "Microphone and account settings" },
];

// Which rail item looks selected for the current screen.
function sectionFor(screen: ScreenId): RailKey | undefined {
  const map: Partial<Record<ScreenId, RailKey>> = {
    "f-home": "home",
    "f-review": "home",
    "f-cases": "cases",
    "f-import": "cases",
    "f-studio": "cases",
    "s-home": "home",
    "s-brief": "home",
    "s-mic": "home",
    "s-debrief": "cases",
    "s-between": "cases",
  };
  return map[screen];
}

type ShellProps = {
  screen: ScreenId;
  go: Go;
  children: ReactNode;
};

// Signed-in frame from the UI references: watercolor dawn across the top, the
// wordmark top left, a slim white icon rail, and one large white sheet.
// The briefing drops the sheet so its card can stand on the street painting.
export function Shell({ screen, go, children }: ShellProps) {
  const switchMode = useModeSwitch();
  const role: Role = screen.startsWith("f-") ? "faculty" : "student";
  const scene = screen === "s-brief";
  const section = sectionFor(screen);
  const items = role === "faculty" ? FACULTY_NAV : STUDENT_NAV;
  const [note, setNote] = useState<NavDef | null>(null);

  useEffect(() => {
    if (!note) return;
    const timer = window.setTimeout(() => setNote(null), 4200);
    return () => window.clearTimeout(timer);
  }, [note]);

  function swap() {
    const next: Role = role === "faculty" ? "student" : "faculty";
    switchMode(next, () => go(next === "faculty" ? "f-home" : "s-home"));
  }

  return (
    <div className={`relative h-full min-h-[640px] overflow-hidden text-ink ${scene ? "bg-street" : "bg-backdrop"}`}>
      <header className={`absolute top-0 right-0 flex h-[108px] items-center justify-between pr-6 ${scene ? "left-[92px] pl-12" : "left-0 pl-[clamp(28px,5.4vw,90px)]"}`}>
        <button type="button" onClick={() => go(role === "faculty" ? "f-home" : "s-home")} className="leading-none" aria-label="Rounds home">
          <Wordmark size="lg" />
        </button>
      </header>

      <nav
        aria-label="Main"
        className={`absolute bottom-0 left-0 flex w-[92px] flex-col items-center gap-3 border-r border-white/70 bg-white/80 pt-6 pb-5 backdrop-blur-md dark:border-line dark:bg-card/80 ${scene ? "top-0 pt-7" : "top-[112px] rounded-tr-[18px] border-t"}`}
      >
        {items.map((item) => {
          const active = section === item.key;
          return (
            <button
              key={item.key}
              type="button"
              title={item.planned ? `${item.label}: not built yet` : item.label}
              aria-label={item.label}
              aria-current={active ? "page" : undefined}
              onClick={() => (item.target ? go(item.target) : setNote(item))}
              className={`group relative flex h-[56px] w-[70px] items-center justify-center rounded-[14px] transition-colors ${
                active ? "bg-indigo-soft text-ink" : "text-ink-soft hover:bg-indigo-soft/60"
              }`}
            >
              <RailIcon name={item.key} />
              {item.planned ? <span className="absolute top-2.5 right-3 size-[7px] rounded-full border border-warn/70 bg-warn-wash" /> : null}
            </button>
          );
        })}
        <div className="flex-1" />
        <button
          type="button"
          onClick={swap}
          className="group flex flex-col items-center gap-1.5 rounded-[14px] px-1.5 py-2 hover:bg-indigo-soft/60"
          aria-label={role === "faculty" ? "Switch to learner mode" : "Switch to educator mode"}
        >
          <DawnDisc size={34} className="transition-transform duration-500 group-hover:rotate-[24deg] group-hover:scale-110" />
          <span className="font-sans text-[11px] leading-tight font-semibold text-ink-soft">
            {role === "faculty" ? "Learner" : "Educator"}
            <br />
            view
          </span>
        </button>
      </nav>

      {scene ? (
        <main className="absolute inset-0 left-[92px] overflow-auto pt-[108px]">{children}</main>
      ) : (
        <main className="absolute top-[112px] right-[clamp(10px,1vw,16px)] bottom-[clamp(12px,2.6vh,28px)] left-[110px] overflow-auto rounded-[18px] border border-white/80 bg-sheet shadow-[0_20px_60px_-30px_rgba(25,31,92,.35)] backdrop-blur-sm dark:border-line">
          {children}
        </main>
      )}

      {note ? (
        <div
          role="status"
          className="absolute bottom-6 left-[110px] z-20 flex max-w-[420px] items-start gap-3 rounded-[14px] border border-warn-line bg-card px-4 py-3.5 shadow-[0_18px_40px_-20px_rgba(25,31,92,.45)]"
        >
          <span className="mt-0.5 size-2.5 shrink-0 rounded-full border-2 border-warn" />
          <div>
            <div className="font-serif text-[18px] leading-snug">{note.label} is not built yet</div>
            <div className="mt-0.5 font-sans text-[13px] text-ink-soft">{note.planned}. The icon is here so the layout matches the plan.</div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

// Filled glyphs matching the references' rail: house, bar chart, page, people, gear.
function RailIcon({ name }: { name: RailKey }) {
  const common = { width: 30, height: 30, viewBox: "0 0 24 24", "aria-hidden": true } as const;
  switch (name) {
    case "home":
      return (
        <svg {...common} fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinejoin="round">
          <path d="M3.5 10.6L12 3.8l8.5 6.8V20.2h-5.7v-5.9H9.2v5.9H3.5z" />
        </svg>
      );
    case "insights":
      return (
        <svg {...common} fill="currentColor">
          <rect x="4" y="13" width="3.6" height="7.5" rx="1.2" />
          <rect x="10.2" y="8.5" width="3.6" height="12" rx="1.2" />
          <rect x="16.4" y="4" width="3.6" height="16.5" rx="1.2" />
        </svg>
      );
    case "cases":
      return (
        <svg {...common} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round">
          <path d="M6 3h8l4.5 4.5V21H6z" />
          <path d="M14 3v4.5h4.5M9 11.5h6M9 14.5h6M9 17.5h4" />
        </svg>
      );
    case "people":
      return (
        <svg {...common} fill="currentColor">
          <circle cx="12" cy="8" r="3" />
          <circle cx="5.5" cy="9.5" r="2.3" />
          <circle cx="18.5" cy="9.5" r="2.3" />
          <path d="M6.5 19.5c0-3.3 2.5-5.7 5.5-5.7s5.5 2.4 5.5 5.7z" />
          <path d="M1.5 19c0-2.6 1.8-4.4 4-4.4 1 0 1.8.3 2.5.8-1 1.1-1.6 2.4-1.8 3.6zM22.5 19c0-2.6-1.8-4.4-4-4.4-1 0-1.8.3-2.5.8 1 1.1 1.6 2.4 1.8 3.6z" />
        </svg>
      );
    case "settings":
      return (
        <svg {...common} fill="currentColor">
          <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.49.49 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.48.48 0 0 0-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.48.48 0 0 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32a.49.49 0 0 0-.12-.61zM12 15.6a3.6 3.6 0 1 1 0-7.2 3.6 3.6 0 0 1 0 7.2z" />
        </svg>
      );
  }
}
