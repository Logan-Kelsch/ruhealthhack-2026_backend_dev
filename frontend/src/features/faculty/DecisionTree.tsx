import { useState, type ReactNode } from "react";
import type { ApprovalGroup, CaseDocument, ItemStatus, StudioVocab } from "../../api/client";
import { PrimaryButton } from "../../components/ui";
import type { SavePhase } from "./caseForm";
import {
  addDecisionPoint,
  addFollowUpVisit,
  addOutcome,
  checkCaption,
  firstChoice,
  groupLabel,
  kindLabel,
  optionList,
  readCheck,
  setDecisionCheck,
  setDecisionLabel,
  setOutcomeFact,
  setOutcomeLabel,
  setOutcomeSummary,
  setOutcomeWhen,
  setVisitBloodPressure,
  setVisitDay,
  setVisitLabel,
  setVisitMood,
  setVisitReason,
  type CheckSlot,
  type GroupKind,
  type LeafKind,
  type WhenChoice,
} from "./decisionAuthoring";

type Visit = NonNullable<CaseDocument["visits"]>[number];
type DecisionPoint = NonNullable<Visit["decision_points"]>[number];
type Branch = NonNullable<Visit["branches"]>[number];

const FIELD = "w-full rounded-xl border border-line-2 bg-card px-3 py-2 text-sm text-ink outline-none";
const GROUPS: GroupKind[] = ["leaf", "any", "all", "not", "before"];
const KINDS: LeafKind[] = ["topic", "action", "maneuver", "order", "fact_disclosed", "open_question"];
const CARD_W = 220;
const GAP = 36;
const ROW_Y = { start: 16, decision: 180, outcome: 380 };
const ROW_H = { start: 96, decision: 120, outcome: 132 };

