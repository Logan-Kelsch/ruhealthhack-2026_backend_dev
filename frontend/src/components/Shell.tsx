import type { ReactNode } from "react";
import type { Go, ScreenId } from "../app/types";
import { useTheme } from "../lib/theme";
import { FACULTY_USER, STUDENT_USER } from "../mock/session";
import { ICONS, StrokeIcon, type IconName } from "./Icons";
import { ThemeToggle, Wordmark } from "./ui";

type Role = "faculty" | "student";

type NavDef = {
  key: string;
  label: string;
  icon: IconName;
  // Missing target means the item is shown but not built yet.
  target?: ScreenId;
  count?: number;
};

const FACULTY_NAV: NavDef[] = [
  { key: "home", label: "Home", icon: "home", target: "f-home", count: 3 },
  { key: "cases", label: "Cases", icon: "cases", target: "f-cases" },
  { key: "cohorts", label: "Cohorts", icon: "cohorts" },
  { key: "insights", label: "Insights", icon: "insights" },
  { key: "settings", label: "Settings", icon: "settings" },
];

const STUDENT_NAV: NavDef[] = [
  { key: "home", label: "Home", icon: "home", target: "s-home" },
  { key: "visits", label: "My visits", icon: "visits", target: "s-between" },
  { key: "settings", label: "Settings", icon: "settings" },
];

// Which sidebar item looks selected for the current screen.
function sectionFor(screen: ScreenId): string | undefined {
  const map: Partial<Record<ScreenId, string>> = {
    "f-home": "home",
    "f-cases": "cases",
    "f-import": "cases",
    "f-studio": "cases",
    "s-home": "home",
    "s-brief": "home",
    "s-debrief": "visits",
    "s-between": "visits",
  };
  return map[screen];
}

type ShellProps = {
  screen: ScreenId;
  go: Go;
  children: ReactNode;
};

// Signed-in frame from Rounds.dc.html: sidebar, wordmark, and the current screen.
// Mic check and the encounter hide the sidebar so the visit can use the full window.
export function Shell({ screen, go, children }: ShellProps) {
  const { theme, toggle } = useTheme();
  const role: Role = screen.startsWith("f-") ? "faculty" : "student";
  const focus = screen === "s-mic" || screen === "s-encounter";
  const section = sectionFor(screen);
  const items = role === "faculty" ? FACULTY_NAV : STUDENT_NAV;
  const user = role === "faculty" ? FACULTY_USER : STUDENT_USER;

  return (
    <div className="relative flex h-full min-h-[620px] overflow-hidden bg-paper text-ink">
      <div className="pointer-events-none absolute inset-0 bg-wash" />
      <div className="relative flex h-full w-full">
        {focus ? null : (
          <aside className="flex h-full w-[232px] shrink-0 flex-col border-r border-ink/7 bg-card/55 px-3.5 pt-[22px] pb-4 backdrop-blur-xl">
            <button
              type="button"
              onClick={() => go(role === "faculty" ? "f-home" : "s-home")}
              className="px-2.5 pb-[22px] text-left leading-none"
            >
              <Wordmark />
            </button>
            <div className="px-2.5 pb-2 text-[11px] font-semibold tracking-[0.8px] text-muted uppercase">
              {role === "faculty" ? "Faculty" : "Student"}
            </div>
            <nav className="flex flex-col gap-0.5">
              {items.map((item) => {
                const active = section === item.key;
                return (
                  <NavItem
                    key={item.key}
                    label={item.label}
                    icon={item.icon}
                    count={item.count}
                    active={active}
                    soon={!item.target}
                    onClick={() => item.target && go(item.target)}
                  />
                );
              })}
            </nav>
            <div className="flex-1" />
            <div className="flex items-center gap-2.5 rounded-xl border border-line bg-card p-2.5">
              <div className="flex size-[34px] shrink-0 items-center justify-center rounded-full bg-indigo-soft text-xs font-bold text-indigo">
                {user.initials}
              </div>
              <div className="min-w-0 flex-1 leading-tight">
                <div className="truncate text-[13px] font-semibold">{user.name}</div>
                <div className="truncate text-xs text-muted">{user.role}</div>
              </div>
            </div>
            <ThemeToggle theme={theme} onToggle={toggle} className="mt-2 w-full" />
            <button
              type="button"
              onClick={() => go("welcome")}
              className="mt-1.5 rounded-lg px-2.5 py-2 text-center text-[12.5px] text-ink-soft hover:bg-card/80"
            >
              Switch role
            </button>
          </aside>
        )}
        <div className="h-full min-w-0 flex-1 overflow-auto">{children}</div>
      </div>
    </div>
  );
}

function NavItem({
  label,
  icon,
  count,
  active,
  soon,
  onClick,
}: {
  label: string;
  icon: IconName;
  count?: number;
  active: boolean;
  soon: boolean;
  onClick: () => void;
}) {
  const state = active
    ? "bg-card font-semibold text-ink shadow-[0_1px_2px_rgba(20,27,77,.08),0_0_0_1px_rgba(20,27,77,.05)]"
    : soon
      ? "cursor-default font-medium text-soon"
      : "font-medium text-ink-soft hover:bg-card/90";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex h-[38px] items-center gap-3 rounded-[9px] px-2.5 text-sm ${state}`}
    >
      <StrokeIcon d={ICONS[icon]} />
      <span className="flex-1 text-left">{label}</span>
      {count ? (
        <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-danger-soft px-1.5 text-[11.5px] font-bold text-danger">
          {count}
        </span>
      ) : null}
      {soon ? <span className="text-[11px] text-faint">Soon</span> : null}
    </button>
  );
}
