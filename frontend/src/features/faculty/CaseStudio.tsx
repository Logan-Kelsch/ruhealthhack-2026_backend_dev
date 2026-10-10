import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import {
  ApiError,
  answerIntake,
  api,
  autofillStudioCase,
  createDraft,
  loadStudioCase,
  loadStudioVocab,
  lookupDiagnosis,
  publishStudioCase,
  saveStudioCase,
  setItemApproval,
  type ApiClient,
  type ApprovalGroup,
  type CaseDocument,
  type Icd10Match,
  type IntakeGap,
  type ItemStatus,
  type StudioCaseDetail,
  type StudioDraftResult,
  type StudioVocab,
} from "../../api/client";
import { factReferenceNotes, saveProblem } from "./caseDraft";
import { CaseBuilder, type CreatePhase } from "./CaseBuilder";
import { CaseReview } from "./CaseReview";
import { DecisionTree } from "./DecisionTree";
import { CaseEditor, ObjectiveEditor, type SavePhase } from "./caseForm";
import type { Go, StudioTab } from "../../app/types";
import { Avatar, type Portrait } from "../../components/Avatar";
import { BackLink, Badge, Card, PrimaryButton, TabNav } from "../../components/ui";

const TABS: { id: StudioTab; label: string }[] = [
  { id: "patient", label: "Patient" },
  { id: "objectives", label: "Learning objectives" },
  { id: "files", label: "Files and sources" },
  { id: "tree", label: "Decision tree" },
  { id: "review", label: "Review" },
];

type LoadPhase =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; detail: StudioCaseDetail };

type AnswerPhase =
  | { kind: "idle" }
  | { kind: "saving"; gapId: string }
  | { kind: "error"; gapId: string; message: string };

type PublishPhase =
  | { kind: "idle" }
  | { kind: "publishing" }
  | { kind: "rejected"; message: string; blockers: string[] }
  | { kind: "error"; message: string };

