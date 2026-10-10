import { useEffect, useState } from "react";
import type { Go, GoOpts, ScreenId, StudioTab, VisitNumber } from "./types";
import { screenFromHash } from "./types";
import { ModeTransitionProvider } from "../components/ModeTransition";
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
export function App() {
  const initial = screenFromHash(window.location.hash) ?? "welcome";
  const [screen, setScreen] = useState<ScreenId>(initial);
  const [visit, setVisit] = useState<VisitNumber>(1);
  const [studioTab, setStudioTab] = useState<StudioTab>("patient");

  const go: Go = (next, opts?: GoOpts) => {
    setScreen(next);
    if (opts?.visit) setVisit(opts.visit);
    if (opts?.studioTab) setStudioTab(opts.studioTab);
    window.history.replaceState(null, "", `#${next}`);
  };

  // A full navigation to /#screen reloads and picks this up in the initial state.
  // A hash-only change (the address bar, or a link) does not reload, so listen for it.
  useEffect(() => {
    const onHash = () => {
      const next = screenFromHash(window.location.hash);
      if (next) setScreen(next);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const body = renderScreen(screen, go, visit, studioTab);
  // The welcome screen and the encounter paint their own full-window watercolor.
  const bare = screen === "welcome" || screen === "s-encounter";
  return (
    <ModeTransitionProvider>
      {bare ? (
        body
      ) : (
        <Shell screen={screen} go={go}>
          {body}
        </Shell>
      )}
    </ModeTransitionProvider>
  );
}

function renderScreen(screen: ScreenId, go: Go, visit: VisitNumber, studioTab: StudioTab) {
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
