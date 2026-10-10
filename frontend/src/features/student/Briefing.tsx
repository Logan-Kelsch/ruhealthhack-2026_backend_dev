import { useEffect, useState } from "react";
import { asApiError, api, type ApiClient, type PublicCase } from "../../api/client";
import type { Go, StudentRoute } from "../../app/types";
import { Avatar } from "../../components/Avatar";
import { ArrowRight, MicIcon } from "../../components/Icons";
import { BackLink, Card, CardHead, GhostButton, Page, PrimaryButton } from "../../components/ui";
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
      <Page width="max-w-[820px]">
        <BackLink label="Cases" onClick={() => go("s-home")} />
        <p className="text-sm text-muted">Choose a published case.</p>
      </Page>
    );
  }

  return (
    <Page width="max-w-[820px]">
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
    </Page>
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
    return <p className="text-sm text-muted">Loading the briefing</p>;
  }
  if (load.kind === "error") {
    return (
      <div className="flex flex-col items-start gap-3">
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
      <header className="flex items-center gap-[18px]">
        <Avatar who={portraitFor(detail.patient)} size={72} />
        <div>
          <div className="text-[13px] font-semibold text-indigo">{visit ? visit.label : "Visit"}</div>
          <h1 className="m-0 mt-0.5 font-serif text-[38px] leading-none font-medium tracking-[-0.8px]">
            {detail.patient.name}, {detail.patient.age}
          </h1>
        </div>
      </header>
      <section className="rounded-2xl bg-panel px-6 py-5 text-white">
        <div className="text-xs font-semibold tracking-[0.6px] text-indigo-on-ink uppercase">Your goal</div>
        <div className="mt-1.5 font-serif text-2xl leading-snug text-pretty">{detail.briefing.goal}</div>
      </section>
      <Card>
        <FactRow label="Your role" value={detail.briefing.student_role} />
        <FactRow label="Setting" value={detail.briefing.setting} />
        <FactRow label="Reason for visit" value={detail.briefing.reason_for_visit} />
      </Card>
      {detail.briefing.show_doorway_vitals ? (
        <Card>
          <CardHead title="Doorway vitals" className="px-5 py-3.5" />
          <div className="grid [grid-template-columns:repeat(auto-fit,minmax(140px,1fr))]">
            {(detail.doorway_vitals ?? []).map((vital) => (
              <div key={vital.key} className="border-r border-hair px-5 py-3.5">
                <div className="text-[12.5px] text-muted">{vital.label}</div>
                <div className="mt-1 text-[22px] font-semibold tracking-[-0.4px] tabular-nums">
                  {vital.value} {vital.unit}
                </div>
                <div className="mt-0.5 text-xs text-ink-soft">Source: {vital.source.kind}</div>
              </div>
            ))}
          </div>
        </Card>
      ) : null}
      <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
        <div className="flex items-center gap-2.5 text-[13px] text-ink-soft">
          <MicIcon />
          The microphone is not available yet.
        </div>
        <PrimaryButton size="lg" onClick={onStart}>
          {starting ? "Starting" : "Start encounter"}
          <ArrowRight />
        </PrimaryButton>
      </div>
      {startError ? <p className="text-sm text-danger">{startError}</p> : null}
    </>
  );
}

// One briefing row. Empty values stay blank rather than being filled from the Studio case.
function FactRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[160px_minmax(0,1fr)] gap-4 border-t border-hair px-5 py-3.5 first:border-t-0">
      <span className="text-[13px] text-muted">{label}</span>
      <span className="text-[14.5px] leading-snug">{value}</span>
    </div>
  );
}
