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

export type StudioTab = "patient" | "objectives" | "files" | "tree" | "review";

export type VisitNumber = 1 | 2;

// Extra state a screen can pass when it navigates, such as which visit or studio tab to open.
export type GoOpts = {
  visit?: VisitNumber;
  studioTab?: StudioTab;
  // Which saved case the faculty member or student picked. These are navigation ids, not API types.
  caseId?: string;
  version?: number;
  visitId?: string;
  encounterId?: string | null;
};

// Identifiers kept in the URL so a refresh can reopen the same visit.
// They are plain strings from the address bar, not generated response types.
export type StudentRoute = {
  caseId: string | null;
  version: number | null;
  visitId: string | null;
  encounterId: string | null;
};

export const emptyStudentRoute: StudentRoute = {
  caseId: null,
  version: null,
  visitId: null,
  encounterId: null,
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

// Reads #screen?case=&version=&visit=&encounter= so refresh can restore the visit.
export function parseHash(hash: string): { screen: ScreenId | null; route: StudentRoute } {
  const raw = hash.replace(/^#/, "");
  const [screenPart, queryPart] = raw.split("?");
  const screen = SCREENS.includes(screenPart as ScreenId) ? (screenPart as ScreenId) : null;
  const params = new URLSearchParams(queryPart ?? "");
  const versionRaw = params.get("version");
  const version = versionRaw !== null && /^\d+$/.test(versionRaw) ? Number(versionRaw) : null;
  return {
    screen,
    route: {
      caseId: params.get("case"),
      version,
      visitId: params.get("visit"),
      encounterId: params.get("encounter"),
    },
  };
}

// Writes the screen and the student ids in a stable order.
export function writeHash(screen: ScreenId, route: StudentRoute): string {
  const params = new URLSearchParams();
  if (route.caseId) params.set("case", route.caseId);
  if (route.version !== null) params.set("version", String(route.version));
  if (route.visitId) params.set("visit", route.visitId);
  if (route.encounterId) params.set("encounter", route.encounterId);
  const query = params.toString();
  return query ? `#${screen}?${query}` : `#${screen}`;
}

// Hash links like #s-encounter let a refresh keep the current screen.
export function screenFromHash(hash: string): ScreenId | null {
  return parseHash(hash).screen;
}

// Student screens keep the case in the URL. Other screens do not carry an encounter forward.
export function routeForScreen(screen: ScreenId, current: StudentRoute, opts?: GoOpts): StudentRoute {
  if (!screen.startsWith("s-") || screen === "s-home") {
    return emptyStudentRoute;
  }
  return {
    caseId: opts?.caseId ?? current.caseId,
    version: opts?.version ?? current.version,
    visitId: opts?.visitId ?? current.visitId,
    // The visit and the debrief reopen the same encounter. Briefing must not resume one by itself.
    encounterId:
      screen === "s-encounter" || screen === "s-debrief" ? (opts?.encounterId ?? current.encounterId) : null,
  };
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
