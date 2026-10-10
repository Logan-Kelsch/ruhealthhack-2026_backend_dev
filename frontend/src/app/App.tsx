import { useEffect, useState } from "react";
import { api, type ApiClient } from "../api/client";
import type { Go, GoOpts, ScreenId, StudioTab, VisitNumber } from "./types";
import { caseRouteFromSearch, hrefFor, screenFromHash } from "./types";
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
  const initial = screenFromHash(window.location.hash) ?? "welcome";
  const initialCase = caseRouteFromSearch(window.location.search);
  const [screen, setScreen] = useState<ScreenId>(initial);
  const [visit, setVisit] = useState<VisitNumber>(1);
  const [studioTab, setStudioTab] = useState<StudioTab>("patient");
  const [caseId, setCaseId] = useState<string | undefined>(initialCase.caseId);
  const [version, setVersion] = useState<number | undefined>(initialCase.version);

  const go: Go = (next, opts?: GoOpts) => {
    setScreen(next);
    if (opts?.visit) setVisit(opts.visit);
    if (opts?.studioTab) setStudioTab(opts.studioTab);
    // Only a navigation that names a case keeps one. New case and other screens do not.
    const nextCaseId = opts?.caseId;
    const nextVersion = nextCaseId === undefined ? undefined : opts?.version;
    setCaseId(nextCaseId);
    setVersion(nextVersion);
    window.history.replaceState(null, "", hrefFor(next, { ...opts, caseId: nextCaseId, version: nextVersion }));
  };

  // A full navigation to /#screen reloads and picks this up in the initial state.
  // A hash-only change (the address bar, or a link) does not reload, so listen for it.
  useEffect(() => {
    const onHash = () => {
      const next = screenFromHash(window.location.hash);
      if (next) setScreen(next);
      const selected = caseRouteFromSearch(window.location.search);
      setCaseId(selected.caseId);
      setVersion(selected.version);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const body = renderScreen(screen, go, visit, studioTab, caseId, version, client);
  if (screen === "welcome") return body;
  return (
    <Shell screen={screen} go={go}>
      {body}
    </Shell>
  );
}

// Pick the screen body. The studio also receives the case id from the URL.
function renderScreen(
  screen: ScreenId,
  go: Go,
  visit: VisitNumber,
  studioTab: StudioTab,
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
      return <ImportPatients go={go} />;
    case "f-studio":
      return <CaseStudio go={go} tab={studioTab} caseId={caseId} version={version} client={client} />;
    case "s-home":
      return <StudentHome go={go} />;
    case "s-brief":
      return <Briefing go={go} visit={visit} />;
    case "s-mic":
      return <MicCheck go={go} />;
    case "s-encounter":
      return <Encounter go={go} visit={visit} />;
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
