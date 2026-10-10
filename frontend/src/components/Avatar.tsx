import type { ReactNode } from "react";

type Portrait = "walter" | "alina" | "eli" | "generic";

type AvatarProps = {
  who: Portrait;
  size: number;
};

// Flat illustrated portraits. The design uses photos, which the design API will not export as files.
// These stay clearly drawn so they are not mistaken for photographs of real people.
export function Avatar({ who, size }: AvatarProps) {
  const face = FACES[who];
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 80 80"
      className="shrink-0 rounded-full"
      aria-hidden
    >
      <circle cx="40" cy="40" r="40" fill={face.bg} />
      <ellipse cx="40" cy="86" rx="28" ry="24" fill={face.shirt} />
      <circle cx="40" cy="36" r="16" fill={face.skin} />
      <path d={face.hair} fill={face.hairColor} />
      {face.extra}
    </svg>
  );
}

const FACES: Record<
  Portrait,
  { bg: string; skin: string; shirt: string; hair: string; hairColor: string; extra?: ReactNode }
> = {
  walter: {
    bg: "#d9def4",
    skin: "#e2c2a4",
    shirt: "#3d4a86",
    hair: "M24 34c1-12 8-18 16-18s15 6 16 18c-4-6-10-8-16-8s-12 2-16 8z",
    hairColor: "#c8c2b8",
    extra: <path d="M28 46c4 6 20 6 24 0" stroke="#b89274" strokeWidth="1.4" fill="none" />,
  },
  alina: {
    bg: "#f3d7e4",
    skin: "#c98a62",
    shirt: "#2b3ab8",
    hair: "M22 38c0-16 8-24 18-24s18 8 18 24c-2-10-8-14-18-14s-16 4-18 14z",
    hairColor: "#2a211c",
  },
  eli: {
    bg: "#d7efe2",
    skin: "#f0c9a0",
    shirt: "#1f7a50",
    hair: "M26 34c2-10 7-16 14-16s12 6 14 16c-3-5-8-7-14-7s-11 2-14 7z",
    hairColor: "#5a3a22",
  },
  generic: {
    bg: "#eceef5",
    skin: "#d7b89a",
    shirt: "#6a7099",
    hair: "M25 36c1-11 7-16 15-16s14 5 15 16c-3-6-8-8-15-8s-12 2-15 8z",
    hairColor: "#3a332e",
  },
};
