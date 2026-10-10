"""HTTP bodies for the debrief and the documentation check.

Scores, trust, and the note check are returned only from the feedback routes.
The encounter recovery view does not use these models.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.http import LlmCallRecord

ScoreValue = Literal[1, 2, 3, 4, "N/A"]
# Keys from the official SHP rubric. A faculty score may only name one of these.
RubricDomainKey = Literal[
    "opening_and_purpose",
    "rapport_respect_empathy",
    "information_gathering",
    "listening_and_response_to_cues",
    "explanation_and_shared_decisions",
    "clinical_reasoning_and_synthesis",
    "professionalism_safety_closure",
]
# The three comments already stored on a generated domain score.
CommentField = Literal[
    "strength_demonstrated",
    "important_gap_or_missed_opportunity",
    "safety_or_accuracy_concern",
]


class EvidenceQuote(BaseModel):
    """A transcript span a score or trust event is allowed to cite."""

    turn: int
    quote: str = Field(min_length=1)


class DomainScore(BaseModel):
    """One official domain. A number is only valid when evidence quotes the transcript."""

    key: str
    name: str
    id: int
    score: ScoreValue
    evidence: list[EvidenceQuote] = Field(default_factory=list)
    strength_demonstrated: str = ""
    important_gap_or_missed_opportunity: str = ""
    safety_or_accuracy_concern: str = ""
    method: Literal["rule-based", "llm"]
    rule_based_score: ScoreValue


class CitedNote(BaseModel):
    """A strength or improvement. The quote is omitted when it was not in the transcript."""

    text: str
    turn: int | None = None
    quote: str | None = None


class RubricResult(BaseModel):
    """The seven-domain result. The interpretation is the official discussion-aid wording."""

    rubric_title: str
    domains: list[DomainScore]
    total: int
    max_total: int
    review_flag: bool
    review_reasons: list[str] = Field(default_factory=list)
    interpretation: str
    strengths: list[CitedNote] = Field(default_factory=list)
    improvements: list[CitedNote] = Field(default_factory=list)
    next_attempt: list[str] = Field(default_factory=list)


class JargonMetric(BaseModel):
    """A term the student used without a plain-language explanation, with the words they said."""

    term: str
    quote: str


class CommunicationMetrics(BaseModel):
    """Counts from the tagged turns. A ratio stays null when there were no questions to count."""

    turns: int
    open_questions: int
    closed_questions: int
    percent_open: int | None = None
    reflections: int
    validations: int
    reflection_to_question_ratio: float | None = None
    unexplained_jargon: list[JargonMetric] = Field(default_factory=list)
    interruptions: int
    student_talk_share: int | None = None


class FoundFact(BaseModel):
    """An expected discovery the student actually elicited, with the turn that released it."""

    fact_id: str
    text: str
    turn: int


class MissedFact(BaseModel):
    """An expected discovery that stayed undisclosed, with a question the student could ask."""

    fact_id: str
    text: str
    suggestion: str = ""


class ObjectiveAction(BaseModel):
    """Whether the student performed one expected action."""

    action: str
    done: bool


class ObjectiveProgress(BaseModel):
    """Elicited and missed items for one learning objective."""

    objective_id: str
    objective: str
    found: list[FoundFact] = Field(default_factory=list)
    missed: list[MissedFact] = Field(default_factory=list)
    actions: list[ObjectiveAction] = Field(default_factory=list)


class TrustTimelineEvent(BaseModel):
    """One trust change. The span is the words that caused it."""

    event: str
    delta: int
    span: str
    turn: int
    note: str | None = None


class TrustPoint(BaseModel):
    """Trust after one turn. Shown in the debrief, not while the visit is going on."""

    turn: int
    trust: int
    events: list[TrustTimelineEvent] = Field(default_factory=list)


class SafetyItem(BaseModel):
    """A case safety fact and whether the student found it and addressed it."""

    fact_id: str
    text: str
    discovered: bool
    addressed: bool | None = None
    patient_words: str = ""


class UnsupportedClaim(BaseModel):
    """A sentence in the note that the disclosure log and chart do not back."""

    statement: str
    reason: str


class MissingFinding(BaseModel):
    """A key finding the student learned and left out of the note. id is the fact or chart reference."""

    id: str
    text: str


class SupportedStatement(BaseModel):
    """A sentence tied to fact ids from the disclosure log, or marked as the student's own plan."""

    statement: str
    supported_by: list[str] = Field(default_factory=list)
    assessment_or_plan: bool = False