// Faculty edit the visits stored on the case. The diagram shows those same visits.
export function DecisionTree({
  caseDocument,
  vocab,
  vocabError,
  savePhase,
  reviewMessage,
  onChange,
  onSave,
  onApprove,
}: {
  caseDocument: CaseDocument;
  vocab: StudioVocab | null;
  vocabError: string | null;
  savePhase: SavePhase;
  reviewMessage: string | null;
  onChange: (next: CaseDocument) => void;
  onSave: () => void;
  onApprove: (group: ApprovalGroup, key: string, status: ItemStatus) => void;
}) {
  const visits = caseDocument.visits ?? [];
  const [visitId, setVisitId] = useState(visits[0]?.id ?? "");
  const visit = visits.find((item) => item.id === visitId) ?? visits[0];

  return (
    <div className="grid min-h-[640px] grid-cols-1 overflow-hidden rounded-2xl border border-line bg-card xl:grid-cols-[minmax(0,1fr)_300px]">
      <div className="min-h-[420px] min-w-0 overflow-auto bg-canvas bg-[radial-gradient(var(--color-canvas-dot)_1px,transparent_1px)] bg-[length:20px_20px]">
        {visit ? <Diagram visit={visit} vocab={vocab} caseDocument={caseDocument} /> : null}
      </div>
      <aside className="flex max-h-[80vh] flex-col gap-4 overflow-auto border-t border-hair-2 px-4 py-4 xl:border-t-0 xl:border-l">
        <SaveNotice phase={savePhase} reviewMessage={reviewMessage} onSave={onSave} />
        {vocabError ? <p className="text-sm text-ink">{vocabError}</p> : null}
        {visits.length > 1 ? (
          <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink-soft">
            Visit
            <select
              id="visit-picker"
              value={visit?.id ?? ""}
              onChange={(event) => setVisitId(event.target.value)}
              className={FIELD}
            >
              {visits.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label || item.id}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {visit ? (
          <VisitEditor
            caseDocument={caseDocument}
            visit={visit}
            vocab={vocab}
            onChange={onChange}
            onApprove={onApprove}
            onAdded={(id) => setVisitId(id)}
          />
        ) : (
          <p className="text-sm text-ink">Add a visit before authoring decision points.</p>
        )}
      </aside>
    </div>
  );
}

// Label, day, mood, reason, and blood pressure for the visit currently on screen.
function VisitEditor({
  caseDocument,
  visit,
  vocab,
  onChange,
  onApprove,
  onAdded,
}: {
  caseDocument: CaseDocument;
  visit: Visit;
  vocab: StudioVocab | null;
  onChange: (next: CaseDocument) => void;
  onApprove: (group: ApprovalGroup, key: string, status: ItemStatus) => void;
  onAdded: (id: string) => void;
}) {
  const pressure = (visit.changes?.vitals ?? []).find((item) => item.key === "bp");
  const points = visit.decision_points ?? [];
  return (
    <div className="flex flex-col gap-4">
      <Field label="Visit label" id={`visit-label-${visit.id}`}>
        <input
          id={`visit-label-${visit.id}`}
          value={visit.label}
          onChange={(event) => onChange(setVisitLabel(caseDocument, visit.id, event.target.value))}
          className={FIELD}
        />
      </Field>
      <Field label="Day" id={`visit-day-${visit.id}`}>
        <input
          id={`visit-day-${visit.id}`}
          inputMode="numeric"
          value={String(visit.day)}
          onChange={(event) => onChange(setVisitDay(caseDocument, visit.id, event.target.value))}
          className={FIELD}
        />
      </Field>
      <Field label="Mood" id={`visit-mood-${visit.id}`}>
        <input
          id={`visit-mood-${visit.id}`}
          value={visit.changes?.mood ?? ""}
          onChange={(event) => onChange(setVisitMood(caseDocument, visit.id, event.target.value))}
          className={FIELD}
        />
      </Field>
      <Field label="Reason for visit" id={`visit-reason-${visit.id}`}>
        <input
          id={`visit-reason-${visit.id}`}
          value={visit.changes?.briefing?.reason_for_visit ?? ""}
          onChange={(event) => onChange(setVisitReason(caseDocument, visit.id, event.target.value))}
          className={FIELD}
        />
      </Field>
      <Field label="Blood pressure" id={`visit-bp-${visit.id}`}>
        <input
          id={`visit-bp-${visit.id}`}
          value={pressure?.value ?? ""}
          onChange={(event) => onChange(setVisitBloodPressure(caseDocument, visit.id, event.target.value))}
          className={FIELD}
        />
      </Field>
      {pressure ? (
        <div className="flex flex-col gap-2">
          <p id={`visit-change-status-${visit.id}`}>{statusWord(pressure.status)}</p>
          <button
            type="button"
            onClick={() =>
              onApprove("visit_changes", visit.id, pressure.status === "approved" ? "draft" : "approved")
            }
            className="h-9 rounded-[9px] border border-line-2 text-sm text-ink"
          >
            {pressure.status === "approved" ? `Return visit ${visit.id} to draft` : `Approve visit ${visit.id}`}
          </button>
        </div>
      ) : null}
      <button
        type="button"
        onClick={() => {
          const next = addFollowUpVisit(caseDocument);
          const added = next.visits?.[next.visits.length - 1];
          onChange(next);
          if (added) onAdded(added.id);
        }}
        className="h-9 rounded-[9px] border border-dashed border-line-4 text-sm text-ink"
      >
        Add follow-up visit
      </button>
      <div className="flex flex-col gap-3">
        <div className="text-[12.5px] font-semibold text-ink-soft">Decision points</div>
        {points.map((point) => (
          <DecisionEditor
            key={point.id}
            caseDocument={caseDocument}
            visitId={visit.id}
            point={point}
            vocab={vocab}
            onChange={onChange}
          />
        ))}
        <button
          type="button"
          disabled={points.length >= 4 || !firstChoice("topic", vocab, caseDocument)}
          onClick={() => onChange(addDecisionPoint(caseDocument, visit.id, vocab))}
          className="h-9 rounded-[9px] border border-dashed border-line-4 text-sm text-ink disabled:text-muted"
        >
          Add decision point
        </button>
      </div>
      <div className="flex flex-col gap-3">
        <div className="text-[12.5px] font-semibold text-ink-soft">Outcomes</div>
        {(visit.branches ?? []).map((branch) => (
          <OutcomeEditor
            key={branch.id}
            caseDocument={caseDocument}
            visit={visit}
            branch={branch}
            onChange={onChange}
            onApprove={onApprove}
          />
        ))}
        <button
          type="button"
          onClick={() => onChange(addOutcome(caseDocument, visit.id))}
          className="h-9 rounded-[9px] border border-dashed border-line-4 text-sm text-ink"
        >
          Add outcome
        </button>
      </div>
    </div>
  );
}

// One decision point: a label for people, and a listed check for the evaluator.
function DecisionEditor({
  caseDocument,
  visitId,
  point,
  vocab,
  onChange,
}: {
  caseDocument: CaseDocument;
  visitId: string;
  point: DecisionPoint;
  vocab: StudioVocab | null;
  onChange: (next: CaseDocument) => void;
}) {
  const read = readCheck(point.predicate);
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-line px-3 py-3">
      <Field label="Decision" id={`decision-label-${point.id}`}>
        <input
          id={`decision-label-${point.id}`}
          value={point.label}
          onChange={(event) => onChange(setDecisionLabel(caseDocument, visitId, point.id, event.target.value))}
          className={FIELD}
        />
      </Field>
      <Field label="Check" id={`decision-group-${point.id}`}>
        <select
          id={`decision-group-${point.id}`}
          value={read?.group ?? "leaf"}
          onChange={(event) => {
            const group = event.target.value as GroupKind;
            if (!GROUPS.includes(group)) return;
            onChange(setDecisionCheck(caseDocument, visitId, point.id, group, slotsFor(group, vocab, caseDocument)));
          }}
          className={FIELD}
        >
          {GROUPS.map((group) => (
            <option key={group} value={group}>
              {groupLabel(group)}
            </option>
          ))}
        </select>
      </Field>
      {read ? (
        read.slots.map((slot, index) => (
          <CheckSlotFields
            key={`${point.id}-${index}`}
            pointId={point.id}
            index={index}
            slot={slot}
            vocab={vocab}
            caseDocument={caseDocument}
            onSlot={(next) => {
              const slots = read.slots.map((item, slotIndex) => (slotIndex === index ? next : item));
              onChange(setDecisionCheck(caseDocument, visitId, point.id, read.group, slots));
            }}
          />
        ))
      ) : (
        <p className="text-sm text-ink">{checkCaption(point.predicate, vocab, caseDocument)}</p>
      )}
    </div>
  );
}

// Kind and value for one slot. The second slot uses a -2 id so two checks can sit on one decision.
function CheckSlotFields({
  pointId,
  index,
  slot,
  vocab,
  caseDocument,
  onSlot,
}: {
  pointId: string;
  index: number;
  slot: CheckSlot;
  vocab: StudioVocab | null;
  caseDocument: CaseDocument;
  onSlot: (slot: CheckSlot) => void;
}) {
  const suffix = index === 0 ? "" : `-${index + 1}`;
  const choices = choicesFor(slot.kind, slot.value, vocab, caseDocument);
  return (
    <div className="flex flex-col gap-2">
      <Field label={index === 0 ? "Kind" : "Second kind"} id={`decision-kind-${pointId}${suffix}`}>
        <select
          id={`decision-kind-${pointId}${suffix}`}
          value={slot.kind}
          onChange={(event) => {
            const kind = event.target.value as LeafKind;
            if (!KINDS.includes(kind)) return;
            onSlot({ kind, value: firstChoice(kind, vocab, caseDocument) ?? "" });
          }}
          className={FIELD}
        >
          {KINDS.map((kind) => (
            <option key={kind} value={kind}>
              {kindLabel(kind)}
            </option>
          ))}
        </select>
      </Field>
      {slot.kind === "open_question" ? null : (
        <Field label={index === 0 ? "Value" : "Second value"} id={`decision-value-${pointId}${suffix}`}>
          <select
            id={`decision-value-${pointId}${suffix}`}
            value={slot.value}
            onChange={(event) => onSlot({ ...slot, value: event.target.value })}
            className={FIELD}
          >
            {choices.map((choice) => (
              <option key={choice.id} value={choice.id}>
                {choice.label}
              </option>
            ))}
          </select>
        </Field>
      )}
    </div>
  );
}

// One faculty-written outcome. Yes and no are explicit; either leaves that decision out of the rule.
function OutcomeEditor({
  caseDocument,
  visit,
  branch,
  onChange,
  onApprove,
}: {
  caseDocument: CaseDocument;
  visit: Visit;
  branch: Branch;
  onChange: (next: CaseDocument) => void;
  onApprove: (group: ApprovalGroup, key: string, status: ItemStatus) => void;
}) {
  const fact = branch.changes?.add_facts?.[0];
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-line px-3 py-3">
      <p id={`outcome-status-${branch.id}`}>{statusWord(branch.status)}</p>
      <Field label="Outcome" id={`outcome-label-${branch.id}`}>
        <input
          id={`outcome-label-${branch.id}`}
          value={branch.label}
          onChange={(event) => onChange(setOutcomeLabel(caseDocument, visit.id, branch.id, event.target.value))}
          className={FIELD}
        />
      </Field>
      <Field label="What happens" id={`outcome-summary-${branch.id}`}>
        <textarea
          id={`outcome-summary-${branch.id}`}
          value={branch.summary}
          onChange={(event) => onChange(setOutcomeSummary(caseDocument, visit.id, branch.id, event.target.value))}
          className={`${FIELD} min-h-16`}
        />
      </Field>
      {(visit.decision_points ?? []).map((point) => (
        <Field key={point.id} label={`${point.label || point.id} result`} id={`outcome-when-${branch.id}-${point.id}`}>
          <select
            id={`outcome-when-${branch.id}-${point.id}`}
            value={whenChoice(branch, point.id)}
            onChange={(event) => {
              const choice = event.target.value as WhenChoice;
              if (choice !== "yes" && choice !== "no" && choice !== "either") return;
              onChange(setOutcomeWhen(caseDocument, visit.id, branch.id, point.id, choice));
            }}
            className={FIELD}
          >
            <option value="yes">Yes</option>
            <option value="no">No</option>
            <option value="either">Either</option>
          </select>
        </Field>
      ))}
      <Field label="Fact on this path" id={`outcome-fact-${branch.id}`}>
        <input
          id={`outcome-fact-${branch.id}`}
          value={fact?.text ?? ""}
          onChange={(event) => onChange(setOutcomeFact(caseDocument, visit.id, branch.id, event.target.value))}
          className={FIELD}
        />
      </Field>
      <button
        type="button"
        onClick={() => onApprove("branches", branch.id, branch.status === "approved" ? "draft" : "approved")}
        className="h-9 rounded-[9px] border border-line-2 text-sm text-ink"
      >
        {branch.status === "approved" ? `Return ${branch.id} to draft` : `Approve ${branch.id}`}
      </button>
    </div>
  );
}

