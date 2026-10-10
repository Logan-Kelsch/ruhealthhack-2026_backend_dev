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
  // Which saved case the faculty member picked. This is navigation state, not an API type.
  caseId?: string;
  version?: number;
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
  const id = hash.replace(/^#/, "").split(/[?&]/)[0] as ScreenId;
  return SCREENS.includes(id) ? id : null;
}

export type CaseRoute = {
  caseId?: string;
  version?: number;
};

// The saved case and version stay in the query, so a refresh can open that draft again.
export function caseRouteFromSearch(search: string): CaseRoute {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const caseId = params.get("case")?.trim() || undefined;
  if (!caseId) return {};
  const rawVersion = params.get("version");
  if (rawVersion === null || rawVersion.trim() === "") return { caseId };
  const version = Number(rawVersion);
  // A missing or unreadable version still identifies the case. The API can return the latest.
  if (!Number.isInteger(version) || version < 1) return { caseId };
  return { caseId, version };
}

// A path URL, not a hash-only URL, so a screen change can clear a previous case query.
export function hrefFor(screen: ScreenId, opts?: GoOpts): string {
  const params = new URLSearchParams();
  if (opts?.caseId) {
    params.set("case", opts.caseId);
    if (opts.version !== undefined) params.set("version", String(opts.version));
  }
  const query = params.toString();
  return `/${query ? `?${query}` : ""}#${screen}`;
}
