import { useId, type ReactNode } from "react";
import type { Theme } from "../lib/theme";
import { BackArrow, MoonIcon, SunIcon } from "./Icons";

// Content inside the white sheet. Each screen can pick a narrower max width.
export function Page({
  children,
  width = "max-w-[1480px]",
}: {
  children: ReactNode;
  width?: string;
}) {
  return (
    <div className={`rnd-enter mx-auto flex flex-col gap-6 px-8 pt-8 pb-10 ${width}`}>{children}</div>
  );
}

export function Title({ kicker, children }: { kicker?: string; children: ReactNode }) {
  return (
    <div>
      {kicker ? <div className="mb-1.5 font-sans text-[13px] text-muted">{kicker}</div> : null}
      <h1 className="m-0 font-serif text-[clamp(40px,4.2vw,58px)] leading-[1.02] font-normal tracking-[-1.4px] text-ink">
        {children}
      </h1>
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

// The Rounds mark: a dawn sky over a violet hill, drawn so it stays sharp at any size.
export function DawnDisc({ size = 40, className = "", logo = false }: { size?: number; className?: string; logo?: boolean }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" className={`shrink-0 ${className}`} data-logo-disc={logo || undefined} aria-hidden>
      <defs>
        <linearGradient id={`${id}-sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffcf7f" />
          <stop offset="0.5" stopColor="#ff9466" />
          <stop offset="0.8" stopColor="#ef8aa0" />
        </linearGradient>
        <linearGradient id={`${id}-hill`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#a888dc" />
          <stop offset="0.45" stopColor="#6f6fd0" />
          <stop offset="1" stopColor="#3550a8" />
        </linearGradient>
        <clipPath id={`${id}-clip`}>
          <circle cx="50" cy="50" r="50" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${id}-clip)`}>
        <rect width="100" height="100" fill={`url(#${id}-sky)`} />
        <path d="M0 62 C 22 54, 38 48, 58 47 S 88 52, 100 56 V100 H0Z" fill={`url(#${id}-hill)`} />
      </g>
    </svg>
  );
}

// "Rounds" with the dawn disc standing in for the o.
export function Wordmark({ size = "md" }: { size?: "lg" | "md" | "sm" | number }) {
  const px = typeof size === "number" ? size : size === "lg" ? 64 : size === "md" ? 52 : 30;
  return (
    <span
      className="inline-flex items-baseline font-serif leading-none font-normal text-ink"
      style={{ fontSize: px, letterSpacing: -px * 0.03 }}
      aria-label="Rounds"
    >
      <span aria-hidden>R</span>
      <DawnDisc size={px * 0.56} logo className="mx-[0.02em] self-baseline translate-y-[0.02em]" />
      <span aria-hidden>unds</span>
    </span>
  );
}

const BUTTON_SIZES = {
  sm: "h-9 gap-1.5 rounded-[10px] px-3.5 text-[15px]",
  md: "h-11 gap-2 rounded-xl px-5 text-[17px]",
  lg: "h-14 gap-2.5 rounded-xl px-8 text-[20px]",
} as const;

// Solid navy button for the one main action on a screen.
export function PrimaryButton({
  children,
  onClick,
  size = "md",
  block = false,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  size?: "sm" | "md" | "lg";
  block?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center bg-panel font-serif text-white shadow-[0_8px_20px_-10px_rgba(37,45,120,.6)] transition-colors hover:bg-panel-hover ${BUTTON_SIZES[size]} ${block ? "w-full justify-center" : ""} ${className}`}
    >
      {children}
    </button>
  );
}

// Light indigo button with an indigo outline: the references' most common action style.
export function SoftButton({
  children,
  onClick,
  size = "md",
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center border border-indigo-line bg-indigo-soft font-serif text-ink transition-colors hover:bg-indigo-soft-2 ${BUTTON_SIZES[size]} ${className}`}
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
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center border border-line-2 bg-card font-serif text-ink transition-colors hover:bg-wash ${BUTTON_SIZES[size]} ${className}`}
    >
      {children}
    </button>
  );
}

/** @deprecated Dark mode is retired and no screen renders this switch. */
export function ThemeToggle({ theme, onToggle, className = "" }: { theme: Theme; onToggle: () => void; className?: string }) {
  const dark = theme === "dark";
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={dark}
      className={`inline-flex h-9 items-center justify-center gap-2 rounded-full border border-line-2 bg-card/90 px-3.5 font-sans text-[13px] font-medium text-ink-soft backdrop-blur hover:bg-card ${className}`}
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
      className="inline-flex items-center gap-1.5 self-start font-sans text-[13px] text-ink-soft hover:text-ink"
    >
      <BackArrow />
      {label}
    </button>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section
      className={`overflow-hidden rounded-[14px] border border-line bg-card shadow-[0_1px_2px_rgba(25,31,92,.04),0_10px_30px_-22px_rgba(25,31,92,.25)] ${className}`}
    >
      {children}
    </section>
  );
}

// Card header: serif title on the left, optional control on the right.
// Pass className to replace the default padding on dense panels.
export function CardHead({
  title,
  aside,
  underline = true,
  className = "px-6 pt-5 pb-4",
}: {
  title: string;
  aside?: ReactNode;
  underline?: boolean;
  className?: string;
}) {
  return (
    <div className={`flex items-center justify-between gap-3 ${underline ? "border-b border-hair-2" : ""} ${className}`}>
      <span className="font-serif text-[clamp(22px,2vw,30px)] leading-tight tracking-[-0.5px] text-ink">{title}</span>
      {aside}
    </div>
  );
}

type BadgeTone = "neutral" | "ok" | "warn" | "danger" | "indigo";

const BADGE_TONES: Record<BadgeTone, string> = {
  neutral: "bg-chip text-ink",
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-pill text-warn-deep",
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
    <span className={`inline-flex h-8 items-center gap-1.5 rounded-full px-3.5 font-serif text-[15px] whitespace-nowrap ${BADGE_TONES[tone]}`}>
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
  info: "bg-indigo-soft text-indigo",
};

// Round check or alert mark for checklists and note lists.
export function Mark({ tone, children, className = "" }: { tone: MarkTone; children: ReactNode; className?: string }) {
  return (
    <span className={`flex size-6 shrink-0 items-center justify-center rounded-full font-sans text-[12px] font-bold ${MARK_TONES[tone]} ${className}`}>
      {children}
    </span>
  );
}

// Large round check or alert used by the debrief and the review queue.
export function BigMark({ tone, className = "" }: { tone: "ok" | "danger" | "info"; className?: string }) {
  const style = tone === "ok" ? "bg-ok-soft text-ok" : tone === "danger" ? "bg-danger-soft text-danger" : "bg-indigo-soft text-indigo";
  return (
    <span className={`flex size-14 shrink-0 items-center justify-center rounded-full ${style} ${className}`}>
      {tone === "ok" ? (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M5 12.5l4.5 4.5L19 7.5" />
        </svg>
      ) : (
        <span className="font-sans text-[26px] leading-none font-bold">!</span>
      )}
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
    <div className={`rounded-[14px] border border-line bg-card px-5 py-[18px] ${STAT_ACCENTS[accent]} ${className}`}>
      <div className="font-sans text-[13px] text-ink-soft">{label}</div>
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
    <nav className="flex gap-7 overflow-x-auto border-b border-line-3">
      {items.map((item) => {
        const on = active === item.id;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onChange(item.id)}
            className={`-mb-px flex items-center gap-1.5 border-b-2 px-2.5 pb-2.5 font-serif text-[18px] whitespace-nowrap hover:text-ink ${
              on ? "border-indigo text-indigo" : "border-transparent text-muted"
            }`}
          >
            {item.label}
            {item.badge ? (
              <span className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-warn-pill px-1 font-sans text-[11px] font-bold text-warn-deep">
                {item.badge}
              </span>
            ) : null}
          </button>
        );
      })}
    </nav>
  );
}

// Honest labels for parts of a screen. "planned" means no backend exists yet;
// "sample" means the backend has the feature but this screen still shows fixture data.
export function BuildTag({ kind, feature, className = "" }: { kind: "planned" | "sample"; feature?: string; className?: string }) {
  const planned = kind === "planned";
  return (
    <span
      title={planned ? "No backend for this yet. Shown to plan the design." : "The API exists; this screen still shows sample data."}
      className={`inline-flex h-6 shrink-0 items-center gap-1.5 rounded-full border border-dashed px-2.5 font-sans text-[11.5px] font-semibold tracking-[0.2px] whitespace-nowrap ${
        planned ? "border-warn/50 bg-warn-wash text-warn" : "border-indigo-line/70 bg-indigo-soft/60 text-indigo"
      } ${className}`}
    >
      <span className={`size-1.5 rounded-full ${planned ? "border border-current" : "bg-current"}`} />
      {planned ? "Not built yet" : "Sample data"}
      {feature ? <span className="font-medium opacity-70">· {feature}</span> : null}
    </span>
  );
}
