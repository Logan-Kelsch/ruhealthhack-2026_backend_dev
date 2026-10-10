import type { ReactNode } from "react";
import type { Theme } from "../lib/theme";
import { BackArrow, MoonIcon, SunIcon } from "./Icons";

// Shared page width. Each screen picks its own max so the design's columns stay intact.
export function Page({
  children,
  width = "max-w-[1240px]",
}: {
  children: ReactNode;
  width?: string;
}) {
  return (
    <div className={`mx-auto flex flex-col gap-5 px-10 py-8 ${width}`}>{children}</div>
  );
}

export function Title({ kicker, children }: { kicker?: string; children: ReactNode }) {
  return (
    <div>
      {kicker ? <div className="mb-1.5 text-[13px] text-muted">{kicker}</div> : null}
      <h1 className="m-0 font-serif text-[38px] leading-[1.05] font-medium tracking-[-0.8px]">{children}</h1>
    </div>
  );
}

// Page headline row: title on the left, actions on the right.
export function PageHeader({
  kicker,
  title,
  children,
}: {
  kicker?: string;
  title: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <Title kicker={kicker}>{title}</Title>
      {children}
    </header>
  );
}

export function Wordmark({ size = "md" }: { size?: "md" | "sm" }) {
  const text = size === "md" ? "text-[30px] tracking-[-0.8px]" : "text-2xl tracking-[-0.6px]";
  return <span className={`font-serif font-medium ${text}`}>Rounds</span>;
}

export function PrimaryButton({
  children,
  onClick,
  size = "md",
  block = false,
  className = "",
  disabled = false,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  size?: "sm" | "md" | "lg";
  block?: boolean;
  className?: string;
  disabled?: boolean;
  type?: "button" | "submit";
}) {
  const shape =
    size === "lg"
      ? "h-12 gap-2.5 rounded-xl px-[22px] text-[15px] font-semibold"
      : size === "sm"
        ? "h-8 gap-1.5 rounded-lg px-3 text-[13px] font-medium"
        : "h-10 gap-2 rounded-[10px] px-4 text-sm font-medium";
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center bg-panel text-white hover:bg-panel-hover disabled:cursor-not-allowed disabled:opacity-60 ${shape} ${block ? "w-full justify-center" : ""} ${className}`}
    >
      {children}
    </button>
  );
}

export function GhostButton({
  children,
  onClick,
  size = "md",
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  size?: "md" | "sm";
  className?: string;
}) {
  const shape = size === "sm" ? "h-8 gap-1.5 rounded-lg px-3 text-[13px]" : "h-10 gap-2 rounded-[10px] px-4 text-sm";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center border border-line-2 bg-card font-medium text-ink hover:bg-wash ${shape} ${className}`}
    >
      {children}
    </button>
  );
}

// Light/dark switch. Lives on the welcome screen and in the sidebar.
export function ThemeToggle({ theme, onToggle, className = "" }: { theme: Theme; onToggle: () => void; className?: string }) {
  const dark = theme === "dark";
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={dark}
      className={`inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-line-2 bg-card px-3 text-[13px] font-medium text-ink-soft hover:bg-wash ${className}`}
    >
      {dark ? <SunIcon /> : <MoonIcon />}
      {dark ? "Light mode" : "Dark mode"}
    </button>
  );
}

export function BackLink({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 self-start text-[13px] text-ink-soft hover:text-ink"
    >
      <BackArrow />
      {label}
    </button>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`overflow-hidden rounded-2xl border border-line bg-card ${className}`}>{children}</section>;
}

// Card header: title on the left, optional control on the right.
// Pass className to replace the default padding on dense panels.
export function CardHead({
  title,
  aside,
  underline = true,
  className = "px-5 py-4",
}: {
  title: string;
  aside?: ReactNode;
  underline?: boolean;
  className?: string;
}) {
  return (
    <div className={`flex items-center justify-between ${underline ? "border-b border-hair-2" : ""} ${className}`}>
      <span className="text-[15px] font-semibold">{title}</span>
      {aside}
    </div>
  );
}

type BadgeTone = "neutral" | "ok" | "warn" | "danger" | "indigo";

const BADGE_TONES: Record<BadgeTone, string> = {
  neutral: "bg-chip text-ink-soft",
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  danger: "bg-danger-soft text-danger",
  indigo: "bg-indigo-soft text-indigo",
};

// Status pill. `dot` adds the small tone-colored dot used for statuses.
export function Badge({
  children,
  tone = "neutral",
  dot = false,
}: {
  children: ReactNode;
  tone?: BadgeTone;
  dot?: boolean;
}) {
  return (
    <span className={`inline-flex h-6 items-center gap-1.5 rounded-md px-2 text-xs font-semibold ${BADGE_TONES[tone]}`}>
      {dot ? <span className="size-1.5 rounded-full bg-current" /> : null}
      {children}
    </span>
  );
}

type MarkTone = "ok" | "warn" | "danger" | "info";

const MARK_TONES: Record<MarkTone, string> = {
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  danger: "bg-danger-soft text-danger",
  info: "bg-segment text-ink-soft",
};

// Round check or alert mark for checklists and note lists.
export function Mark({ tone, children, className = "" }: { tone: MarkTone; children: ReactNode; className?: string }) {
  return (
    <span className={`flex size-5 items-center justify-center rounded-full text-[11px] font-bold ${MARK_TONES[tone]} ${className}`}>
      {children}
    </span>
  );
}

type StatAccent = "none" | "ok" | "danger";

const STAT_ACCENTS: Record<StatAccent, string> = {
  none: "",
  ok: "border-t-[3px] border-t-ok",
  danger: "border-t-[3px] border-t-danger-strong",
};

// Summary tile: label on top, one number or line below.
export function StatCard({
  label,
  accent = "none",
  className = "",
  children,
}: {
  label: string;
  accent?: StatAccent;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={`rounded-2xl border border-line bg-card px-5 py-[18px] ${STAT_ACCENTS[accent]} ${className}`}>
      <div className="text-[13px] text-ink-soft">{label}</div>
      {children}
    </div>
  );
}

export type TabItem<T extends string> = { id: T; label: string; badge?: string };

// Underline tabs used by Patient Studio and the debrief.
export function TabNav<T extends string>({
  items,
  active,
  onChange,
}: {
  items: TabItem<T>[];
  active: T;
  onChange: (id: T) => void;
}) {
  return (
    <nav className="flex gap-6 overflow-x-auto border-b border-line-3">
      {items.map((item) => {
        const on = active === item.id;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onChange(item.id)}
            className={`-mb-px flex items-center gap-1.5 border-b-2 px-px pb-3 text-sm whitespace-nowrap hover:text-ink ${
              on ? "border-ink font-semibold text-ink" : "border-transparent font-medium text-muted"
            }`}
          >
            {item.label}
            {item.badge ? (
              <span className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-warn-soft px-1 text-[11px] font-bold text-warn">
                {item.badge}
              </span>
            ) : null}
          </button>
        );
      })}
    </nav>
  );
}