// The tree for one visit. Cards wrap their text and the pane scrolls, so a long label stays readable.
function Diagram({
  visit,
  vocab,
  caseDocument,
}: {
  visit: Visit;
  vocab: StudioVocab | null;
  caseDocument: CaseDocument;
}) {
  const laid = layout(visit, vocab, caseDocument);
  return (
    <div className="relative" style={{ width: laid.width, height: laid.height }}>
      <svg width={laid.width} height={laid.height} className="absolute inset-0">
        <defs>
          <marker id="tree-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M0 0L10 5L0 10z" fill="var(--color-inactive)" />
          </marker>
        </defs>
        {laid.edges.map((edge) => (
          <path
            key={`${edge.from}-${edge.to}-${edge.label ?? "next"}`}
            d={edge.d}
            fill="none"
            stroke="#b6bad6"
            strokeWidth="1.5"
            markerEnd="url(#tree-arrow)"
          />
        ))}
      </svg>
      {laid.edges.map((edge) =>
        edge.label ? (
          <span
            key={`${edge.from}-${edge.to}-label`}
            className={`absolute inline-flex h-[22px] -translate-x-1/2 -translate-y-1/2 items-center rounded-md px-2 text-xs font-semibold ${edge.label === "Yes" ? "bg-ok-soft text-ok" : "bg-danger-soft text-danger"}`}
            style={{ left: edge.lx, top: edge.ly }}
          >
            {edge.label}
          </span>
        ) : null,
      )}
      {laid.cards.map((card) => (
        <div
          key={card.id}
          className="absolute overflow-hidden rounded-xl border border-line-3 bg-card px-3.5 py-3"
          style={{ left: card.x, top: card.y, width: CARD_W, height: card.h }}
        >
          <div className="text-[11px] font-bold tracking-[0.6px] text-indigo uppercase">{card.kicker}</div>
          <div className="mt-1 line-clamp-3 text-[14.5px] leading-snug font-semibold break-words">{card.title}</div>
          {card.detail ? <div className="mt-1 line-clamp-3 text-[12.5px] leading-snug break-words text-ink-soft">{card.detail}</div> : null}
        </div>
      ))}
    </div>
  );
}

