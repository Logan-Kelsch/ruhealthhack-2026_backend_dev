export type Portrait = "walter" | "alina" | "eli" | "generic";

type AvatarProps = {
  // Kept so a case can name its portrait once iteration 2 adds faces. Unused until then.
  who: Portrait;
  size: number;
};

// Iteration 1 never shows a face. Every patient is the same plain person mark on white,
// so a card reads as "a patient" without suggesting a real person or a mood.
export function Avatar({ size }: AvatarProps) {
  return (
    <span
      aria-hidden
      className="flex shrink-0 items-center justify-center rounded-full border border-line bg-white text-[#a3a8bd]"
      style={{ width: size, height: size }}
    >
      <svg width={size * 0.52} height={size * 0.52} viewBox="0 0 24 24" fill="currentColor">
        <circle cx="12" cy="7.6" r="4.3" />
        <path d="M3.6 21.2c0-4.9 3.8-8.1 8.4-8.1s8.4 3.2 8.4 8.1z" />
      </svg>
    </span>
  );
}
