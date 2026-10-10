import { useEffect, useState } from "react";
import { asApiError, api, type ApiClient, type PublicEncounter } from "../../api/client";
import type { components } from "../../api/schema";
import type { Go } from "../../app/types";
import { GhostButton, Page, PageHeader, PrimaryButton } from "../../components/ui";

type FeedbackResponse = components["schemas"]["FeedbackResponse"];
type DomainScore = components["schemas"]["DomainScore"];
type ScoreValue = DomainScore["score"];
type CommentField = components["schemas"]["CommentOverride"]["field"];
type RubricDomain = components["schemas"]["ScoreOverride"]["domain"];

const RUBRIC_DOMAINS: RubricDomain[] = [
  "opening_and_purpose",
  "rapport_respect_empathy",
  "information_gathering",
  "listening_and_response_to_cues",
  "explanation_and_shared_decisions",
  "clinical_reasoning_and_synthesis",
  "professionalism_safety_closure",
];

const COMMENT_FIELDS: { field: CommentField; label: string }[] = [
  { field: "strength_demonstrated", label: "Strength demonstrated" },
  { field: "important_gap_or_missed_opportunity", label: "Important gap or missed opportunity" },
  { field: "safety_or_accuracy_concern", label: "Safety or accuracy concern" },
];

// Faculty review of one saved encounter. The generated debrief stays visible beside any override.
export function FacultyReview({
  go,
  encounterId,
  client = api,
}: {
  go: Go;
  encounterId: string | null;
  client?: ApiClient;
}) {
  const [attempt, setAttempt] = useState(0);
  const [loading, setLoading] = useState(Boolean(encounterId));
  const [encounter, setEncounter] = useState<PublicEncounter | null>(null);
  const [feedback, setFeedback] = useState<FeedbackResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [score, setScore] = useState("");
  const [comment, setComment] = useState("");
  const [commentField, setCommentField] = useState<CommentField>("safety_or_accuracy_concern");
  const [domain, setDomain] = useState("");

  useEffect(() => {
    if (!encounterId) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    // Read the saved visit and its debrief. Neither call starts an encounter or writes an override.
    Promise.all([
      client.GET("/api/encounters/{enc_id}", { params: { path: { enc_id: encounterId } } }),
      client.GET("/api/encounters/{enc_id}/feedback", { params: { path: { enc_id: encounterId } } }),
    ])
      .then(([encounterResult, feedbackResult]) => {
        if (cancelled) return;
        const problems: string[] = [];
        if (encounterResult.data) {
          setEncounter(encounterResult.data);
        } else {
          problems.push(asApiError(encounterResult.response?.status ?? 0, encounterResult.error).message);
        }
        if (feedbackResult.data) {
          setFeedback(feedbackResult.data);
          const first = feedbackResult.data.rubric.domains[0]?.key;
          if (first) setDomain((current) => current || first);
        } else {
          problems.push(asApiError(feedbackResult.response?.status ?? 0, feedbackResult.error).message);
          // A failed read must not leave a previous encounter's scores on screen.
          setFeedback(null);
        }
        setLoadError(problems[0] ?? null);
      })
      .catch(() => {
        if (!cancelled) setLoadError("Feedback could not be loaded.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [client, encounterId, attempt]);

  if (!encounterId) {
    return <p className="px-6 py-8 text-sm text-muted">Choose a saved encounter to review.</p>;
  }

  const title = encounter?.patient ? `${encounter.patient.name}, ${encounter.patient.age}` : "Review";

  return (
    <Page width="max-w-[980px]">
      <PageHeader kicker={encounter?.visit_label ?? "Review"} title={title}>
        <GhostButton onClick={() => go("f-home")}>Back to encounters</GhostButton>
      </PageHeader>
      {loading ? <p className="text-sm text-muted">Loading feedback</p> : null}
      {loadError ? <p className="text-sm text-ink">{loadError}</p> : null}
      {saveError ? <p className="text-sm text-ink">{saveError}</p> : null}
      {feedback ? (
        <FeedbackReview
          feedback={feedback}
          domain={domain}
          score={score}
          comment={comment}
          commentField={commentField}
          onDomain={setDomain}
          onScore={setScore}
          onComment={setComment}
          onCommentField={setCommentField}
          onSave={() => {
            void saveOverride(client, encounterId, domain || feedback.rubric.domains[0]?.key || "", score, comment, commentField, setFeedback, setSaveError);
          }}
        />
      ) : null}
      {!loading && loadError ? (
        <GhostButton onClick={() => setAttempt((value) => value + 1)}>Retry</GhostButton>
      ) : null}
    </Page>
  );
}

// Send one score or comment. A failure leaves the generated debrief and any earlier override as they were.
async function saveOverride(
  client: ApiClient,
  encounterId: string,
  domain: string,
  score: string,
  comment: string,
  commentField: CommentField,
  setFeedback: (feedback: FeedbackResponse) => void,
  setSaveError: (message: string | null) => void,
) {
  const chosen = chosenScore(score);
  const note = comment.trim();
  const rubricDomain = RUBRIC_DOMAINS.find((key) => key === domain) ?? null;
  if (!rubricDomain || (chosen === null && !note)) {
    setSaveError("Add a score or a comment");
    return;
  }
  try {
    const result = await client.PATCH("/api/encounters/{enc_id}/feedback", {
      params: { path: { enc_id: encounterId } },
      body: {
        scores: chosen === null ? [] : [{ domain: rubricDomain, score: chosen }],
        comments: note ? [{ domain: rubricDomain, field: commentField, text: note }] : [],
      },
    });
    if (!result.response?.ok || !result.data) {
      setSaveError(asApiError(result.response?.status ?? 0, result.error).message);
      return;
    }
    // Only a successful response replaces what is shown as saved.
    setFeedback(result.data);
    setSaveError(null);
  } catch (err) {
    setSaveError(err instanceof Error ? err.message : "That change was not saved.");
  }
}

// The select uses these strings. Anything else is "no score change", not a stored score.
function chosenScore(value: string): ScoreValue | null {
  if (value === "1" || value === "2" || value === "3" || value === "4") return Number(value) as 1 | 2 | 3 | 4;
  if (value === "N/A") return "N/A";
  return null;
}

// The generated rubric, its evidence, and the faculty change when one has been saved.
function FeedbackReview({
  feedback,
  domain,
  score,
  comment,
  commentField,
  onDomain,
  onScore,
  onComment,
  onCommentField,
  onSave,
}: {
  feedback: FeedbackResponse;
  domain: string;
  score: string;
  comment: string;
  commentField: CommentField;
  onDomain: (value: string) => void;
  onScore: (value: string) => void;
  onComment: (value: string) => void;
  onCommentField: (value: CommentField) => void;
  onSave: () => void;
}) {
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
          <p className="mt-3 text-sm font-semibold text-ink">Needs review. {(rubric.review_reasons ?? []).join(". ")}</p>
        ) : null}
        {rubric.domains.map((item) => (
          <DomainReview key={item.key} domain={item} overrides={feedback.overrides ?? null} />
        ))}
      </section>
      <OverrideForm
        domains={rubric.domains}
        domain={domain}
        score={score}
        comment={comment}
        commentField={commentField}
        onDomain={onDomain}
        onScore={onScore}
        onComment={onComment}
        onCommentField={onCommentField}
        onSave={onSave}
      />
    </div>
  );
}

// One generated domain, then the faculty score or comment for that same domain if it was saved.
function DomainReview({
  domain,
  overrides,
}: {
  domain: DomainScore;
  overrides: FeedbackResponse["overrides"];
}) {
  const facultyScore = (overrides?.scores ?? []).find((item) => item.domain === domain.key);
  const facultyComments = (overrides?.comments ?? []).filter((item) => item.domain === domain.key);
  return (
    <div className="border-t border-hair py-3">
      <div className="text-[15px] font-semibold">{domain.name}</div>
      <p className="mt-1 text-sm">Generated score {scoreLabel(domain.score)}</p>
      {(domain.evidence ?? []).map((span) => (
        <p key={`${span.turn}-${span.quote}`} className="mt-1 text-sm text-ink-soft">
          Turn {span.turn}: {span.quote}
        </p>
      ))}
      {domain.safety_or_accuracy_concern ? <p className="mt-1 text-sm">{domain.safety_or_accuracy_concern}</p> : null}
      {domain.important_gap_or_missed_opportunity ? <p className="mt-1 text-sm">{domain.important_gap_or_missed_opportunity}</p> : null}
      {facultyScore ? <p className="mt-2 text-sm font-semibold">Faculty score {scoreLabel(facultyScore.score)}</p> : null}
      {facultyComments.map((item) => (
        <p key={`${item.field}-${item.text}`} className="mt-1 text-sm">
          {item.text}
        </p>
      ))}
    </div>
  );
}

// Turns the official score into words. N/A is not shown as zero.
function scoreLabel(score: ScoreValue): string {
  if (score === "N/A") return "N/A";
  return `${score} / 4`;
}

// The form holds a draft. It is not shown as a faculty score until the save succeeds.
function OverrideForm({
  domains,
  domain,
  score,
  comment,
  commentField,
  onDomain,
  onScore,
  onComment,
  onCommentField,
  onSave,
}: {
  domains: DomainScore[];
  domain: string;
  score: string;
  comment: string;
  commentField: CommentField;
  onDomain: (value: string) => void;
  onScore: (value: string) => void;
  onComment: (value: string) => void;
  onCommentField: (value: CommentField) => void;
  onSave: () => void;
}) {
  return (
    <form
      className="flex flex-col gap-3 rounded-2xl border border-line bg-card px-5 py-4"
      onSubmit={(event) => {
        event.preventDefault();
        onSave();
      }}
    >
      <h2 className="text-[15px] font-semibold">Change a score or comment</h2>
      <label className="flex flex-col gap-1 text-sm">
        Domain
        <select name="domain" value={domain} onChange={(event) => onDomain(event.target.value)} className="h-10 rounded-lg border border-line bg-paper px-2">
          {domains.map((item) => (
            <option key={item.key} value={item.key}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Score
        <select name="score" value={score} onChange={(event) => onScore(event.target.value)} className="h-10 rounded-lg border border-line bg-paper px-2">
          <option value="">No score change</option>
          <option value="1">1</option>
          <option value="2">2</option>
          <option value="3">3</option>
          <option value="4">4</option>
          <option value="N/A">N/A</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Comment field
        <select
          name="commentField"
          value={commentField}
          onChange={(event) => onCommentField(event.target.value as CommentField)}
          className="h-10 rounded-lg border border-line bg-paper px-2"
        >
          {COMMENT_FIELDS.map((item) => (
            <option key={item.field} value={item.field}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Comment
        <textarea
          name="comment"
          value={comment}
          onChange={(event) => onComment(event.target.value)}
          rows={3}
          className="rounded-lg border border-line bg-paper px-2 py-2"
        />
      </label>
      <PrimaryButton type="button" onClick={onSave}>Save override</PrimaryButton>
    </form>
  );
}