// Same words as the patient editor, so a failed save is an alert and a success says Saved.
function SaveNotice({
  phase,
  reviewMessage,
  onSave,
}: {
  phase: SavePhase;
  reviewMessage: string | null;
  onSave: () => void;
}) {
  const saving = phase.kind === "saving";
  return (
    <div className="flex flex-col items-start gap-2">
      <PrimaryButton onClick={onSave} disabled={saving}>
        {saving ? "Saving case" : "Save case"}
      </PrimaryButton>
      {phase.kind === "saved" ? <p>Saved</p> : null}
      {phase.kind === "error" ? (
        <p role="alert" className="text-sm text-ink">
          {phase.message}
        </p>
      ) : null}
      {reviewMessage ? (
        <p role="alert" className="text-sm text-ink">
          {reviewMessage}
        </p>
      ) : null}
    </div>
  );
}

// A labeled control. The id is shared so the label and the field stay together.
function Field({ label, id, children }: { label: string; id: string; children: ReactNode }) {
  return (
    <label htmlFor={id} className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink-soft">
      {label}
      {children}
    </label>
  );
}

// Draft or Approved, with no other words, so the case badge is a separate Draft.
function statusWord(status: "draft" | "approved" | undefined): string {
  return status === "approved" ? "Approved" : "Draft";
}