class DocumentationCheck(BaseModel):
    """The fabrication check. unsupported and missing keep the evidence they were judged against."""

    unsupported: list[UnsupportedClaim] = Field(default_factory=list)
    missing: list[MissingFinding] = Field(default_factory=list)
    supported: list[SupportedStatement] = Field(default_factory=list)
    method: Literal["rule-based", "llm"]


class BranchSummary(BaseModel):
    """Which authored outcome was taken. Later-visit fact changes are not part of this view."""

    id: str
    label: str
    summary: str = ""


class DecisionPathView(BaseModel):
    """The outcome id for this visit. Follow-up selection is a separate screen."""

    visit_id: str
    taken: BranchSummary | None = None
    ghosts: list[BranchSummary] = Field(default_factory=list)
    needs_faculty_review: list[str] = Field(default_factory=list)


class DebriefTurn(BaseModel):
    """One exchange the debrief can point at. mode says whether the reply used the template."""

    turn: int
    student: str
    patient: str
    mode: Literal["template", "llm"] = "template"


class ScoreOverride(BaseModel):
    """A faculty score for one official domain. It does not replace the generated score."""

    model_config = ConfigDict(extra="forbid")

    domain: RubricDomainKey
    score: ScoreValue


class CommentOverride(BaseModel):
    """A faculty comment on one domain field. The generated comment stays on the rubric."""

    model_config = ConfigDict(extra="forbid")

    domain: RubricDomainKey
    field: CommentField
    text: str = Field(min_length=1, max_length=2000)


class FeedbackOverrideRequest(BaseModel):
    """The only body a faculty override accepts: scores, comments, or both."""

    model_config = ConfigDict(extra="forbid")

    scores: list[ScoreOverride] = Field(default_factory=list)
    comments: list[CommentOverride] = Field(default_factory=list)

    @model_validator(mode="after")
    def needs_a_change(self) -> Self:
        """An empty body is not a faculty change, so it must not look saved."""
        if not self.scores and not self.comments:
            raise ValueError("Add a score or a comment")
        return self


class FeedbackOverrides(BaseModel):
    """Saved faculty changes. They sit beside the generated debrief."""

    model_config = ConfigDict(extra="forbid")

    scores: list[ScoreOverride] = Field(default_factory=list)
    comments: list[CommentOverride] = Field(default_factory=list)
    updated_at: str


class FeedbackResponse(BaseModel):
    """The saved debrief: rubric, evidence, trust, the note check, and the counts behind them."""

    rubric: RubricResult
    metrics: CommunicationMetrics
    elicited: list[ObjectiveProgress]
    trust_timeline: list[TrustPoint]
    safety: list[SafetyItem] = Field(default_factory=list)
    communication_notes: list[str] = Field(default_factory=list)
    documentation: DocumentationCheck | None = None
    decision_path: DecisionPathView
    transcript: list[DebriefTurn]
    llm_calls: list[LlmCallRecord] = Field(default_factory=list)
    fallback_used: bool = False
    generated_at: str
    # None until faculty save a score or comment. The rubric above stays the generated result.
    overrides: FeedbackOverrides | None = None

    @model_validator(mode="after")
    def numeric_scores_cite_a_span(self) -> Self:
        """Reject a 1–4 that has no quote. N/A is the only score that may omit one."""
        for domain in self.rubric.domains:
            if domain.score != "N/A" and not domain.evidence:
                raise ValueError(f"{domain.key} scored {domain.score} without a transcript span")
        return self
