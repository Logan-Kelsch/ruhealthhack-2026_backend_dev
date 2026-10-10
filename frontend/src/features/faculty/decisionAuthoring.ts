import type { CaseDocument, StudioVocab } from "../../api/client";

// The case document is the only place these edits live. The screen reads and writes this shape.
type Visit = NonNullable<CaseDocument["visits"]>[number];
type DecisionPoint = NonNullable<Visit["decision_points"]>[number];
type Branch = NonNullable<Visit["branches"]>[number];
type Predicate = DecisionPoint["predicate"];
type VisitChanges = NonNullable<Visit["changes"]>;
type Fact = NonNullable<VisitChanges["add_facts"]>[number];
type Vital = NonNullable<VisitChanges["vitals"]>[number];

export type LeafKind = "topic" | "action" | "maneuver" | "order" | "fact_disclosed" | "open_question";
export type GroupKind = "leaf" | "any" | "all" | "not" | "before";
export type WhenChoice = "yes" | "no" | "either";

// One listed check. value is a vocabulary id, or empty when the check is "open question".
export type CheckSlot = { kind: LeafKind; value: string };

type Choice = { id: string; label: string };

const LEAF_KINDS: LeafKind[] = ["topic", "action", "maneuver", "order", "fact_disclosed", "open_question"];
const OPERATOR_KEYS = new Set([
  "topic",
  "action",
  "maneuver",
  "order",
  "fact_disclosed",
  "open_question",
  "any",
  "all",
  "not",
  "before",
]);

// The words beside each operator. Faculty pick one of these; they do not type a rule.
export function groupLabel(group: GroupKind): string {
  switch (group) {
    case "leaf":
      return "One check";
    case "any":
      return "Any of these";
    case "all":
      return "All of these";
    case "not":
      return "Not this check";
    case "before":
      return "First check before the second";
    default: {
      const unreachable: never = group;
      return unreachable;
    }
  }
}

// The words beside each leaf. The id stays the vocabulary id.
export function kindLabel(kind: LeafKind): string {
  switch (kind) {
    case "topic":
      return "Topic";
    case "action":
      return "Action";
    case "maneuver":
      return "Exam maneuver";
    case "order":
      return "Order";
    case "fact_disclosed":
      return "Fact disclosed";
    case "open_question":
      return "Open question";
    default: {
      const unreachable: never = kind;
      return unreachable;
    }
  }
}

// Listed values for one leaf. Case-specific topics and actions sit beside the shared vocabulary.
export function optionList(kind: LeafKind, vocab: StudioVocab | null, caseDocument: CaseDocument): Choice[] {
  switch (kind) {
    case "topic":
      return [...(vocab?.topics ?? []), ...(caseDocument.topics ?? [])].map((item) => ({
        id: item.id,
        label: item.description,
      }));
    case "action":
      return [...(vocab?.actions ?? []), ...(caseDocument.actions ?? [])].map((item) => ({
        id: item.id,
        label: item.description,
      }));
    case "maneuver":
      return (vocab?.maneuvers ?? []).map((item) => ({ id: item.id, label: item.label }));
    case "order":
      return (vocab?.lab_panels ?? []).map((id) => ({ id, label: id }));
    case "fact_disclosed":
      return knownFacts(caseDocument).map((fact) => ({ id: fact.id, label: fact.text }));
    case "open_question":
      return [];
    default: {
      const unreachable: never = kind;
      return unreachable;
    }
  }
}

// A single operator, or null when the predicate is a group or has more than one key.
export function asLeaf(predicate: Predicate): CheckSlot | null {
  // A group is not a leaf, even when a child also has a topic.
  if (predicate.any?.length || predicate.all?.length || predicate.not || predicate.before?.length) return null;
  const filled = LEAF_KINDS.filter((kind) => kind !== "open_question" && Boolean(predicate[kind]));
  if (predicate.open_question === true) {
    if (filled.length > 0) return null;
    return { kind: "open_question", value: "" };
  }
  if (filled.length !== 1) return null;
  const kind = filled[0];
  // The remaining kinds store an id. Open question is handled above and has no id.
  if (kind !== "topic" && kind !== "action" && kind !== "maneuver" && kind !== "order" && kind !== "fact_disclosed") {
    return null;
  }
  return { kind, value: predicate[kind] ?? "" };
}

