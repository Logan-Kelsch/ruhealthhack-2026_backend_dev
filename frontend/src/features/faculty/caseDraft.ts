import type { CaseDocument } from "../../api/client";

type Fact = NonNullable<CaseDocument["facts"]>[number];
type Source = NonNullable<Fact["source"]>;
type Lab = NonNullable<CaseDocument["labs"]>[number];

const FACT_ID_PREFIX = "f_";

// The words under a value. The kind is the signal; the citation is the rest of the sentence.
export function sourceLabel(source?: Source): string {
  if (!source?.kind) return "Source: not recorded";
  const parts: string[] = [source.kind];
  if (source.ref) parts.push(source.ref);
  if (source.by) parts.push(source.by);
  return `Source: ${parts.join(" · ")}`;
}

// A faculty change to a ruled or computed value must stop citing that rule.
export function keepFacultySource(source?: Source): Source {
  if (source?.kind === "faculty") return source;
  return { kind: "faculty", ref: null, by: null };
}

// High and low are words, so color is not the only way to see an out-of-range result.
export function labFlag(lab: Pick<Lab, "value" | "ref_low" | "ref_high">): "High" | "Low" | null {
  if (typeof lab.value !== "number") return null;
  if (typeof lab.ref_low === "number" && lab.value < lab.ref_low) return "Low";
  if (typeof lab.ref_high === "number" && lab.value > lab.ref_high) return "High";
  return null;
}

// A numeric lab stays a number. Anything else, such as "Negative", stays text.
export function labValueFromInput(raw: string): number | string {
  const trimmed = raw.trim();
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) return Number(trimmed);
  return raw;
}

// The id is chosen when the row is added. Later edits of the text do not change it.
export function nextFactId(facts: { id: string }[]): string {
  const used = new Set(facts.map((fact) => fact.id));
  let n = facts.length + 1;
  while (used.has(`${FACT_ID_PREFIX}${n}`)) n += 1;
  return `${FACT_ID_PREFIX}${n}`;
}

// One sentence the faculty member must fix before a save can drop this fact.
export function factReferenceNotes(caseDocument: CaseDocument, factId: string): string[] {
  const notes: string[] = [];
  for (const objective of caseDocument.objectives ?? []) {
    if ((objective.expected_discoveries ?? []).includes(factId)) {
      notes.push(`Learning objective ${objective.id} still expects this fact.`);
    }
  }
  for (const other of caseDocument.facts ?? []) {
    if (other.id !== factId && (other.unlock?.requires_facts ?? []).includes(factId)) {
      notes.push(`Fact ${other.id} is withheld until this fact is disclosed.`);
    }
  }
  for (const lab of caseDocument.labs ?? []) {
    if (lab.release?.fact_id === factId) notes.push(`Lab ${lab.name} is released when this fact is disclosed.`);
  }
  for (const diagnosis of caseDocument.diagnoses ?? []) {
    if (diagnosis.release?.fact_id === factId) {
      notes.push(`Diagnosis ${diagnosis.name} is released when this fact is disclosed.`);
    }
  }
  for (const medication of caseDocument.medications ?? []) {
    if (medication.release?.fact_id === factId) {
      notes.push(`Medication ${medication.name} is released when this fact is disclosed.`);
    }
  }
  for (const allergy of caseDocument.allergies ?? []) {
    if (allergy.release?.fact_id === factId) {
      notes.push(`Allergy ${allergy.substance} is released when this fact is disclosed.`);
    }
  }
  for (const artifact of caseDocument.artifacts ?? []) {
    if (artifact.release?.fact_id === factId) notes.push(`File ${artifact.title} is released when this fact is disclosed.`);
  }
  for (const visit of caseDocument.visits ?? []) {
    notes.push(...changeNotes(visit.label, visit.changes, factId));
    for (const point of visit.decision_points ?? []) {
      if (predicateMentions(point.predicate, factId)) {
        notes.push(`Visit ${visit.label} decision point ${point.id} checks whether this fact was disclosed.`);
      }
    }
    for (const branch of visit.branches ?? []) {
      notes.push(...changeNotes(`${visit.label}, ${branch.label}`, branch.changes, factId));
    }
  }
  return notes;
}

// Uses inside one visit or branch change list. where is the label faculty see.
function changeNotes(
  where: string,
  changes: NonNullable<CaseDocument["visits"]>[number]["changes"],
  factId: string,
): string[] {
  if (!changes) return [];
  const notes: string[] = [];
  if ((changes.remove_facts ?? []).includes(factId)) notes.push(`${where} still removes this fact.`);
  if (changes.update_facts && factId in changes.update_facts) notes.push(`${where} still updates this fact.`);
  for (const lab of changes.labs ?? []) {
    if (lab.release?.fact_id === factId) notes.push(`${where} releases lab ${lab.name} when this fact is disclosed.`);
  }
  for (const artifact of changes.artifacts ?? []) {
    if (artifact.release?.fact_id === factId) notes.push(`${where} releases file ${artifact.title} when this fact is disclosed.`);
  }
  for (const medication of changes.medications ?? []) {
    if (medication.release?.fact_id === factId) {
      notes.push(`${where} releases medication ${medication.name} when this fact is disclosed.`);
    }
  }
  return notes;
}

// True when a decision predicate names this fact, including any/all/not/before groups.
function predicateMentions(predicate: unknown, factId: string): boolean {
  if (typeof predicate !== "object" || predicate === null) return false;
  if (Array.isArray(predicate)) return predicate.some((item) => predicateMentions(item, factId));
  const record = predicate as Record<string, unknown>;
  if (record.fact_disclosed === factId) return true;
  return Object.values(record).some((value) => predicateMentions(value, factId));
}

// Blank required text is a validation failure. It is not sent, and it is not a successful save.
export function saveProblem(caseDocument: CaseDocument): string | null {
  if (!caseDocument.profile.name.trim()) return "Enter the patient's name before saving.";
  for (const fact of caseDocument.facts ?? []) {
    if (!fact.text.trim()) return "Write each fact before saving.";
  }
  for (const vital of caseDocument.vitals ?? []) {
    if (!vital.value.trim()) return "Enter each vital sign before saving.";
  }
  for (const lab of caseDocument.labs ?? []) {
    if (typeof lab.value === "string" && !lab.value.trim()) return "Enter each lab value before saving.";
    if (!lab.name.trim() || !lab.key.trim()) return "Enter a name and key for each lab before saving.";
  }
  for (const finding of caseDocument.exam ?? []) {
    if (!finding.maneuver.trim() || !finding.finding.trim()) return "Enter each exam finding before saving.";
  }
  for (const diagnosis of caseDocument.diagnoses ?? []) {
    if (!diagnosis.name.trim()) return "Enter each diagnosis before saving.";
  }
  for (const medication of caseDocument.medications ?? []) {
    if (!medication.name.trim()) return "Enter each medication before saving.";
  }
  for (const allergy of caseDocument.allergies ?? []) {
    if (!allergy.substance.trim()) return "Enter each allergy before saving.";
  }
  for (const objective of caseDocument.objectives ?? []) {
    if (!objective.text.trim()) return "Write each learning objective before saving.";
  }
  return null;
}
