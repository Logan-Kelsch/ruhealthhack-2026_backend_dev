import { useEffect, useState, type ReactNode } from "react";
import { asApiError, api, type ApiClient, type PublicCase } from "../../api/client";
import type { Go, StudentRoute } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { ArrowRight, MicIcon } from "../../components/Icons";
import { BackLink, GhostButton } from "../../components/ui";
import { DocIcon } from "../../components/Icons";
import { portraitFor } from "./portrait";

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; detail: PublicCase };

// Doorway card from the public case. Starting the encounter is a separate button.
export function Briefing({ go, route, client = api }: { go: Go; route: StudentRoute; client?: ApiClient }) {
  const [attempt, setAttempt] = useState(0);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [load, setLoad] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    if (!route.caseId) return;
    let cancelled = false;
    setLoad({ kind: "loading" });
    const caseId = route.caseId;
    client
      .GET("/api/cases/{case_id}", {
        params: {
          path: { case_id: caseId },
          query: {
            version: route.version ?? undefined,
            visit_id: route.visitId ?? undefined,
          },
        },
      })
      .then((result) => {
        if (cancelled) return;
        if (!result.response?.ok || !result.data) {
          const status = result.response?.status ?? 0;
          setLoad({ kind: "error", message: asApiError(status, result.error).message });
          return;
        }
        setLoad({ kind: "ready", detail: result.data });
      })
      .catch(() => {
        if (!cancelled) setLoad({ kind: "error", message: "The briefing could not be loaded." });
      });
    return () => {
      cancelled = true;
    };
  }, [client, route.caseId, route.version, route.visitId, attempt]);

  if (!route.caseId) {
    return (
      <Scene>
        <BackLink label="Cases" onClick={() => go("s-home")} />
        <p className="mt-4 text-sm text-muted">Choose a published case.</p>
      </Scene>
    );
  }

  return (
    <Scene>
      <BackLink label="Cases" onClick={() => go("s-home")} />
      <BriefingBody
        load={load}
        starting={starting}
        startError={startError}
        onRetry={() => setAttempt((value) => value + 1)}
        visitId={route.visitId}
        onStart={() => {
          if (load.kind !== "ready" || starting) return;
          void startEncounter(client, load.detail, route.visitId, go, setStarting, setStartError);
        }}
      />
    </Scene>
  );
}

// The briefing is one card standing on the clinic street painting.
function Scene({ children }: { children: ReactNode }) {
  return (
    <div className="rnd-enter flex min-h-full items-start justify-center px-[clamp(16px,4vw,64px)] pt-2 pb-10">
      <section className="w-full max-w-[1100px] rounded-[18px] border border-white/80 bg-card/92 p-[clamp(16px,1.8vw,26px)] shadow-[0_30px_80px_-40px_rgba(25,31,92,.6)] backdrop-blur-md">
        {children}
      </section>
    </div>
  );
}

// Saves the encounter, then opens it. The briefing screen itself never creates one on load.
async function startEncounter(
  client: ApiClient,
  detail: PublicCase,
  visitId: string | null,
  go: Go,
  setStarting: (value: boolean) => void,
  setStartError: (value: string | null) => void,
) {
  setStarting(true);
  setStartError(null);
  const chosenVisit = visitId ?? detail.visits[0]?.id ?? null;
  try {
    const result = await client.POST("/api/encounters", {
      body: {
        case_id: detail.case_id,
        version: detail.version,
        visit_id: chosenVisit,
        student_name: "",
        previous_encounter_id: null,
      },
    });
    if (!result.response?.ok || !result.data) {
      const status = result.response?.status ?? 0;
      setStartError(asApiError(status, result.error).message);
      return;
    }
    go("s-encounter", {
      caseId: detail.case_id,
      version: detail.version,
      visitId: result.data.visit_id,
      encounterId: result.data.encounter_id,
    });
  } catch {
    setStartError("The encounter could not be started.");
  } finally {
    setStarting(false);
  }
}