// The operator and its listed slots. Null means the saved predicate is kept until faculty choose a new one.
export function readCheck(predicate: Predicate): { group: GroupKind; slots: CheckSlot[] } | null {
  if (hasFreeText(predicate)) return null;
  const leaf = asLeaf(predicate);
  if (leaf) return { group: "leaf", slots: [leaf] };
  if (predicate.not) {
    const inner = asLeaf(predicate.not);
    if (!inner) return null;
    return { group: "not", slots: [inner] };
  }
  const list = predicate.any ?? predicate.all ?? predicate.before;
  if (!list?.length) return null;
  const slots = list.map((child) => asLeaf(child));
  if (slots.some((slot) => slot === null)) return null;
  const group: GroupKind = predicate.any ? "any" : predicate.all ? "all" : "before";
  return { group, slots: slots as CheckSlot[] };
}

// A short sentence for the card. It describes the saved check; it is not itself a predicate.
export function checkCaption(predicate: Predicate, vocab: StudioVocab | null, caseDocument: CaseDocument): string {
  const read = readCheck(predicate);
  if (!read) return "This saved check is kept until you choose a new one.";
  if (read.group === "leaf") return leafCaption(read.slots[0], vocab, caseDocument);
  if (read.group === "not") return `Yes when this is not true: ${leafCaption(read.slots[0], vocab, caseDocument)}`;
  const parts = read.slots.map((slot) => leafCaption(slot, vocab, caseDocument));
  if (read.group === "any") return `Yes when any match: ${parts.join("; ")}`;
  if (read.group === "all") return `Yes when all match: ${parts.join("; ")}`;
  return `Yes when the first happens before the second: ${parts.join("; ")}`;
}

// Build the predicate the evaluator understands. A sentence never becomes a key.
export function predicateFrom(group: GroupKind, slots: CheckSlot[]): Predicate | null {
  if (group === "leaf") return leafPredicate(slots[0]);
  if (group === "not") {
    const inner = leafPredicate(slots[0]);
    return inner ? { not: inner } : null;
  }
  const children = slots.map((slot) => leafPredicate(slot));
  if (children.some((child) => child === null)) return null;
  const list = children as Predicate[];
  if (group === "any") return { any: list };
  if (group === "all") return { all: list };
  return { before: list };
}

// The first listed id for a new check. Open question has no id.
export function firstChoice(kind: LeafKind, vocab: StudioVocab | null, caseDocument: CaseDocument): string | null {
  if (kind === "open_question") return "";
  return optionList(kind, vocab, caseDocument)[0]?.id ?? null;
}

// Add one yes/no point that starts as a listed topic. Four is the most a visit may have.
export function addDecisionPoint(
  caseDocument: CaseDocument,
  visitId: string,
  vocab: StudioVocab | null,
): CaseDocument {
  const topic = firstChoice("topic", vocab, caseDocument);
  if (!topic) return caseDocument;
  return mapVisit(caseDocument, visitId, (visit) => {
    const points = visit.decision_points ?? [];
    if (points.length >= 4) return visit;
    const id = nextSerialId("dp_", pointIds(caseDocument));
    const point: DecisionPoint = {
      id,
      label: "",
      affects: "patient",
      predicate: { topic },
    };
    return { ...visit, decision_points: [...points, point] };
  });
}

// Add a blank outcome. Faculty write the label, the summary, and which results it covers.
export function addOutcome(caseDocument: CaseDocument, visitId: string): CaseDocument {
  return mapVisit(caseDocument, visitId, (visit) => {
    const id = nextSerialId("b_", branchIds(caseDocument));
    const branch: Branch = {
      id,
      label: "",
      summary: "",
      status: "draft",
      when: {},
    };
    return { ...visit, branches: [...(visit.branches ?? []), branch] };
  });
}

// A later visit keeps a day at or after the previous one, so the gap stays in order.
export function addFollowUpVisit(caseDocument: CaseDocument): CaseDocument {
  const visits = caseDocument.visits ?? [];
  const id = nextSerialId("v", visits.map((visit) => visit.id));
  const previousDay = visits[visits.length - 1]?.day ?? 0;
  const visit: Visit = {
    id,
    label: "Follow-up",
    day: previousDay + 14,
    decision_points: [],
    branches: [],
  };
  return { ...caseDocument, visits: [...visits, visit] };
}

// The visit name faculty see on the diagram.
export function setVisitLabel(caseDocument: CaseDocument, visitId: string, label: string): CaseDocument {
  return mapVisit(caseDocument, visitId, (visit) => ({ ...visit, label }));
}

// Days are whole days from the first visit. Anything other than digits is left out.
export function setVisitDay(caseDocument: CaseDocument, visitId: string, raw: string): CaseDocument {
  const digits = raw.replace(/\D/g, "");
  const day = digits === "" ? 0 : Number(digits);
  return mapVisit(caseDocument, visitId, (visit) => ({ ...visit, day }));
}