// Patient Studio. Supported case content, including the decision tree, can be edited and approved. Files cannot.
export function CaseStudio({
  go,
  tab,
  caseId,
  version,
  client = api,
}: {
  go: Go;
  tab: StudioTab;
  caseId?: string;
  version?: number;
  client?: ApiClient;
}) {
  const [current, setCurrent] = useState<StudioTab>(tab);
  const [description, setDescription] = useState("");
  const [createPhase, setCreatePhase] = useState<CreatePhase>({ kind: "editing" });
  const [load, setLoad] = useState<LoadPhase>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [answerPhase, setAnswerPhase] = useState<AnswerPhase>({ kind: "idle" });
  const [draft, setDraft] = useState<CaseDocument | null>(null);
  const [dirty, setDirty] = useState(false);
  const [savePhase, setSavePhase] = useState<SavePhase>({ kind: "idle" });
  const [reviewMessage, setReviewMessage] = useState<string | null>(null);
  const [factHold, setFactHold] = useState<string | null>(null);
  const [notes, setNotes] = useState<string[]>([]);
  const [vocab, setVocab] = useState<StudioVocab | null>(null);
  const [vocabError, setVocabError] = useState<string | null>(null);
  const [lookupResults, setLookupResults] = useState<Icd10Match[]>([]);
  const [lookupMessage, setLookupMessage] = useState<string | null>(null);
  const [publishPhase, setPublishPhase] = useState<PublishPhase>({ kind: "idle" });

  // Follow the shell when another screen opens Studio on a chosen tab.
  useEffect(() => {
    setCurrent(tab);
  }, [tab]);

  // Opening a case id loads that saved version. It does not create a draft.
  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    setLoad({ kind: "loading" });
    loadStudioCase(client, caseId, version)
      .then((detail) => {
        if (!cancelled) setLoad({ kind: "ready", detail });
      })
      .catch((error: unknown) => {
        if (!cancelled) setLoad({ kind: "error", message: failureMessage(error, "The draft could not be loaded.") });
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, version, client, attempt]);

  // Copy the saved case into the editor only when the faculty member has no unsaved edits.
  useEffect(() => {
    if (load.kind !== "ready" || dirty) return;
    setDraft(load.detail.case);
  }, [load, dirty]);

  // Topics, maneuvers, and panels come from the vocabulary route. A failure does not invent a list.
  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    setVocab(null);
    setVocabError(null);
    loadStudioVocab(client)
      .then((next) => {
        if (cancelled) return;
        // A 200 that is not the vocabulary must not be treated as a maneuver list.
        if (!isStudioVocab(next)) {
          setVocabError("The vocabulary could not be loaded.");
          return;
        }
        setVocab(next);
      })
      .catch((error: unknown) => {
        if (!cancelled) setVocabError(failureMessage(error, "The vocabulary could not be loaded."));
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, client]);

  const detail = load.kind === "ready" ? load.detail : null;
  const heading = detail?.case.profile.name ?? "New case";

  // Save the description, then open the case id and version the server returned.
  async function submitDescription() {
    setCreatePhase({ kind: "saving" });
    try {
      const result = await createDraft(client, description);
      go("f-studio", {
        studioTab: "patient",
        caseId: result.case.case_id,
        version: result.case.version,
      });
    } catch (error: unknown) {
      // Stay on the form. A failed create has no case id to open.
      setCreatePhase({ kind: "error", message: failureMessage(error, "The draft could not be saved.") });
    }
  }

  // Send the text to this gap only. A failure leaves the saved draft on screen.
  async function submitAnswer(event: FormEvent, gap: IntakeGap) {
    event.preventDefault();
    if (!caseId) return;
    const text = (answers[gap.id] ?? "").trim();
    // An empty box is not a saved answer, and it is not sent.
    if (!text) {
      setAnswerPhase({ kind: "error", gapId: gap.id, message: "Write an answer before saving." });
      return;
    }
    // Intake replaces the saved case. Unsaved edits have to be stored first or they would disappear.
    if (dirty) {
      setAnswerPhase({ kind: "error", gapId: gap.id, message: "Save these edits before answering intake." });
      return;
    }
    setAnswerPhase({ kind: "saving", gapId: gap.id });
    try {
      const result = await answerIntake(client, caseId, gap.id, text);
      setLoad({ kind: "ready", detail: detailFromResult(result) });
      setAnswers((currentAnswers) => {
        const next = { ...currentAnswers };
        delete next[gap.id];
        return next;
      });
      setAnswerPhase({ kind: "idle" });
      setDraft(result.case);
      setDirty(false);
    } catch (error: unknown) {
      // Keep the previous case on screen. The answer stays in the box for an explicit retry.
      setAnswerPhase({
        kind: "error",
        gapId: gap.id,
        message: failureMessage(error, "The answer could not be saved."),
      });
    }
  }

  // Keep the edited case locally. A later failed save still has this copy.
  function edit(next: CaseDocument) {
    setDraft(next);
    setDirty(true);
    setSavePhase({ kind: "idle" });
  }

  // Publish only moves the badge when the server saved a published version. A rejection stays on the draft.
  async function publishDraft() {
    if (!caseId || load.kind !== "ready") return;
    if (dirty) {
      setPublishPhase({ kind: "error", message: "Save these edits before publishing." });
      return;
    }
    setPublishPhase({ kind: "publishing" });
    try {
      const result = await publishStudioCase(client, caseId);
      setPublishPhase({ kind: "idle" });
      remember(result);
    } catch (error: unknown) {
      if (error instanceof ApiError && (error.status === 409 || error.blockers.length > 0)) {
        setPublishPhase({ kind: "rejected", message: error.message, blockers: error.blockers });
        return;
      }
      setPublishPhase({ kind: "error", message: failureMessage(error, "The case could not be published.") });
    }
  }

  // Point the address bar at the case the server just stored, so a refresh opens that version.
  function remember(next: StudioCaseDetail) {
    setLoad({ kind: "ready", detail: next });
    setDraft(next.case);
    setDirty(false);
    go("f-studio", { studioTab: current, caseId: next.case.case_id, version: next.case.version });
  }

  // Write the editor's case. Validation and request failures stay on the form.
  async function saveEdits() {
    if (!caseId || !draft) return;
    const problem = saveProblem(draft);
    if (problem) {
      setSavePhase({ kind: "error", message: problem });
      return;
    }
    setSavePhase({ kind: "saving" });
    try {
      const result = await saveStudioCase(client, caseId, draft);
      setSavePhase({ kind: "saved" });
      setFactHold(null);
      setReviewMessage(null);
      remember(result);
    } catch (error: unknown) {
      setSavePhase({ kind: "error", message: failureMessage(error, "The case could not be saved.") });
    }
  }

  // Approval reads the saved case, so unsaved edits must be stored before it runs.
  async function review(group: ApprovalGroup, key: string, status: ItemStatus) {
    if (!caseId) return;
    if (dirty) {
      setReviewMessage("Save these edits before changing approval.");
      return;
    }
    try {
      const result = await setItemApproval(client, caseId, group, status, [key]);
      setReviewMessage(null);
      remember(result);
    } catch (error: unknown) {
      setReviewMessage(failureMessage(error, "The approval could not be saved."));
    }
  }

  // Auto-fill also reads the saved case. Faculty overrides have to be saved before it proposes values.
  async function propose(panels: string[], vitals: boolean) {
    if (!caseId) return;
    if (dirty) {
      setReviewMessage("Save these edits before auto-fill so faculty entries are kept.");
      return;
    }
    if (panels.length === 0 && !vitals) {
      setReviewMessage("Choose a lab panel or vital signs before proposing values.");
      return;
    }
    try {
      const result = await autofillStudioCase(client, caseId, panels, vitals);
      setNotes(result.notes);
      setReviewMessage(null);
      remember({ case: result.case, status: result.status, gaps: result.gaps, blockers: result.blockers });
    } catch (error: unknown) {
      // Drop any older notes so a failure does not still look like a proposal.
      setNotes([]);
      setReviewMessage(failureMessage(error, "Auto-fill could not be saved."));
    }
  }

  // Show the lookup rows the API returned. A failure clears them instead of leaving a previous list.
  async function searchDiagnosis(query: string) {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setLookupResults([]);
      setLookupMessage("Type at least two letters to look up a diagnosis.");
      return;
    }
    try {
      const matches = await lookupDiagnosis(client, trimmed);
      setLookupResults(matches);
      setLookupMessage(matches.length === 0 ? "No matching diagnosis." : null);
    } catch (error: unknown) {
      setLookupResults([]);
      setLookupMessage(failureMessage(error, "Diagnosis lookup failed."));
    }
  }

  // Store the diagnosis the faculty member picked. The code is the one the lookup returned.
  function useDiagnosis(match: Icd10Match) {
    if (!draft) return;
    const diagnoses = draft.diagnoses ?? [];
    if (diagnoses.some((item) => (item.codes ?? []).some((code) => code.code === match.code))) {
      setLookupMessage("That diagnosis is already on the case.");
      return;
    }
    edit({
      ...draft,
      diagnoses: [
        ...diagnoses,
        {
          name: match.display,
          status: "draft",
          codes: [{ system: "ICD-10-CM", code: match.code, display: match.display }],
          source: { kind: "faculty", ref: "icd10 lookup", by: null },
        },
      ],
    });
    setLookupMessage(null);
  }

  // Show references and keep the fact when something else still names it.
  function removeFact(factId: string) {
    if (!draft) return;
    const held = factReferenceNotes(draft, factId);
    if (held.length > 0) {
      setFactHold(held.join(" "));
      return;
    }
    setFactHold(null);
    edit({ ...draft, facts: (draft.facts ?? []).filter((fact) => fact.id !== factId) });
  }

  const editorProps = draft
    ? {
        caseDocument: draft,
        vocab,
        vocabError,
        savePhase,
        reviewMessage,
        lookupResults,
        lookupMessage,
        factHold,
        notes,
        onChange: edit,
        onSave: () => {
          void saveEdits();
        },
        onApprove: (group: ApprovalGroup, key: string, status: ItemStatus) => {
          void review(group, key, status);
        },
        onAutofill: (panels: string[], vitals: boolean) => {
          void propose(panels, vitals);
        },
        onLookup: (query: string) => {
          void searchDiagnosis(query);
        },
        onUseDiagnosis: useDiagnosis,
        onRemoveFact: removeFact,
      }
    : null;

  return (
    <div className={`mx-auto flex max-w-[1320px] flex-col gap-5 px-10 pt-7 ${caseId ? "pb-12" : "h-full pb-6"}`}>
      <header className="flex flex-col gap-3.5">
        <BackLink label="Cases" onClick={() => go("f-cases")} />
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <Avatar who={caseId ? portraitFor(caseId) : "generic"} size={52} />
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="m-0 font-serif text-[34px] leading-none font-medium tracking-[-0.7px]">{heading}</h1>
                {detail ? (
                  <Badge tone={detail.status === "published" ? "ok" : "warn"} dot>
                    {statusLabel(detail.status)}
                  </Badge>
                ) : null}
              </div>
              <div className="mt-1 text-[13px] text-muted">{metaLine(detail)}</div>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <div className="flex gap-2">
              <button
                type="button"
                disabled={!caseId || load.kind !== "ready"}
                onClick={() => setCurrent("review")}
                className="inline-flex h-10 items-center rounded-[10px] border border-line-2 bg-card px-4 text-sm font-medium text-ink disabled:cursor-not-allowed disabled:text-muted"
              >
                {caseId && load.kind === "ready" ? "Preview" : "Preview unavailable"}
              </button>
              <button
                type="button"
                disabled={!caseId || load.kind !== "ready" || publishPhase.kind === "publishing"}
                onClick={() => {
                  void publishDraft();
                }}
                className="h-10 rounded-[10px] bg-panel px-[18px] text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-inactive"
              >
                {publishLabel(Boolean(caseId) && load.kind === "ready", publishPhase)}
              </button>
            </div>
            <PublishNotice phase={publishPhase} />
          </div>
        </div>
        {caseId ? <TabNav items={TABS} active={current} onChange={setCurrent} /> : null}
      </header>

      {current === "patient" ? (
        caseId ? (
          <LoadedDraft
            load={load}
            editor={editorProps ? <CaseEditor {...editorProps} /> : null}
            answers={answers}
            answerPhase={answerPhase}
            onRetryLoad={() => setAttempt((value) => value + 1)}
            onAnswerChange={(gapId, text) => setAnswers((currentAnswers) => ({ ...currentAnswers, [gapId]: text }))}
            onAnswer={(event, gap) => {
              void submitAnswer(event, gap);
            }}
          />
        ) : (
          <CaseBuilder
            go={go}
            client={client}
            description={description}
            onDescriptionChange={setDescription}
            createPhase={createPhase}
            onCreateDraft={() => {
              void submitDescription();
            }}
          />
        )
      ) : current === "objectives" ? (
        editorProps ? (
          <ObjectiveEditor
            caseDocument={editorProps.caseDocument}
            vocab={editorProps.vocab}
            savePhase={editorProps.savePhase}
            reviewMessage={editorProps.reviewMessage}
            onChange={editorProps.onChange}
            onSave={editorProps.onSave}
            onApprove={editorProps.onApprove}
          />
        ) : (
          <LoadStatus load={load} onRetry={() => setAttempt((value) => value + 1)} />
        )
      ) : current === "tree" ? (
        editorProps ? (
          <DecisionTree
            caseDocument={editorProps.caseDocument}
            vocab={editorProps.vocab}
            vocabError={editorProps.vocabError}
            savePhase={editorProps.savePhase}
            reviewMessage={editorProps.reviewMessage}
            onChange={editorProps.onChange}
            onSave={editorProps.onSave}
            onApprove={editorProps.onApprove}
          />
        ) : (
          <LoadStatus load={load} onRetry={() => setAttempt((value) => value + 1)} />
        )
      ) : current === "review" ? (
        load.kind === "ready" && caseId ? (
          <CaseReview client={client} caseId={caseId} visits={load.detail.case.visits ?? []} />
        ) : (
          <LoadStatus load={load} onRetry={() => setAttempt((value) => value + 1)} />
        )
      ) : (
        <Card>
          <div className="px-5 py-8 text-sm text-ink">This part of the studio is not available yet.</div>
        </Card>
      )}
    </div>
  );
}

