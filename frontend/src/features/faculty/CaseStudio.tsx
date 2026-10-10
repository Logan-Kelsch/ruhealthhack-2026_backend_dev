import { useEffect, useState, type FormEvent } from "react";
import {
  ApiError,
  answerIntake,
  api,
  createDraft,
  loadStudioCase,
  type ApiClient,
  type IntakeGap,
  type StudioCaseDetail,
  type StudioDraftResult,
} from "../../api/client";
import type { Go, StudioTab } from "../../app/types";
import { Avatar, type Portrait } from "../../components/Avatar";
import { BackLink, Badge, Card, CardHead, PrimaryButton, TabNav } from "../../components/ui";

const TABS: { id: StudioTab; label: string }[] = [
  { id: "patient", label: "Patient" },
  { id: "objectives", label: "Learning objectives" },
  { id: "files", label: "Files and sources" },
  { id: "tree", label: "Decision tree" },
];

type CreatePhase = { kind: "editing" } | { kind: "saving" } | { kind: "error"; message: string };

type LoadPhase =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; detail: StudioCaseDetail };

type AnswerPhase =
  | { kind: "idle" }
  | { kind: "saving"; gapId: string }
  | { kind: "error"; gapId: string; message: string };

// Patient Studio for a description and its guided questions. Other studio actions stay unavailable.
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

  const detail = load.kind === "ready" ? load.detail : null;
  const heading = detail?.case.profile.name ?? "New case";

  // Save the description, then open the case id and version the server returned.
  async function submitDescription(event: FormEvent) {
    event.preventDefault();
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
    } catch (error: unknown) {
      // Keep the previous case on screen. The answer stays in the box for an explicit retry.
      setAnswerPhase({
        kind: "error",
        gapId: gap.id,
        message: failureMessage(error, "The answer could not be saved."),
      });
    }
  }

  return (
    <div className="mx-auto flex max-w-[1320px] flex-col gap-5 px-10 pt-7 pb-12">
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
          <div className="flex gap-2">
            <button
              type="button"
              disabled
              className="inline-flex h-10 cursor-not-allowed items-center rounded-[10px] border border-line-2 bg-card px-4 text-sm font-medium text-muted"
            >
              Preview unavailable
            </button>
            <button
              type="button"
              disabled
              className="h-10 cursor-not-allowed rounded-[10px] bg-inactive px-[18px] text-sm font-medium text-white"
            >
              Publish unavailable
            </button>
          </div>
        </div>
        <TabNav items={TABS} active={current} onChange={setCurrent} />
      </header>

      {current === "patient" ? (
        caseId ? (
          <LoadedDraft
            load={load}
            answers={answers}
            answerPhase={answerPhase}
            onRetryLoad={() => setAttempt((value) => value + 1)}
            onAnswerChange={(gapId, text) => setAnswers((currentAnswers) => ({ ...currentAnswers, [gapId]: text }))}
            onAnswer={(event, gap) => {
              void submitAnswer(event, gap);
            }}
          />
        ) : (
          <DescriptionForm
            description={description}
            phase={createPhase}
            onChange={setDescription}
            onSubmit={(event) => {
              void submitDescription(event);
            }}
          />
        )
      ) : (
        <Card>
          <div className="px-5 py-8 text-sm text-ink">This part of the studio is not available yet.</div>
        </Card>
      )}
    </div>
  );
}

// The plain-language description. Nothing here is shown as a saved patient until the request succeeds.
function DescriptionForm({
  description,
  phase,
  onChange,
  onSubmit,
}: {
  description: string;
  phase: CreatePhase;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  const saving = phase.kind === "saving";
  return (
    <Card>
      <CardHead title="New draft" />
      <form onSubmit={onSubmit} className="flex flex-col gap-3 px-5 py-5">
        <label htmlFor="patient-description" className="text-sm font-medium">
          Describe the patient
        </label>
        <textarea
          id="patient-description"
          value={description}
          onChange={(event) => onChange(event.target.value)}
          disabled={saving}
          className="min-h-28 w-full rounded-xl border border-line-2 bg-card px-3 py-2 text-sm text-ink outline-none"
        />
        {phase.kind === "error" ? (
          <p role="alert" className="text-sm text-ink">
            {phase.message}
          </p>
        ) : null}
        <div>
          <PrimaryButton type="submit" disabled={saving}>
            {saving ? "Saving draft" : phase.kind === "error" ? "Try again" : "Create draft"}
          </PrimaryButton>
        </div>
      </form>
    </Card>
  );
}

// The saved draft, its remaining questions, and the words the faculty member already entered.
function LoadedDraft({
  load,
  answers,
  answerPhase,
  onRetryLoad,
  onAnswerChange,
  onAnswer,
}: {
  load: LoadPhase;
  answers: Record<string, string>;
  answerPhase: AnswerPhase;
  onRetryLoad: () => void;
  onAnswerChange: (gapId: string, text: string) => void;
  onAnswer: (event: FormEvent, gap: IntakeGap) => void;
}) {
  if (load.kind === "loading") {
    return <p className="text-sm text-muted">Loading draft</p>;
  }
  if (load.kind === "error") {
    return (
      <div className="flex flex-col items-start gap-3">
        <p role="alert" className="text-sm text-ink">
          {load.message}
        </p>
        <PrimaryButton onClick={onRetryLoad}>Try again</PrimaryButton>
      </div>
    );
  }
  const { detail } = load;
  const gaps = detail.gaps;
  const required = gaps.filter((gap) => gap.blocking).length;
  return (
    <div className="flex flex-wrap items-start gap-5">
      <div className="min-w-0 flex-[1_1_560px]">
        <Card>
          <CardHead title="Case" aside={<span className="text-[12.5px] text-muted">Version {detail.case.version}</span>} />
          <div className="flex flex-col gap-3 px-5 py-5 text-sm">
            <p>{detail.case.description}</p>
            <p>
              {ageLabel(detail.case.profile.age)} · {sexLabel(detail.case.profile.sex)}
            </p>
            <FactList facts={detail.case.facts} />
          </div>
        </Card>
      </div>
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

// Facts already stored on the case. An unsaved answer is not added here.
function FactList({ facts }: { facts: StudioCaseDetail["case"]["facts"] }) {
  const rows = facts ?? [];
  if (rows.length === 0) return <p className="text-muted">No facts yet</p>;
  return (
    <ul className="flex flex-col gap-2">
      {rows.map((fact) => (
        <li key={fact.id}>
          <span className="block font-medium">{fact.text}</span>
          <span className="text-[12.5px] text-muted">
            {factStatusLabel(fact.status)} · Source: {fact.source?.kind ?? "not recorded"}
          </span>
        </li>
      ))}
    </ul>
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

// Draft and approved are both words. Color is not the only way to tell them apart.
function factStatusLabel(status: "draft" | "approved"): string {
  switch (status) {
    case "draft":
      return "Draft";
    case "approved":
      return "Approved";
    default: {
      const unreachable: never = status;
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
