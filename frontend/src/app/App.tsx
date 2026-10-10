import { useEffect, useState } from "react";
import { api, type ApiClient } from "../api/client";
import type { Go, GoOpts, ScreenId, StudentRoute, StudioTab, VisitNumber } from "./types";
import { parseHash, routeForScreen, writeHash } from "./types";
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

// One place owns the prototype's screen, visit number, and studio tab.
// Screens call `go` instead of using a router, matching the design file's navigation.
export function App({ client = api }: { client?: ApiClient }) {
  const initial = parseHash(window.location.hash);
  const [screen, setScreen] = useState<ScreenId>(initial.screen ?? "welcome");
  const [visit, setVisit] = useState<VisitNumber>(1);
  const [studioTab, setStudioTab] = useState<StudioTab>("patient");
  const [route, setRoute] = useState<StudentRoute>(initial.route);

  const go: Go = (next, opts?: GoOpts) => {
    const updated = routeForScreen(next, route, opts);
    setScreen(next);
    setRoute(updated);
    if (opts?.visit) setVisit(opts.visit);
    if (opts?.studioTab) setStudioTab(opts.studioTab);
    // The hash is what a refresh reads. History state still carries the faculty case id.
    const hash = writeHash(next, updated);
    window.history.replaceState({ caseId: opts?.caseId ?? updated.caseId, version: opts?.version ?? updated.version }, "", hash);
  };

  // A full navigation to /#screen reloads and picks this up in the initial state.
  // A hash-only change (the address bar, or a link) does not reload, so listen for it.
  useEffect(() => {
    const onHash = () => {
      const next = parseHash(window.location.hash);
      if (!next.screen) return;
      setScreen(next.screen);
      setRoute(next.route);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const body = renderScreen(screen, go, visit, studioTab, route, client);
  if (screen === "welcome") return body;
  return (
    <Shell screen={screen} go={go}>
      {body}
    </Shell>
  );
}

// Picks the screen. Student briefing and the encounter receive the URL route and the shared client.
function renderScreen(
  screen: ScreenId,
  go: Go,
  visit: VisitNumber,
  studioTab: StudioTab,
  route: StudentRoute,
  client: ApiClient,
) {
  switch (screen) {
    case "welcome":
      return <Welcome go={go} />;
    case "f-home":
      return <FacultyHome go={go} />;
    case "f-cases":
      return <CaseLibrary go={go} />;
    case "f-import":
      return <ImportPatients go={go} />;
    case "f-studio":
      return <CaseStudio go={go} tab={studioTab} />;
    case "s-home":
      return <StudentHome go={go} client={client} />;
    case "s-brief":
      return <Briefing go={go} route={route} client={client} />;
    case "s-mic":
      return <MicCheck go={go} />;
    case "s-encounter":
      return <Encounter route={route} client={client} />;
    case "s-debrief":
      return <Debrief go={go} visit={visit} />;
    case "s-between":
      return <BetweenVisits go={go} />;
    default: {
      const unreachable: never = screen;
      return unreachable;
    }
  }
}