// Loading and load errors. The editor is not shown until a saved case is in hand.
function LoadStatus({ load, onRetry }: { load: LoadPhase; onRetry: () => void }) {
  if (load.kind === "error") {
    return (
      <div className="flex flex-col items-start gap-3">
        <p role="alert" className="text-sm text-ink">
          {load.message}
        </p>
        <PrimaryButton onClick={onRetry}>Try again</PrimaryButton>
      </div>
    );
  }
  return <p className="text-sm text-muted">Loading draft</p>;
}

// The saved draft's questions sit beside the editor. The editor is the case itself.
function LoadedDraft({
  load,
  editor,
  answers,
  answerPhase,
  onRetryLoad,
  onAnswerChange,
  onAnswer,
}: {
  load: LoadPhase;
  editor: ReactNode;
  answers: Record<string, string>;
  answerPhase: AnswerPhase;
  onRetryLoad: () => void;
  onAnswerChange: (gapId: string, text: string) => void;
  onAnswer: (event: FormEvent, gap: IntakeGap) => void;
}) {
  if (load.kind !== "ready" || !editor) {
    return <LoadStatus load={load} onRetry={onRetryLoad} />;
  }
  const { detail } = load;
  const gaps = detail.gaps;
  const required = gaps.filter((gap) => gap.blocking).length;
  return (
    <div className="flex flex-wrap items-start gap-5">
      <div className="min-w-0 flex-[1_1_560px]">{editor}</div>
      <aside className="sticky top-5 max-w-[420px] min-w-[280px] flex-[1_1_280px] overflow-hidden rounded-2xl border border-line bg-card">
        <div className="border-b border-hair-2 px-[18px] py-4">
          <div className="text-[15px] font-semibold">Guided intake</div>
          <p className="mt-1 text-[13px] text-muted">{openQuestionLabel(gaps.length)}</p>
          <p className="mt-0.5 text-[13px] text-ink">{requiredLabel(required)}</p>
        </div>
        {detail.blockers.length > 0 ? (
          <div className="border-b border-hair-2 px-[18px] py-4">
            <div className="text-[13px] font-semibold">Still needed</div>
            <ul className="mt-2 flex flex-col gap-1 text-[13px] text-ink">
              {detail.blockers.map((blocker) => (
                <li key={blocker}>{blocker}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {gaps.length === 0 ? (
          <p className="px-[18px] py-4 text-sm text-muted">No intake questions left</p>
        ) : (
          gaps.map((gap) => (
            <GapForm
              key={gap.id}
              gap={gap}
              value={answers[gap.id] ?? ""}
              phase={answerPhase}
              onChange={(text) => onAnswerChange(gap.id, text)}
              onSubmit={(event) => onAnswer(event, gap)}
            />
          ))
        )}
      </aside>
    </div>
  );
}

// One question from the backend gap list. The answer is sent only for this gap id.
function GapForm({
  gap,
  value,
  phase,
  onChange,
  onSubmit,
}: {
  gap: IntakeGap;
  value: string;
  phase: AnswerPhase;
  onChange: (text: string) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  const saving = phase.kind === "saving" && phase.gapId === gap.id;
  const failed = phase.kind === "error" && phase.gapId === gap.id;
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-2 border-t border-hair px-[18px] py-4">
      <label htmlFor={`gap-${gap.id}`} className="text-[14.5px] font-medium">
        {gap.question}
      </label>
      <p className="text-[12.5px] text-muted">
        {gapKindLabel(gap.kind)}
        {gap.blocking ? " · Required" : ""}
      </p>
      <textarea
        id={`gap-${gap.id}`}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={saving}
        className="min-h-20 w-full rounded-xl border border-line-2 bg-card px-3 py-2 text-sm text-ink outline-none"
      />
      {failed ? (
        <p role="alert" className="text-sm text-ink">
          {phase.message}
        </p>
      ) : null}
      <div>
        <PrimaryButton type="submit" disabled={saving}>
          {saving ? "Saving answer" : failed ? "Try again" : "Save answer"}
        </PrimaryButton>
      </div>
    </form>
  );
}

// Intake returns the same case view as a load, plus model calls the screen does not show.
function detailFromResult(result: StudioDraftResult): StudioCaseDetail {
  return {
    case: result.case,
    status: result.status,
    gaps: result.gaps,
    blockers: result.blockers,
  };
}

// The editor only offers a vocabulary that has the four lists. Anything else is a failed load.
function isStudioVocab(value: StudioVocab): boolean {
  return (
    Array.isArray(value.topics) &&
    Array.isArray(value.actions) &&
    Array.isArray(value.maneuvers) &&
    Array.isArray(value.lab_panels)
  );
}

// Prefer the server message. A network failure still gets a sentence instead of a blank screen.
function failureMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.message.trim()) return error.message;
  return fallback;
}

// The line under the name. Numbers and words come from the saved case.
function metaLine(detail: StudioCaseDetail | null): string {
  if (!detail) return "Not saved yet";
  return `Version ${detail.case.version} · ${ageLabel(detail.case.profile.age)} · ${sexLabel(detail.case.profile.sex)}`;
}

// Age 0 means the description did not include an age. Do not present 0 as a real age.
function ageLabel(age: number): string {
  if (age > 0) return `Age ${age}`;
  return "Age not recorded";
}

// The sex word is the signal. The portrait does not carry it.
function sexLabel(sex: StudioCaseDetail["case"]["profile"]["sex"]): string {
  switch (sex) {
    case "male":
      return "Male";
    case "female":
      return "Female";
    case "other":
      return "Other";
    default: {
      const unreachable: never = sex;
      return unreachable;
    }
  }
}

// The publish control names the state it is in. A draft that can be sent does not say it is already published.
function publishLabel(ready: boolean, phase: PublishPhase): string {
  if (!ready) return "Publish unavailable";
  if (phase.kind === "publishing") return "Publishing";
  return "Publish";
}

// Blockers stay sentences from the server. A rejection is not shown as a published case.
function PublishNotice({ phase }: { phase: PublishPhase }) {
  if (phase.kind === "idle" || phase.kind === "publishing") return null;
  if (phase.kind === "rejected") {
    return (
      <div role="alert" className="max-w-md text-sm text-ink">
        <p>{phase.message}</p>
        <ul className="mt-1 flex flex-col gap-1">
          {phase.blockers.map((blocker) => (
            <li key={blocker}>{blocker}</li>
          ))}
        </ul>
      </div>
    );
  }
  return (
    <p role="alert" className="max-w-md text-sm text-ink">
      {phase.message}
    </p>
  );
}

// Status text matches the saved value. The badge color repeats it.
function statusLabel(status: StudioCaseDetail["status"]): string {
  switch (status) {
    case "draft":
      return "Draft";
    case "published":
      return "Published";
    case "archived":
      return "Archived";
    default: {
      const unreachable: never = status;
      return unreachable;
    }
  }
}

// How many questions the backend still wants, written out so the count is not only a bar.
function openQuestionLabel(count: number): string {
  const noun = count === 1 ? "question" : "questions";
  return `${count} intake ${noun} still open`;
}

// Required questions are the blocking gaps. Zero of them is a complete required intake.
function requiredLabel(count: number): string {
  if (count === 0) return "Required intake questions are answered";
  const noun = count === 1 ? "question" : "questions";
  return `${count} required ${noun} still open`;
}

// A short name for the gap kind, so the question says what kind of answer it stores.
function gapKindLabel(kind: IntakeGap["kind"]): string {
  switch (kind) {
    case "field":
      return "Profile";
    case "facts":
      return "Patient fact";
    case "objectives":
      return "Learning objective";
    case "autofill":
      return "Auto-fill";
    default: {
      const unreachable: never = kind;
      return unreachable;
    }
  }
}

// The three golden cases keep their drawn portraits. Every other case uses the generic face.
function portraitFor(caseId: string): Portrait {
  if (caseId === "walter_greene") return "walter";
  if (caseId === "alina_reyes") return "alina";
  if (caseId === "eli_brooks") return "eli";
  return "generic";
}