// Yes, no, or either. A missing key means the outcome does not depend on that decision.
function whenChoice(branch: Branch, pointId: string): WhenChoice {
  const value = branch.when?.[pointId];
  if (value === true) return "yes";
  if (value === false) return "no";
  return "either";
}

// A new group starts from the first listed topic and action, so the predicate is executable.
function slotsFor(group: GroupKind, vocab: StudioVocab | null, caseDocument: CaseDocument): CheckSlot[] {
  const topic = firstChoice("topic", vocab, caseDocument) ?? "";
  const action = firstChoice("action", vocab, caseDocument) ?? topic;
  const one: CheckSlot = { kind: "topic", value: topic };
  if (group === "leaf" || group === "not") return [one];
  return [one, { kind: "action", value: action }];
}

// Keep a saved id visible even when this vocabulary load did not list it.
function choicesFor(kind: LeafKind, current: string, vocab: StudioVocab | null, caseDocument: CaseDocument) {
  const listed = optionList(kind, vocab, caseDocument);
  if (current && !listed.some((item) => item.id === current)) return [{ id: current, label: current }, ...listed];
  return listed;
}

type Card = { id: string; kicker: string; title: string; detail: string; x: number; y: number; h: number };
type DrawnEdge = { from: string; to: string; label: "Yes" | "No" | null; d: string; lx: number; ly: number };

