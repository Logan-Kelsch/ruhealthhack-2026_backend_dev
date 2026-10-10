import { useEffect, useState } from "react";
import { api, type ApiClient } from "../api/client";
import type { Go, GoOpts, ScreenId, StudentRoute, StudioTab } from "./types";
import { caseRouteFromSearch, hrefFor, parseHash, routeForScreen, writeHash } from "./types";
import { Shell } from "../components/Shell";
import { Welcome } from "../features/welcome/Welcome";
import { FacultyHome } from "../features/faculty/FacultyHome";
import { CaseLibrary } from "../features/faculty/CaseLibrary";
import { ImportPatients } from "../features/faculty/ImportPatients";
import { CaseStudio } from "../features/faculty/CaseStudio";
import { StudentHome } from "../features/student/StudentHome";
import { Briefing } from "../features/student/Briefing";
import { MicCheck } from "../features/student/MicCheck";
import { Encounter } from "../features/encounter/Encounter";
import { Debrief } from "../features/debrief/Debrief";
import { BetweenVisits } from "../features/student/BetweenVisits";

// One place owns the screen, the visit number, the studio tab, and the open case.
// Screens call `go` instead of using a router, matching the design file's navigation.
export function App({ client = api }: { client?: ApiClient }) {
  const initial = parseHash(window.location.hash);
  const initialCase = caseRouteFromSearch(window.location.search);
  const [screen, setScreen] = useState<ScreenId>(initial.screen ?? "welcome");
  const [studioTab, setStudioTab] = useState<StudioTab>("patient");
  // Student visit ids live in the hash. Faculty case ids live in the page search.
  const [route, setRoute] = useState<StudentRoute>(initial.route);
  const [caseId, setCaseId] = useState<string | undefined>(initialCase.caseId);
  const [version, setVersion] = useState<number | undefined>(initialCase.version);

  const go: Go = (next, opts?: GoOpts) => {
    const updated = routeForScreen(next, route, opts);
    setScreen(next);
    setRoute(updated);
    if (opts?.studioTab) setStudioTab(opts.studioTab);
    const studentUrl = updated.caseId !== null || updated.encounterId !== null;
    if (studentUrl) {
      // A student visit does not keep a faculty case in the page search.
      setCaseId(undefined);
      setVersion(undefined);
      window.history.replaceState(null, "", `/${writeHash(next, updated)}`);
      return;
    }
    // Only a navigation that names a case keeps one. New case and other screens do not.
    const nextCaseId = opts?.caseId;
    const nextVersion = nextCaseId === undefined ? undefined : opts?.version;
    setCaseId(nextCaseId);
    setVersion(nextVersion);
    window.history.replaceState(null, "", hrefFor(next, { caseId: nextCaseId, version: nextVersion }));
  };

  // A full navigation reloads and picks this up in the initial state.
  // A hash-only change (the address bar, or a link) does not reload, so listen for it.
  useEffect(() => {
    const onHash = () => {
      const next = parseHash(window.location.hash);
      if (next.screen) setScreen(next.screen);
      setRoute(next.route);
      const selected = caseRouteFromSearch(window.location.search);
      setCaseId(selected.caseId);
      setVersion(selected.version);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const body = renderScreen(screen, go, studioTab, route, caseId, version, client);
  if (screen === "welcome") return body;
  return (
    <Shell screen={screen} go={go}>
      {body}
    </Shell>
  );
}

// Picks the screen. Faculty studio reads the search case. Student screens read the hash route.
function renderScreen(
  screen: ScreenId,
  go: Go,
  studioTab: StudioTab,
  route: StudentRoute,
  caseId: string | undefined,
  version: number | undefined,
  client: ApiClient,
) {
  switch (screen) {
    case "welcome":
      return <Welcome go={go} />;
    case "f-home":
      return <FacultyHome go={go} />;
    case "f-cases":
      return <CaseLibrary go={go} client={client} />;
    case "f-import":
      return <ImportPatients go={go} client={client} />;
    case "f-studio":
      return <CaseStudio go={go} tab={studioTab} caseId={caseId} version={version} client={client} />;
    case "s-home":
      return <StudentHome go={go} client={client} />;
    case "s-brief":
      return <Briefing go={go} route={route} client={client} />;
    case "s-mic":
      return <MicCheck go={go} />;
    case "s-encounter":
      return <Encounter route={route} client={client} go={go} />;
    case "s-debrief":
      return <Debrief go={go} route={route} client={client} />;
    case "s-between":
      return <BetweenVisits go={go} />;
    default: {
      const unreachable: never = screen;
      return unreachable;
    }
  }
}