// Mood at this visit. It is a visit change, not a new clinical fact.
export function setVisitMood(caseDocument: CaseDocument, visitId: string, mood: string): CaseDocument {
  return mapVisit(caseDocument, visitId, (visit) => withChanges(visit, { mood }));
}

// The reason the patient gives for this visit. Other briefing lines stay as they were.
export function setVisitReason(caseDocument: CaseDocument, visitId: string, reason: string): CaseDocument {
  return mapVisit(caseDocument, visitId, (visit) => {
    const briefing = visit.changes?.briefing;
    return withChanges(visit, {
      briefing: {
        setting: briefing?.setting ?? "",
        reason_for_visit: reason,
        goal: briefing?.goal ?? "",
        student_role: briefing?.student_role ?? "",
        show_doorway_vitals: briefing?.show_doorway_vitals ?? true,
      },
    });
  });
}

// Blood pressure typed by faculty. Editing it returns the value to draft.
export function setVisitBloodPressure(caseDocument: CaseDocument, visitId: string, value: string): CaseDocument {
  return mapVisit(caseDocument, visitId, (visit) => {
    const vitals = [...(visit.changes?.vitals ?? [])];
    const next: Vital = {
      key: "bp",
      label: "Blood pressure",
      value,
      unit: "mmHg",
      status: "draft",
      source: { kind: "faculty", ref: null, by: null },
    };
    const index = vitals.findIndex((item) => item.key === "bp");
    if (index >= 0) vitals[index] = { ...vitals[index], ...next };
    else vitals.push(next);
    return withChanges(visit, { vitals });
  });
}

// The question faculty read. The predicate stays whatever check was already chosen.
export function setDecisionLabel(
  caseDocument: CaseDocument,
  visitId: string,
  pointId: string,
  label: string,
): CaseDocument {
  return mapPoint(caseDocument, visitId, pointId, (point) => ({ ...point, label }));
}

// Replace the check with operators and listed ids. The label is not copied into the predicate.
export function setDecisionCheck(
  caseDocument: CaseDocument,
  visitId: string,
  pointId: string,
  group: GroupKind,
  slots: CheckSlot[],
): CaseDocument {
  const predicate = predicateFrom(group, slots);
  if (!predicate) return caseDocument;
  return mapPoint(caseDocument, visitId, pointId, (point) => ({ ...point, predicate }));
}

// Outcome name. A change after approval has to be approved again.
export function setOutcomeLabel(
  caseDocument: CaseDocument,
  visitId: string,
  branchId: string,
  label: string,
): CaseDocument {
  return mapBranch(caseDocument, visitId, branchId, (branch) => ({ ...branch, label, status: "draft" }));
}

// What the patient is like on this path. Faculty write it; nothing is generated.
export function setOutcomeSummary(
  caseDocument: CaseDocument,
  visitId: string,
  branchId: string,
  summary: string,
): CaseDocument {
  return mapBranch(caseDocument, visitId, branchId, (branch) => ({ ...branch, summary, status: "draft" }));
}

// Yes, no, or either. Either drops the key so that result does not limit the outcome.
export function setOutcomeWhen(
  caseDocument: CaseDocument,
  visitId: string,
  branchId: string,
  pointId: string,
  choice: WhenChoice,
): CaseDocument {
  return mapBranch(caseDocument, visitId, branchId, (branch) => {
    const when = { ...(branch.when ?? {}) };
    if (choice === "either") delete when[pointId];
    else when[pointId] = choice === "yes";
    return { ...branch, when, status: "draft" };
  });
}

// One new fact on this path. Clearing the box removes that fact and leaves any others.
export function setOutcomeFact(
  caseDocument: CaseDocument,
  visitId: string,
  branchId: string,
  text: string,
): CaseDocument {
  return mapBranch(caseDocument, visitId, branchId, (branch) => {
    const facts = [...(branch.changes?.add_facts ?? [])];
    const trimmed = text.trim();
    if (!trimmed) facts.shift();
    else if (facts[0]) facts[0] = { ...facts[0], text, status: "draft" };
    else facts.unshift(draftFact(`f_${branchId}`, text));
    return {
      ...branch,
      status: "draft",
      changes: { ...branch.changes, add_facts: facts },
    };
  });
}

