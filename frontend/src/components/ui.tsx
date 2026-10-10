import type { ReactNode } from "react";
import { ArrowRight, BackArrow, PlusIcon } from "./Icons";

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

export function PrimaryButton({
  children,
  onClick,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex h-10 items-center gap-2 rounded-[10px] bg-ink px-4 text-sm font-medium text-white hover:bg-indigo ${className}`}
    >
      {children}
    </button>
  );
}

export function GhostButton({
  children,
  onClick,
}: {
  children: ReactNode;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-10 items-center gap-2 rounded-[10px] border border-line-2 bg-white px-4 text-sm font-medium text-ink hover:bg-wash"
    >
      {children}
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
  return <section className={`overflow-hidden rounded-2xl border border-line bg-white ${className}`}>{children}</section>;
}

export function CardHead({ title, aside }: { title: string; aside?: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-[#eeeff5] px-5 py-4">
      <span className="text-[15px] font-semibold">{title}</span>
      {aside}
    </div>
  );
}

export { ArrowRight, PlusIcon };
