// Screens the Rounds shell can show. Names match the design prototype's go() targets.
export type ScreenId =
  | "welcome"
  | "f-home"
  | "f-cases"
  | "f-import"
  | "f-studio"
  | "s-home"
  | "s-brief"
  | "s-mic"
  | "s-encounter"
  | "s-debrief"
  | "s-between";

export type StudioTab = "patient" | "objectives" | "files" | "tree";

export type VisitNumber = 1 | 2;

// Extra state a screen can pass when it navigates, such as which visit or studio tab to open.
export type GoOpts = {
  visit?: VisitNumber;
  studioTab?: StudioTab;
};

export type Go = (screen: ScreenId, opts?: GoOpts) => void;

const SCREENS: ScreenId[] = [
  "welcome",
  "f-home",
  "f-cases",
  "f-import",
  "f-studio",
  "s-home",
  "s-brief",
  "s-mic",
  "s-encounter",
  "s-debrief",
  "s-between",
];

// Hash links like #s-encounter let a refresh keep the current screen.
export function screenFromHash(hash: string): ScreenId | null {
  const id = hash.replace(/^#/, "") as ScreenId;
  return SCREENS.includes(id) ? id : null;
}