// The sentence that blocks a save. An empty visit list, and a visit with no decision points, can still be saved.
export function visitAuthoringProblem(caseDocument: CaseDocument): string | null {
  const visits = caseDocument.visits ?? [];
  const seen = new Set<string>();
  let previousDay: number | null = null;
  for (let index = 0; index < visits.length; index += 1) {
    const visit = visits[index];
    if (!visit) continue;
    if (seen.has(visit.id)) return `Visit id ${visit.id} is used more than once.`;
    seen.add(visit.id);
    if (!visit.label.trim()) return "Write a label for each visit.";
    if (previousDay !== null && visit.day < previousDay) {
      return `Visit ${visit.label} starts before the previous visit.`;
    }
    previousDay = visit.day;
    const problem = oneVisitProblem(visits, index);
    if (problem) return problem;
  }
  return null;
}

// Count first, then missing words, then coverage. Coverage is skipped when the visit is already invalid.
function oneVisitProblem(visits: Visit[], index: number): string | null {
  const visit = visits[index];
  if (!visit) return null;
  const points = visit.decision_points ?? [];
  const count = points.length;
  // Zero means the visit is not branched yet. One, or more than four, is not an authored tree.
  if (count !== 0 && (count < 2 || count > 4)) {
    return `Visit ${visit.label} needs 2 to 4 decision points.`;
  }
  const pointIds = new Set<string>();
  for (const point of points) {
    if (pointIds.has(point.id)) return `Decision point ${point.id} is used more than once on ${visit.label}.`;
    pointIds.add(point.id);
    if (!point.label.trim()) return "Write a label for each decision point.";
    if (hasFreeText(point.predicate) || !readCheck(point.predicate)) {
      return "Choose a check from the list for each decision point.";
    }
    const read = readCheck(point.predicate);
    if (read?.slots.some((slot) => slot.kind !== "open_question" && !slot.value.trim())) {
      return "Choose a check from the list for each decision point.";
    }
  }
  for (const branch of visit.branches ?? []) {
    if (!branch.label.trim() || !branch.summary.trim()) return "Write what happens for each outcome.";
    for (const dpId of Object.keys(branch.when ?? {})) {
      if (!pointIds.has(dpId)) {
        return `Outcome ${branch.id} depends on decision point ${dpId}, which is not on visit ${visit.id}.`;
      }
    }
  }
  if (!covers(visits, index)) return `Visit ${visit.label} does not cover every yes or no result.`;
  return null;
}

// Patient checks, plus any id an outcome names, must each have a faculty-written outcome.
function covers(visits: Visit[], index: number): boolean {
  const visit = visits[index];
  if (!visit) return true;
  const resultIds = resultIdsFor(visit);
  if (resultIds.length === 0) return true;
  const branches = visit.branches ?? [];
  const last = index === visits.length - 1;
  // The last visit may score a decision and stop. A later visit needs an outcome for each result.
  if (branches.length === 0 && last) return true;
  const priors = priorPaths(visits, index);
  for (const prior of priors) {
    for (const assignment of assignments(resultIds)) {
      if (!matched(visit, assignment, prior)) return false;
    }
  }
  return true;
}

// Decision points that choose what happens next.
function resultIdsFor(visit: Visit): string[] {
  const ids: string[] = [];
  for (const point of visit.decision_points ?? []) {
    if (point.affects !== "score" && !ids.includes(point.id)) ids.push(point.id);
  }
  for (const branch of visit.branches ?? []) {
    for (const id of Object.keys(branch.when ?? {})) {
      if (!ids.includes(id)) ids.push(id);
    }
  }
  return ids;
}

// The first visit has no earlier outcome. A later visit is reached through each previous outcome.
function priorPaths(visits: Visit[], index: number): Array<string | null> {
  if (index === 0) return [null];
  const previous = visits[index - 1]?.branches ?? [];
  if (previous.length === 0) return [null];
  return previous.map((branch) => branch.id);
}

// Every yes/no combination. A visit has at most four decision points, so this stays small.
function assignments(ids: string[]): Array<Record<string, boolean>> {
  const rows: Array<Record<string, boolean>> = [];
  for (let mask = 0; mask < 1 << ids.length; mask += 1) {
    const row: Record<string, boolean> = {};
    ids.forEach((id, bit) => {
      row[id] = Boolean(mask & (1 << bit));
    });
    rows.push(row);
  }
  return rows;
}

// First matching outcome wins, same as the encounter evaluator.
function matched(visit: Visit, assignment: Record<string, boolean>, prior: string | null): boolean {
  for (const branch of visit.branches ?? []) {
    const priors = branch.after_branches ?? [];
    if (priors.length > 0 && (prior === null || !priors.includes(prior))) continue;
    const when = branch.when ?? {};
    const fits = Object.entries(when).every(([id, want]) => assignment[id] === want);
    if (fits) return true;
  }
  return false;
}

