import { useEffect, useState } from "react";
import { asApiError, api, type ApiClient, type PublicEncounter } from "../../api/client";
import type { components } from "../../api/schema";
import type { Go, StudentRoute } from "../../app/types";
import { ArrowRight } from "../../components/Icons";
import { Page, PageHeader, PrimaryButton } from "../../components/ui";

type FeedbackResponse = components["schemas"]["FeedbackResponse"];
type BranchSummary = components["schemas"]["BranchSummary"];

// What the completed visit selected, then the door into the next visit. Hidden facts stay on the server.
export function BetweenVisits({ go, route, client = api }: { go: Go; route: StudentRoute; client?: ApiClient }) {
  const [attempt, setAttempt] = useState(0);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(route.encounterId));
  const [encounter, setEncounter] = useState<PublicEncounter | null>(null);
  const [taken, setTaken] = useState<BranchSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!route.encounterId) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    const encounterId = route.encounterId;
    setLoading(true);
    // Read the finished visit and its debrief. This screen does not start the next one.
    Promise.all([
      client.GET("/api/encounters/{enc_id}", { params: { path: { enc_id: encounterId } } }),
      client.GET("/api/encounters/{enc_id}/feedback", { params: { path: { enc_id: encounterId } } }),
    ])
      .then(([encounterResult, feedbackResult]) => {
        if (cancelled) return;
        if (encounterResult.data) {
          setEncounter(encounterResult.data);
        } else {
          setError(asApiError(encounterResult.response?.status ?? 0, encounterResult.error).message);
        }
        if (feedbackResult.data) {
          setTaken(outcomeTaken(feedbackResult.data));
        } else {
          setError(asApiError(feedbackResult.response?.status ?? 0, feedbackResult.error).message);
        }
      })
      .catch(() => {
        if (!cancelled) setError("The visit could not be loaded.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [client, route.encounterId, attempt]);

  if (!route.encounterId) {
    return <p className="px-6 py-8 text-sm text-muted">Choose a completed visit to see what happens next.</p>;
  }

  const patient = encounter?.patient;
  const title = patient ? `${patient.name}, ${patient.age}` : "Between visits";

  return (
    <Page width="max-w-[720px]">
      <PageHeader kicker={encounter?.visit_label ?? "Between visits"} title={title} />
      {loading ? <p className="text-sm text-muted">Loading the visit</p> : null}
      {error ? <p className="text-sm text-ink">{error}</p> : null}
      {taken ? <TakenOutcome taken={taken} /> : null}
      {encounter && !encounter.has_next_visit ? <p className="text-sm text-ink">No further visit is available.</p> : null}
      {encounter?.has_next_visit ? (
        <PrimaryButton
          size="lg"
          className="w-fit"
          onClick={() => {
            void startFollowUp(client, encounter, go, setStarting, setStartError);
          }}
        >
          {starting ? "Starting" : "Start the next visit"}
          <ArrowRight />
        </PrimaryButton>
      ) : null}
      {startError ? <p className="text-sm text-ink">{startError}</p> : null}
      {!loading && error ? (
        <button type="button" onClick={() => setAttempt((value) => value + 1)} className="h-10 w-fit rounded-[10px] border border-line-2 px-4 text-sm font-medium">
          Retry
        </button>
      ) : null}
    </Page>
  );
}

// The outcome the debrief stored. Other branches are already on the debrief and are not repeated here.
function outcomeTaken(feedback: FeedbackResponse): BranchSummary | null {
  return feedback.decision_path.taken ?? null;
}

// The path that was selected, in the faculty member's words. Chart edits for later visits are not copied here.
function TakenOutcome({ taken }: { taken: BranchSummary }) {
  return (
    <section aria-label="Path taken" className="rounded-2xl border border-line bg-card px-5 py-4">
      <h2 className="text-[15px] font-semibold">{taken.label}</h2>
      {taken.summary ? <p className="mt-2 text-[15px] leading-snug">{taken.summary}</p> : null}
      {(taken.evidence ?? []).map((span) => (
        <p key={`${span.turn}-${span.quote}`} className="mt-1 text-sm text-ink-soft">
          Turn {span.turn}: {span.quote}
        </p>
      ))}
    </section>
  );
}

// Opens the next visit from this encounter. A refusal stays on this screen.
async function startFollowUp(
  client: ApiClient,
  encounter: PublicEncounter,
  go: Go,
  setStarting: (value: boolean) => void,
  setStartError: (value: string | null) => void,
) {
  setStarting(true);
  setStartError(null);
  try {
    const result = await client.POST("/api/encounters", {
      body: {
        case_id: encounter.case_id,
        version: encounter.case_version,
        visit_id: null,
        student_name: "",
        previous_encounter_id: encounter.encounter_id,
      },
    });
    if (!result.response?.ok || !result.data) {
      setStartError(asApiError(result.response?.status ?? 0, result.error).message);
      return;
    }
    go("s-brief", {
      caseId: result.data.case_id,
      version: result.data.case_version,
      visitId: result.data.visit_id,
      encounterId: result.data.encounter_id,
    });
  } catch {
    setStartError("The next visit could not be started.");
  } finally {
    setStarting(false);
  }
}