// The fields on the public case. Vitals are the doorway set, with the source beside each value.
function BriefingBody({
  load,
  visitId,
  starting,
  startError,
  onRetry,
  onStart,
}: {
  load: LoadState;
  visitId: string | null;
  starting: boolean;
  startError: string | null;
  onRetry: () => void;
  onStart: () => void;
}) {
  if (load.kind === "loading") {
    return <p className="mt-4 text-sm text-muted">Loading the briefing</p>;
  }
  if (load.kind === "error") {
    return (
      <div className="mt-4 flex flex-col items-start gap-3">
        <p className="text-sm text-ink">{load.message}</p>
        <GhostButton onClick={onRetry}>Retry</GhostButton>
      </div>
    );
  }
  const { detail } = load;
  // The URL names the visit. Fall back to the first visit only when the address has none.
  const visit = detail.visits.find((item) => item.id === visitId) ?? detail.visits[0];
  return (
    <>
      <header className="bg-banner mt-3 flex min-h-[136px] flex-wrap items-center justify-between gap-4 rounded-[14px] px-[clamp(20px,3vw,40px)] py-6">
        <div className="flex items-center gap-5">
          <Avatar who={portraitFor(detail.patient)} size={84} />
          <h1 className="m-0 font-serif text-[clamp(38px,4vw,62px)] leading-none font-normal tracking-[-1.4px] text-[#141a55]">
            {detail.patient.name}, {detail.patient.age}
          </h1>
        </div>
        <span className="rounded-full border border-indigo-line/60 bg-white/80 px-6 py-2.5 font-sans text-[19px] text-[#141a55] backdrop-blur-sm">
          {visit ? visit.label : "Visit"}
        </span>
      </header>

      <div className="mt-4 grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr))]">
        <Tile icon={<PinIcon />} title="Setting">
          {detail.briefing.setting}
        </Tile>
        <Tile icon={<PersonIcon />} title="Your role">
          {detail.briefing.student_role}
        </Tile>
        <Tile icon={<TargetIcon />} title="Goal">
          {detail.briefing.goal}
        </Tile>
        <Tile icon={<DocIcon size={26} />} title="Reason for visit">
          {detail.briefing.reason_for_visit}
        </Tile>
      </div>

      {detail.briefing.show_doorway_vitals ? (
        <div className="mt-4 flex flex-wrap items-center gap-x-10 gap-y-4 rounded-[14px] border border-line px-7 py-5">
          <div className="flex items-center gap-6">
            <IconDot>
              <HeartIcon />
            </IconDot>
            <span className="font-serif text-[26px] tracking-[-0.3px]">Doorway vitals</span>
          </div>
          <div className="flex flex-1 flex-wrap gap-y-3">
            {(detail.doorway_vitals ?? []).map((vital) => (
              <div key={vital.key} className="min-w-[110px] flex-1 border-l border-line px-5 first:border-l-0">
                <div className="font-sans text-[15px] text-ink-soft">{vital.label}</div>
                <div className="font-serif text-[28px] tabular-nums">
                  {vital.value} <span className="text-[18px] text-ink-soft">{vital.unit}</span>
                </div>
                <div className="font-sans text-[12px] text-muted">Source: {vital.source.kind}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-4 flex items-center justify-center gap-5 rounded-[14px] bg-indigo-soft/80 px-6 py-3.5 font-sans text-[17px]">
        <span className="flex size-12 items-center justify-center rounded-full bg-card text-ink">
          <MicIcon size={24} />
        </span>
        Your microphone stays on during the visit. There is no typing.
      </div>

      <div className="mt-5 flex flex-col items-center gap-3">
        <button
          type="button"
          onClick={onStart}
          disabled={starting}
          className="inline-flex h-[64px] w-full max-w-[480px] items-center justify-center gap-4 rounded-xl bg-panel font-serif text-[28px] text-white shadow-[0_16px_34px_-18px_rgba(37,45,120,.9)] hover:bg-ink disabled:opacity-60"
        >
          {starting ? "Starting" : "Start encounter"}
          <ArrowRight />
        </button>
        {startError ? <p className="text-sm text-danger">{startError}</p> : null}
      </div>
    </>
  );
}

function Tile({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div className="flex items-center gap-6 rounded-[14px] border border-line px-7 py-5">
      <IconDot>{icon}</IconDot>
      <div>
        <div className="font-serif text-[26px] leading-tight tracking-[-0.3px]">{title}</div>
        <div className="mt-1 font-sans text-[18px] leading-snug text-ink">{children}</div>
      </div>
    </div>
  );
}

function IconDot({ children }: { children: ReactNode }) {
  return <span className="flex size-[60px] shrink-0 items-center justify-center rounded-full bg-indigo-soft text-ink">{children}</span>;
}

function PinIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M12 2.5a7 7 0 0 0-7 7c0 5 7 12 7 12s7-7 7-12a7 7 0 0 0-7-7zm0 9.6a2.6 2.6 0 1 1 0-5.2 2.6 2.6 0 0 1 0 5.2z" />
    </svg>
  );
}

function PersonIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <circle cx="12" cy="8" r="4.2" />
      <path d="M3.8 21c0-4.6 3.7-7.6 8.2-7.6s8.2 3 8.2 7.6z" />
    </svg>
  );
}

function TargetIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.4" fill="currentColor" />
    </svg>
  );
}

function HeartIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" aria-hidden>
      <path d="M12 20s-7.5-4.6-7.5-10.1A4.3 4.3 0 0 1 12 7.3a4.3 4.3 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z" />
    </svg>
  );
}