// A key other than the supported operators is free text. It is not sent as a predicate.
function hasFreeText(predicate: Predicate): boolean {
  return Object.entries(predicate).some(([key, value]) => value != null && !OPERATOR_KEYS.has(key));
}

// One operator object. An empty id is not a check, so the predicate is not built.
function leafPredicate(slot: CheckSlot | undefined): Predicate | null {
  if (!slot) return null;
  switch (slot.kind) {
    case "topic":
      return slot.value ? { topic: slot.value } : null;
    case "action":
      return slot.value ? { action: slot.value } : null;
    case "maneuver":
      return slot.value ? { maneuver: slot.value } : null;
    case "order":
      return slot.value ? { order: slot.value } : null;
    case "fact_disclosed":
      return slot.value ? { fact_disclosed: slot.value } : null;
    case "open_question":
      return { open_question: true };
    default: {
      const unreachable: never = slot.kind;
      return unreachable;
    }
  }
}

// The words on the card for one listed check.
function leafCaption(slot: CheckSlot | undefined, vocab: StudioVocab | null, caseDocument: CaseDocument): string {
  if (!slot) return "Choose a check from the list";
  if (slot.kind === "open_question") return "Yes when the student asks an open question";
  const found = optionList(slot.kind, vocab, caseDocument).find((item) => item.id === slot.value);
  const name = found?.label ?? slot.value;
  return `${kindLabel(slot.kind)}: ${name}`;
}

// Facts a check may name: the chart, plus facts a visit or outcome adds.
function knownFacts(caseDocument: CaseDocument): Fact[] {
  const facts = [...(caseDocument.facts ?? [])];
  for (const visit of caseDocument.visits ?? []) {
    facts.push(...(visit.changes?.add_facts ?? []));
    for (const branch of visit.branches ?? []) facts.push(...(branch.changes?.add_facts ?? []));
  }
  return facts;
}

// A faculty-written fact. It stays draft until that outcome is approved.
function draftFact(id: string, text: string): Fact {
  return {
    id,
    category: "history",
    cue: false,
    safety: false,
    text,
    tier: "discoverable",
    status: "draft",
    source: { kind: "faculty", ref: null, by: null },
  };
}

// Replace one part of the visit change list and keep the rest.
function withChanges(visit: Visit, patch: Partial<VisitChanges>): Visit {
  return { ...visit, changes: { ...visit.changes, ...patch } };
}

// Copy the case with one visit replaced.
function mapVisit(caseDocument: CaseDocument, visitId: string, change: (visit: Visit) => Visit): CaseDocument {
  return {
    ...caseDocument,
    visits: (caseDocument.visits ?? []).map((visit) => (visit.id === visitId ? change(visit) : visit)),
  };
}

// Copy the visit with one decision point replaced.
function mapPoint(
  caseDocument: CaseDocument,
  visitId: string,
  pointId: string,
  change: (point: DecisionPoint) => DecisionPoint,
): CaseDocument {
  return mapVisit(caseDocument, visitId, (visit) => ({
    ...visit,
    decision_points: (visit.decision_points ?? []).map((point) => (point.id === pointId ? change(point) : point)),
  }));
}

// Copy the visit with one outcome replaced.
function mapBranch(
  caseDocument: CaseDocument,
  visitId: string,
  branchId: string,
  change: (branch: Branch) => Branch,
): CaseDocument {
  return mapVisit(caseDocument, visitId, (visit) => ({
    ...visit,
    branches: (visit.branches ?? []).map((branch) => (branch.id === branchId ? change(branch) : branch)),
  }));
}

// Decision-point ids already used, so the next row does not reuse one.
function pointIds(caseDocument: CaseDocument): string[] {
  return (caseDocument.visits ?? []).flatMap((visit) => (visit.decision_points ?? []).map((point) => point.id));
}

// Outcome ids already used, so the next row does not reuse one.
function branchIds(caseDocument: CaseDocument): string[] {
  return (caseDocument.visits ?? []).flatMap((visit) => (visit.branches ?? []).map((branch) => branch.id));
}

// dp_1, b_1, v2. The number is the next free suffix, so a deleted row does not reuse an id still on the case.
function nextSerialId(prefix: string, ids: string[]): string {
  const used = new Set(ids);
  let n = 1;
  while (used.has(`${prefix}${n}`)) n += 1;
  return `${prefix}${n}`;
}