// Place cards on separate rows so they do not cover one another. Yes and no are the only labeled edges.
function layout(visit: Visit, vocab: StudioVocab | null, caseDocument: CaseDocument): {
  cards: Card[];
  edges: DrawnEdge[];
  width: number;
  height: number;
} {
  const points = visit.decision_points ?? [];
  const branches = visit.branches ?? [];
  const columns = Math.max(1, points.length, branches.length);
  const width = Math.max(640, columns * CARD_W + (columns + 1) * GAP);
  const height = 540;
  const startX = placeRow(1, width)[0] ?? GAP;
  const cards: Card[] = [
    {
      id: visit.id,
      kicker: "Visit",
      title: visit.label || visit.id,
      detail: `Day ${visit.day}`,
      x: startX,
      y: ROW_Y.start,
      h: ROW_H.start,
    },
  ];
  const decisionX = placeRow(points.length, width);
  points.forEach((point, index) => {
    cards.push({
      id: point.id,
      kicker: "Decision",
      title: point.label || "Decision point",
      detail: checkCaption(point.predicate, vocab, caseDocument),
      x: decisionX[index] ?? GAP,
      y: ROW_Y.decision,
      h: ROW_H.decision,
    });
  });
  const outcomeX = placeRow(branches.length, width);
  branches.forEach((branch, index) => {
    cards.push({
      id: branch.id,
      kicker: "Outcome",
      title: branch.label || "Outcome",
      detail: branch.summary,
      x: outcomeX[index] ?? GAP,
      y: ROW_Y.outcome,
      h: ROW_H.outcome,
    });
  });
  const byId = new Map(cards.map((card) => [card.id, card]));
  const edges: DrawnEdge[] = [];
  for (const point of points) {
    const from = byId.get(visit.id);
    const to = byId.get(point.id);
    if (from && to) edges.push(drawEdge(from, to, null));
  }
  for (const branch of branches) {
    for (const point of points) {
      const want = branch.when?.[point.id];
      if (want !== true && want !== false) continue;
      const from = byId.get(point.id);
      const to = byId.get(branch.id);
      if (from && to) edges.push(drawEdge(from, to, want ? "Yes" : "No"));
    }
  }
  return { cards, edges, width, height };
}

// Spread a row across the canvas with a gap, so neighboring cards do not share pixels.
function placeRow(count: number, width: number): number[] {
  if (count <= 0) return [];
  const rowWidth = count * CARD_W + (count - 1) * GAP;
  const left = Math.max(GAP, (width - rowWidth) / 2);
  return Array.from({ length: count }, (_, index) => left + index * (CARD_W + GAP));
}

// Curve from the bottom of one card to the top of the next. The label sits in the gap.
function drawEdge(from: Card, to: Card, label: "Yes" | "No" | null): DrawnEdge {
  const x1 = from.x + CARD_W / 2;
  const y1 = from.y + from.h;
  const x2 = to.x + CARD_W / 2;
  const y2 = to.y;
  const mid = (y1 + y2) / 2;
  return {
    from: from.id,
    to: to.id,
    label,
    d: `M${x1} ${y1} C${x1} ${mid},${x2} ${mid},${x2} ${y2}`,
    lx: (x1 + x2) / 2,
    ly: mid,
  };
}
