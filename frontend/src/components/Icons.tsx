type IconProps = {
  d: string;
  className?: string;
};

// Stroke icon used in the sidebar. The path comes from the design file's icon set.
export function StrokeIcon({ d, className }: IconProps) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d={d} />
    </svg>
  );
}

export const ICONS = {
  home: "M3 11l9-7 9 7v9h-6v-6H9v6H3z",
  cases: "M6 3h8l4 4v14H6zM9 12h6M9 16h6",
  cohorts:
    "M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM3 20c0-3.5 2.7-6 6-6s6 2.5 6 6M17 11a2.5 2.5 0 1 0 0-5M17 14c2.6.4 4 2.4 4 5",
  insights: "M6 20v-5M12 20V9M18 20V4",
  visits: "M4 6h16M4 12h16M4 18h10",
  settings:
    "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1",
} as const;

export type IconName = keyof typeof ICONS;

// Small chevron used on rows that open another screen.
export function Chevron() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8a8fb3" strokeWidth="2" strokeLinecap="round" aria-hidden>
      <path d="M9 5l7 7-7 7" />
    </svg>
  );
}

export function ArrowRight() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

export function BackArrow() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden>
      <path d="M15 5l-7 7 7 7" />
    </svg>
  );
}

export function PlusIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}
