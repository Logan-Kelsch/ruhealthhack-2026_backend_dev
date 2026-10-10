import { useEffect, useState } from "react";
import {
  ApiError,
  dismissFinding,
  loadConsistency,
  previewStudioCase,
  type ApiClient,
  type ConsistencyFinding,
  type PreviewRequest,
  type PreviewRun,
} from "../../api/client";
import { Card, CardHead, PrimaryButton } from "../../components/ui";

const LEVELS = ["novice", "competent", "expert", "adversarial"] as const;
const DRIVERS = ["scripted", "llm"] as const;

type VisitChoice = { id: string; label: string };

type CheckPhase =
  | { kind: "checking" }
  | { kind: "ready"; findings: ConsistencyFinding[] }
  | { kind: "error"; message: string };

type PreviewPhase =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "ready"; run: PreviewRun }
  | { kind: "error"; message: string };

// Faculty review of the saved draft. Findings and the preview come from the API, not from sample text.
export function CaseReview({
  client,
  caseId,
  visits,
}: {
  client: ApiClient;
  caseId: string;
  visits: VisitChoice[];
}) {
  const [check, setCheck] = useState<CheckPhase>({ kind: "checking" });
  const [dismissing, setDismissing] = useState<string | null>(null);
  const [dismissError, setDismissError] = useState<string | null>(null);
  const [level, setLevel] = useState<PreviewRequest["level"]>("competent");
  const [driver, setDriver] = useState<PreviewRequest["driver"]>("scripted");
  const [visitId, setVisitId] = useState(visits[0]?.id ?? "");
  const [preview, setPreview] = useState<PreviewPhase>({ kind: "idle" });

  // The check is of the saved case. Opening the tab again reads whatever dismissal was stored.
  useEffect(() => {
    let cancelled = false;
    setCheck({ kind: "checking" });
    loadConsistency(client, caseId)
      .then((findings) => {
        if (!cancelled) setCheck({ kind: "ready", findings });
      })
      .catch((error: unknown) => {
        if (!cancelled) setCheck({ kind: "error", message: failureMessage(error, "The consistency check could not be loaded.") });
      });
    return () => {
      cancelled = true;
    };
  }, [client, caseId]);

  // Store the dismissal, then show it without waiting for another navigation.
  async function dismiss(findingId: string) {
    setDismissing(findingId);
    setDismissError(null);
    try {
      await dismissFinding(client, caseId, findingId);
      setCheck((current) => {
        if (current.kind !== "ready") return current;
        return {
          kind: "ready",
          findings: current.findings.map((finding) =>
            finding.id === findingId ? { ...finding, dismissed: true } : finding,
          ),
        };
      });
    } catch (error: unknown) {
      setDismissError(failureMessage(error, "The dismissal could not be saved."));
    } finally {
      setDismissing(null);
    }
  }

  // Send the selected level, driver, and visit. The panel then shows that response, including a fallback.
  async function runPreview() {
    if (!visitId) {
      setPreview({ kind: "error", message: "This case has no visit to preview." });
      return;
    }
    setPreview({ kind: "running" });
    try {
      const run = await previewStudioCase(client, caseId, { level, driver, visit_id: visitId });
      setPreview({ kind: "ready", run });
    } catch (error: unknown) {
      setPreview({ kind: "error", message: failureMessage(error, "The preview could not be run.") });
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <Card>
        <CardHead title="Consistency" aside={<span className="text-[13px] text-muted">Worth review</span>} />
        <div className="flex flex-col gap-3 px-5 py-4">
          <Findings check={check} dismissing={dismissing} dismissError={dismissError} onDismiss={(id) => void dismiss(id)} />
        </div>
      </Card>
      <Card>
        <CardHead title="Test student" />
        <form
          className="flex flex-col gap-3 px-5 py-4"
          onSubmit={(event) => {
            event.preventDefault();
            void runPreview();
          }}
        >
          <PreviewChoices
            level={level}
            driver={driver}
            visitId={visitId}
            visits={visits}
            running={preview.kind === "running"}
            onLevel={setLevel}
            onDriver={setDriver}
            onVisit={setVisitId}
          />
          {preview.kind === "error" ? (
            <p role="alert" className="text-sm text-ink">
              {preview.message}
            </p>
          ) : null}
          {preview.kind === "ready" ? <PreviewResult run={preview.run} /> : null}
        </form>
      </Card>
    </div>
  );
}

// The three choices the preview route accepts. Labels are the words faculty pick.
function PreviewChoices({
  level,
  driver,
  visitId,
  visits,
  running,
  onLevel,
  onDriver,
  onVisit,
}: {
  level: PreviewRequest["level"];
  driver: PreviewRequest["driver"];
  visitId: string;
  visits: VisitChoice[];
  running: boolean;
  onLevel: (value: PreviewRequest["level"]) => void;
  onDriver: (value: PreviewRequest["driver"]) => void;
  onVisit: (value: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="flex flex-col gap-1 text-[13px] text-muted" htmlFor="preview-level">
        Level
        <select
          id="preview-level"
          value={level}
          disabled={running}
          onChange={(event) => onLevel(event.target.value as PreviewRequest["level"])}
          className="h-10 rounded-[10px] border border-line-2 bg-card px-2 text-sm text-ink"
        >
          {LEVELS.map((item) => (
            <option key={item} value={item}>
              {levelLabel(item)}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-[13px] text-muted" htmlFor="preview-driver">
        Driver
        <select
          id="preview-driver"
          value={driver}
          disabled={running}
          onChange={(event) => onDriver(event.target.value as PreviewRequest["driver"])}
          className="h-10 rounded-[10px] border border-line-2 bg-card px-2 text-sm text-ink"
        >
          {DRIVERS.map((item) => (
            <option key={item} value={item}>
              {driverLabel(item)}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-[13px] text-muted" htmlFor="preview-visit">
        Visit
        <select
          id="preview-visit"
          value={visitId}
          disabled={running}
          onChange={(event) => onVisit(event.target.value)}
          className="h-10 rounded-[10px] border border-line-2 bg-card px-2 text-sm text-ink"
        >
          {visits.map((visit) => (
            <option key={visit.id} value={visit.id}>
              {visit.label}
            </option>
          ))}
        </select>
      </label>
      <PrimaryButton type="submit" disabled={running}>
        {running ? "Running preview" : "Run preview"}
      </PrimaryButton>
    </div>
  );
}

// The run that came back: transcript, discoveries, blocked replies, feedback, and any driver fallback.
function PreviewResult({ run }: { run: PreviewRun }) {
  return (
    <div className="flex flex-col gap-4 text-sm text-ink">
      {run.fallback ? <p>{run.fallback.reason}</p> : null}
      <section>
        <h3 className="m-0 text-[15px] font-semibold">Transcript</h3>
        <ol className="mt-2 flex flex-col gap-2">
          {run.transcript.map((turn) => (
            <li key={turn.turn}>
              <div>Student: {turn.student}</div>
              <div>Patient: {turn.patient}</div>
            </li>
          ))}
        </ol>
      </section>
      <section>
        <h3 className="m-0 text-[15px] font-semibold">Discoveries</h3>
        {run.discoveries.length === 0 ? (
          <p className="mt-2 text-muted">No facts were discovered</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-1">
            {run.discoveries.map((item) => (
              <li key={`${item.objective_id}-${item.fact_id}`}>
                {item.text} <span className="text-muted">({item.fact_id})</span>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h3 className="m-0 text-[15px] font-semibold">Blocked replies</h3>
        {run.blocked_replies.length === 0 ? (
          <p className="mt-2 text-muted">No replies were blocked</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-2">
            {run.blocked_replies.map((item) => (
              <li key={`${item.turn}-${item.reply}`}>
                <div>{item.reply}</div>
                <div className="text-muted">{item.problems.join(" ")}</div>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h3 className="m-0 text-[15px] font-semibold">Feedback</h3>
        <p className="mt-2">
          {run.feedback.total} of {run.feedback.max_total}
        </p>
        <p className="text-muted">{run.feedback.interpretation}</p>
        <ul className="mt-2 flex flex-col gap-1">
          {run.feedback.domains.map((domain) => (
            <li key={domain.key}>
              {domain.name}: {domain.score}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

// Short names for the four supported levels. The value sent to the API stays the id.
function levelLabel(level: PreviewRequest["level"]): string {
  switch (level) {
    case "novice":
      return "Novice";
    case "competent":
      return "Competent";
    case "expert":
      return "Expert";
    case "adversarial":
      return "Adversarial";
    default: {
      const unreachable: never = level;
      return unreachable;
    }
  }
}

// The two drivers the preview route accepts.
function driverLabel(driver: PreviewRequest["driver"]): string {
  switch (driver) {
    case "scripted":
      return "Scripted";
    case "llm":
      return "Language model";
    default: {
      const unreachable: never = driver;
      return unreachable;
    }
  }
}

// The check's own words. A review finding is never labeled an error.
function Findings({
  check,
  dismissing,
  dismissError,
  onDismiss,
}: {
  check: CheckPhase;
  dismissing: string | null;
  dismissError: string | null;
  onDismiss: (findingId: string) => void;
}) {
  if (check.kind === "checking") {
    return <p className="text-sm text-muted">Checking the case</p>;
  }
  if (check.kind === "error") {
    return (
      <p role="alert" className="text-sm text-ink">
        {check.message}
      </p>
    );
  }
  if (check.findings.length === 0) {
    return <p className="text-sm text-muted">No consistency findings</p>;
  }
  return (
    <div className="flex flex-col gap-3">
      {dismissError ? (
        <p role="alert" className="text-sm text-ink">
          {dismissError}
        </p>
      ) : null}
      {check.findings.map((finding) => (
        <FindingRow key={finding.id} finding={finding} dismissing={dismissing === finding.id} onDismiss={() => onDismiss(finding.id)} />
      ))}
    </div>
  );
}

// One finding, its references, and the dismissal control when faculty have not accepted it yet.
function FindingRow({
  finding,
  dismissing,
  onDismiss,
}: {
  finding: ConsistencyFinding;
  dismissing: boolean;
  onDismiss: () => void;
}) {
  return (
    <div className="rounded-xl border border-line-2 px-4 py-3">
      <div className="text-[12.5px] font-medium text-muted">{severityLabel(finding.severity)}</div>
      <p className="mt-1 text-sm text-ink">{finding.message}</p>
      <p className="mt-1 text-[13px] text-muted">References: {(finding.refs ?? []).join(", ") || "none"}</p>
      {finding.dismissed ? (
        <p className="mt-2 text-sm text-ink">Dismissed</p>
      ) : (
        <div className="mt-2">
          <PrimaryButton onClick={onDismiss} disabled={dismissing}>
            {dismissing ? "Saving dismissal" : `Dismiss ${finding.id}`}
          </PrimaryButton>
        </div>
      )}
    </div>
  );
}

// Review is the word faculty see. Info is a note. Neither is called an error.
function severityLabel(severity: ConsistencyFinding["severity"]): string {
  switch (severity) {
    case "review":
      return "Worth review";
    case "info":
      return "Note";
    default: {
      const unreachable: never = severity;
      return unreachable;
    }
  }
}

// Prefer the server message. A dropped request still gets a sentence.
function failureMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.message.trim()) return error.message;
  return fallback;
}
