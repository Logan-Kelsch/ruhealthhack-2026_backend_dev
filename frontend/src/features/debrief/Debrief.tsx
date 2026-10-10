import { useEffect, useState } from "react";
import { asApiError, api, type ApiClient, type PublicEncounter } from "../../api/client";
import type { components } from "../../api/schema";
import type { Go, StudentRoute } from "../../app/types";
import { Page, PageHeader, PrimaryButton } from "../../components/ui";

type FeedbackResponse = components["schemas"]["FeedbackResponse"];
type RubricResult = components["schemas"]["RubricResult"];
type DomainScore = components["schemas"]["DomainScore"];
type ScoreValue = DomainScore["score"];

// The debrief is the first place trust, scores, and the note check are shown.
export function Debrief({ go, route, client = api }: { go: Go; route: StudentRoute; client?: ApiClient }) {
  const [attempt, setAttempt] = useState(0);
  const [loading, setLoading] = useState(Boolean(route.encounterId));
  const [encounter, setEncounter] = useState<PublicEncounter | null>(null);
  const [feedback, setFeedback] = useState<FeedbackResponse | null>(null);
  const [encounterError, setEncounterError] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  useEffect(() => {
    if (!route.encounterId) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    const encounterId = route.encounterId;
    setLoading(true);
    // Read the saved visit and its debrief. Neither call starts an encounter.
    Promise.all([
      client.GET("/api/encounters/{enc_id}", { params: { path: { enc_id: encounterId } } }),
      client.GET("/api/encounters/{enc_id}/feedback", { params: { path: { enc_id: encounterId } } }),
    ])
      .then(([encounterResult, feedbackResult]) => {
        if (cancelled) return;
        if (encounterResult.data) {
          setEncounter(encounterResult.data);
          setEncounterError(null);
        } else {
          setEncounterError(asApiError(encounterResult.response?.status ?? 0, encounterResult.error).message);
        }
        if (feedbackResult.data) {
          setFeedback(feedbackResult.data);
          setFeedbackError(null);
        } else {
          // Keep a debrief we already showed. A failed refresh must not replace it with an empty score.
          setFeedbackError(asApiError(feedbackResult.response?.status ?? 0, feedbackResult.error).message);
        }
      })
      .catch(() => {
        if (!cancelled) setFeedbackError("Feedback could not be loaded.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [client, route.encounterId, attempt]);

  if (!route.encounterId) {
    return <p className="px-6 py-8 text-sm text-muted">This visit has not been started.</p>;
  }

  const patient = encounter?.patient;
  const title = patient ? `${patient.name}, ${patient.age}` : "Feedback";
  const saved = encounter?.saved_documentation ?? null;

  return (
    <Page width="max-w-[1180px]">
      <PageHeader kicker={encounter?.visit_label ?? "Feedback"} title={title}>
        <PrimaryButton size="lg" onClick={() => go("s-home")}>
          Back to home
        </PrimaryButton>
      </PageHeader>
      {loading ? <p className="text-sm text-muted">Loading feedback</p> : null}
      {encounterError ? <p className="text-sm text-ink">{encounterError}</p> : null}
      {feedbackError ? <p className="text-sm text-ink">{feedbackError}</p> : null}
      {saved ? <SavedNote saved={saved} /> : null}
      {feedback ? <FeedbackBody feedback={feedback} /> : null}
      {!loading && (encounterError || feedbackError) ? (
        <button type="button" onClick={() => setAttempt((value) => value + 1)} className="h-10 w-fit rounded-[10px] border border-line-2 px-4 text-sm font-medium">
          Retry
        </button>
      ) : null}
    </Page>
  );
}

// The note that was already stored. It stays on screen when the score request fails.
function SavedNote({ saved }: { saved: Record<string, string> }) {
  const entries = Object.entries(saved).filter(([, value]) => value.trim());
  if (entries.length === 0) return null;
  return (
    <section aria-label="Saved documentation" className="rounded-2xl border border-line bg-card px-5 py-4">
      <h2 className="text-[15px] font-semibold">Saved documentation</h2>
      {entries.map(([field, value]) => (
        <p key={field} className="mt-2 text-[15px] leading-snug">
          <span className="font-semibold">{field}. </span>
          {value}
        </p>
      ))}
    </section>
  );
}

// Scores, evidence, trust, and the note check from the saved feedback response.
function FeedbackBody({ feedback }: { feedback: FeedbackResponse }) {
  const rubric = feedback.rubric;
  return (
    <div className="flex flex-col gap-4">
      <section aria-label="Rubric" className="rounded-2xl border border-line bg-card px-5 py-4">
        <h2 className="text-[15px] font-semibold">{rubric.rubric_title}</h2>
        <p className="mt-2 text-[28px] font-semibold tracking-[-0.6px]">
          {rubric.total} <span className="text-base font-medium text-muted">/ {rubric.max_total}</span>
        </p>
        <p className="mt-1 text-sm leading-snug text-ink-soft">{rubric.interpretation}</p>
        {rubric.review_flag ? (
          <p className="mt-3 text-sm font-semibold text-ink">
            Needs review. {(rubric.review_reasons ?? []).join(". ")}
          </p>
        ) : null}
        <div className="mt-4 flex flex-col">
          {rubric.domains.map((domain) => (
            <DomainRow key={domain.key} domain={domain} />
          ))}
        </div>
      </section>
      <NoteList title="What you did well" items={strengthLines(rubric)} empty="No strengths were recorded." />
      <NoteList title="What to improve" items={gapLines(rubric)} empty="No gaps were recorded." />
      <NoteList title="Try this next time" items={rubric.next_attempt ?? []} empty="No next attempt was recorded." />
      <SafetyList feedback={feedback} />
      <ElicitedList feedback={feedback} />
      <MetricList feedback={feedback} />
      <TrustList feedback={feedback} />
      <DocumentationCheck feedback={feedback} />
      {(feedback.communication_notes ?? []).length > 0 ? (
        <NoteList title="Communication notes" items={feedback.communication_notes ?? []} empty="" />
      ) : null}
      <TranscriptList feedback={feedback} />
    </div>
  );
}

// One domain. The number is written out so the score is not only a colored bar.
function DomainRow({ domain }: { domain: DomainScore }) {
  const flagged = (domain.id === 6 || domain.id === 7) && domain.score === 1;
  return (
    <div className="border-t border-hair py-3 first:border-t-0">
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-[15px]">{domain.name}</span>
        <span className={`text-[15px] font-semibold ${domain.score === 1 ? "text-danger" : "text-ink"}`}>
          {scoreLabel(domain.score)}
          {flagged ? <span className="ml-2 text-sm font-semibold text-ink">Needs review</span> : null}
        </span>
      </div>
      {(domain.evidence ?? []).map((span) => (
        <p key={`${span.turn}-${span.quote}`} className="mt-1 text-sm text-ink-soft">
          Turn {span.turn}: {span.quote}
        </p>
      ))}
      {domain.safety_or_accuracy_concern ? <p className="mt-1 text-sm">{domain.safety_or_accuracy_concern}</p> : null}
    </div>
  );
}

// Turns the official score into words. N/A is not shown as zero.
function scoreLabel(score: ScoreValue): string {
  if (score === "N/A") return "N/A";
  return `${score} / 4`;
}

// Domain comments plus the short list. Blank lines are left out so the screen does not invent one.
function strengthLines(rubric: RubricResult): string[] {
  const fromDomains = rubric.domains.map((domain) => domain.strength_demonstrated.trim()).filter(Boolean);
  const fromList = (rubric.strengths ?? []).map((item) => item.text.trim()).filter(Boolean);
  return [...fromDomains, ...fromList];
}

// Gaps from the domain comments and the improvement list.
function gapLines(rubric: RubricResult): string[] {
  const fromDomains = rubric.domains.map((domain) => domain.important_gap_or_missed_opportunity.trim()).filter(Boolean);
  const fromList = (rubric.improvements ?? []).map((item) => item.text.trim()).filter(Boolean);
  return [...fromDomains, ...fromList];
}

// A heading and the lines under it. An empty list says so instead of filling in an example.
function NoteList({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  const lines = items.map((item) => item.trim()).filter(Boolean);
  return (
    <section className="rounded-2xl border border-line bg-card px-5 py-4">
      <h2 className="text-[15px] font-semibold">{title}</h2>
      {lines.length === 0 ? <p className="mt-2 text-sm text-muted">{empty}</p> : null}
      {lines.map((line) => (
        <p key={line} className="mt-2 text-[15px] leading-snug">
          {line}
        </p>
      ))}
    </section>
  );
}

// Safety facts from the case, with words for found and addressed so color is not the only signal.
function SafetyList({ feedback }: { feedback: FeedbackResponse }) {
  const items = feedback.safety ?? [];
  return (
    <section aria-label="Safety" className="rounded-2xl border border-line bg-card px-5 py-4">
      <h2 className="text-[15px] font-semibold">Safety</h2>
      {items.length === 0 ? <p className="mt-2 text-sm text-muted">No safety items were recorded.</p> : null}
      {items.map((item) => (
        <div key={item.fact_id} className="mt-3 text-[15px] leading-snug">
          <div>
            Fact {item.fact_id}. {item.text}
          </div>
          <div className="text-sm text-ink-soft">
            {item.discovered ? "Found" : "Not found"}
            {item.addressed === null || item.addressed === undefined ? "" : item.addressed ? ". Addressed" : ". Not addressed"}
          </div>
          {item.patient_words ? <div className="text-sm text-ink-soft">{item.patient_words}</div> : null}
        </div>
      ))}
    </section>
  );
}

// What the student elicited and what stayed missing, each with its fact id.
function ElicitedList({ feedback }: { feedback: FeedbackResponse }) {
  return (
    <section aria-label="Elicited and missed" className="rounded-2xl border border-line bg-card px-5 py-4">
      <h2 className="text-[15px] font-semibold">Elicited and missed</h2>
      {feedback.elicited.map((objective) => (
        <div key={objective.objective_id} className="mt-3">
          <div className="text-sm font-semibold">{objective.objective}</div>
          {(objective.found ?? []).map((item) => (
            <p key={item.fact_id} className="mt-1 text-[15px] leading-snug">
              Found. Fact {item.fact_id}. Turn {item.turn}. {item.text}
            </p>
          ))}
          {(objective.missed ?? []).map((item) => (
            <p key={item.fact_id} className="mt-1 text-[15px] leading-snug">
              Missed. Fact {item.fact_id}. {item.text} {item.suggestion}
            </p>
          ))}
        </div>
      ))}
    </section>
  );
}

// The counts the pipeline stored. Null ratios are skipped rather than shown as zero.
function MetricList({ feedback }: { feedback: FeedbackResponse }) {
  const metrics = feedback.metrics;
  const rows: string[] = [
    `Turns: ${metrics.turns}`,
    `Open questions: ${metrics.open_questions}`,
    `Closed questions: ${metrics.closed_questions}`,
    `Reflections: ${metrics.reflections}`,
    `Validations: ${metrics.validations}`,
    `Interruptions: ${metrics.interruptions}`,
  ];
  if (metrics.percent_open !== null && metrics.percent_open !== undefined) rows.push(`Open question share: ${metrics.percent_open}%`);
  if (metrics.reflection_to_question_ratio !== null && metrics.reflection_to_question_ratio !== undefined) {
    rows.push(`Reflection to question ratio: ${metrics.reflection_to_question_ratio}`);
  }
  if (metrics.student_talk_share !== null && metrics.student_talk_share !== undefined) {
    rows.push(`Student talk share: ${metrics.student_talk_share}%`);
  }
  for (const jargon of metrics.unexplained_jargon ?? []) {
    rows.push(`Unexplained jargon: ${jargon.term}. ${jargon.quote}`);
  }
  return (
    <section aria-label="Communication" className="rounded-2xl border border-line bg-card px-5 py-4">
      <h2 className="text-[15px] font-semibold">Communication</h2>
      {rows.map((row) => (
        <p key={row} className="mt-1 text-[15px] leading-snug">
          {row}
        </p>
      ))}
    </section>
  );
}

// Trust is listed here with the words that changed it. The visit screen does not render this.
function TrustList({ feedback }: { feedback: FeedbackResponse }) {
  return (
    <section aria-label="Trust" className="rounded-2xl border border-line bg-card px-5 py-4">
      <h2 className="text-[15px] font-semibold">Trust</h2>
      {feedback.trust_timeline.map((point) => (
        <div key={point.turn} className="mt-3">
          <div className="text-[15px]">
            Turn {point.turn}: trust {point.trust}
          </div>
          {(point.events ?? []).map((event) => (
            <blockquote key={`${event.turn}-${event.event}-${event.span}`} className="mt-1 text-sm text-ink-soft">
              “{event.span}”
            </blockquote>
          ))}
        </div>
      ))}
    </section>
  );
}

// Unsupported claims and missing findings, including the fact or chart id the check kept.
function DocumentationCheck({ feedback }: { feedback: FeedbackResponse }) {
  const check = feedback.documentation;
  return (
    <section aria-label="Documentation check" className="rounded-2xl border border-line bg-card px-5 py-4">
      <h2 className="text-[15px] font-semibold">Documentation check</h2>
      {!check ? <p className="mt-2 text-sm text-muted">No documentation check was saved.</p> : null}
      {(check?.unsupported ?? []).map((claim) => (
        <p key={claim.statement} className="mt-2 text-[15px] leading-snug">
          Unsupported. {claim.statement} {claim.reason}
        </p>
      ))}
      {(check?.missing ?? []).map((item) => (
        <p key={item.id} className="mt-2 text-[15px] leading-snug">
          Missing. Fact {item.id}. {item.text}
        </p>
      ))}
      {check && (check.unsupported ?? []).length === 0 && (check.missing ?? []).length === 0 ? (
        <p className="mt-2 text-sm text-muted">No unsupported claims or missing findings were flagged.</p>
      ) : null}
    </section>
  );
}

// The transcript the scores cite. Captions stay visible with the feedback.
function TranscriptList({ feedback }: { feedback: FeedbackResponse }) {
  return (
    <section aria-label="Transcript" className="rounded-2xl border border-line bg-card px-5 py-4">
      <h2 className="text-[15px] font-semibold">Transcript</h2>
      {feedback.transcript.map((line) => (
        <div key={line.turn} className="mt-3 text-[15px] leading-snug">
          <div>Turn {line.turn}</div>
          <div>Student: {line.student}</div>
          <div>Patient: {line.patient}</div>
        </div>
      ))}
    </section>
  );
}
