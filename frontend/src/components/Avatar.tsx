export type Portrait = "walter" | "alina" | "eli" | "generic";

type AvatarProps = {
  who: Portrait;
  size: number;
};

// Iteration 1 never shows a face: each patient is a watercolor bloom cut from the same painting,
// so the cases stay recognizable without looking like a photo of a real person.
const CROPS: Record<Portrait, { pos: string; tint: string }> = {
  walter: { pos: "62% 38%", tint: "rgba(255,190,120,.35)" },
  alina: { pos: "18% 62%", tint: "rgba(255,160,120,.45)" },
  eli: { pos: "86% 22%", tint: "rgba(255,210,140,.3)" },
  generic: { pos: "40% 10%", tint: "rgba(170,160,230,.3)" },
};

export function Avatar({ who, size }: AvatarProps) {
  const crop = CROPS[who];
  return (
    <span
      aria-hidden
      className="relative block shrink-0 overflow-hidden rounded-full"
      style={{
        width: size,
        height: size,
        background: `radial-gradient(circle at 55% 60%, ${crop.tint}, transparent 60%), url(/assets/bloom.jpg) ${crop.pos} / 420% auto`,
        boxShadow: "inset 0 0 0 1px rgba(255,255,255,.6)",
        maskImage: "radial-gradient(circle, #000 64%, rgba(0,0,0,.55) 70%, transparent 71%)",
      }}
    />
  );
}
