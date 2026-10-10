import { useState, type ReactNode } from "react";
import type { ApprovalGroup, CaseDocument, Icd10Match, ItemStatus, StudioVocab } from "../../api/client";
import { Card, CardHead, PrimaryButton } from "../../components/ui";
import { keepFacultySource, labFlag, labValueFromInput, nextFactId, sourceLabel } from "./caseDraft";

type Fact = NonNullable<CaseDocument["facts"]>[number];
type Source = NonNullable<Fact["source"]>;

export type SavePhase = { kind: "idle" } | { kind: "saving" } | { kind: "saved" } | { kind: "error"; message: string };

const FIELD = "w-full rounded-xl border border-line-2 bg-card px-3 py-2 text-sm text-ink outline-none";

const FACT_CATEGORIES = [
  "presenting",
  "history",
  "medication",
  "allergy",
  "social",
  "diet",
  "family",
  "psych",
  "ros",
  "personal",
  "goal",
  "fear",
  "small_talk",
  "other",
];

const TIERS = ["initial", "discoverable", "reluctant", "hidden"] as const;
const LITERACY = ["low", "medium", "high"] as const;
const TRAITS = ["openness", "irritability", "verbosity", "humor"];
const VITALS = [
  { key: "bp", label: "Blood pressure" },
  { key: "hr", label: "Heart rate" },
  { key: "rr", label: "Breathing rate" },
  { key: "temp_c", label: "Temperature" },
  { key: "spo2", label: "Oxygen saturation" },
  { key: "weight", label: "Weight" },
  { key: "height", label: "Height" },
  { key: "bmi", label: "Body mass index" },
];

type EditorProps = {
  caseDocument: CaseDocument;
  vocab: StudioVocab | null;
  vocabError: string | null;
  savePhase: SavePhase;
  reviewMessage: string | null;
  lookupResults: Icd10Match[];
  lookupMessage: string | null;
  factHold: string | null;
  notes: string[];
  onChange: (next: CaseDocument) => void;
  onSave: () => void;
  onApprove: (group: ApprovalGroup, key: string, status: ItemStatus) => void;
  onAutofill: (panels: string[], vitals: boolean) => void;
  onLookup: (query: string) => void;
  onUseDiagnosis: (match: Icd10Match) => void;
  onRemoveFact: (factId: string) => void;
};

// Profile, clinical lists, and the save control. Objectives live on their own tab.
export function CaseEditor(props: EditorProps) {
  return (
    <div className="flex flex-col gap-5">
      <ProfileSection {...props} />
      <BriefingSection {...props} />
      <FactSection {...props} />
      <VitalSection {...props} />
      <LabSection {...props} />
      <ExamSection {...props} />
      <DiagnosisSection {...props} />
      <MedicationSection {...props} />
      <AllergySection {...props} />
      <SaveBar phase={props.savePhase} reviewMessage={props.reviewMessage} onSave={props.onSave} />
    </div>
  );
}

// Learning objectives and the same save. A fact link is how an objective names a fact.
export function ObjectiveEditor({
  caseDocument,
  vocab,
  savePhase,
  reviewMessage,
  onChange,
  onSave,
  onApprove,
}: Pick<EditorProps, "caseDocument" | "vocab" | "savePhase" | "reviewMessage" | "onChange" | "onSave" | "onApprove">) {
  const objectives = caseDocument.objectives ?? [];
  return (
    <div className="flex flex-col gap-5">
      <Section title="Learning objectives">
        {objectives.length === 0 ? <p className="text-muted">No learning objectives yet</p> : null}
        {objectives.map((objective) => (
          <div key={objective.id} className="flex flex-col gap-2 border-t border-hair pt-3">
            <p className="text-[12.5px] text-muted">{objective.id}</p>
            <label htmlFor={`objective-text-${objective.id}`} className="font-medium">
              Objective
            </label>
            <textarea
              id={`objective-text-${objective.id}`}
              value={objective.text}
              onChange={(event) =>
                onChange({
                  ...caseDocument,
                  objectives: objectives.map((item) =>
                    item.id === objective.id ? { ...item, text: event.target.value } : item,
                  ),
                })
              }
              className={`${FIELD} min-h-20`}
            />
            <fieldset className="flex flex-col gap-1">
              <legend className="font-medium">Expected discoveries</legend>
              {(caseDocument.facts ?? []).map((fact) => {
                const checked = (objective.expected_discoveries ?? []).includes(fact.id);
                return (
                  <label key={fact.id} className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => {
                        const current = objective.expected_discoveries ?? [];
                        const expected_discoveries = checked
                          ? current.filter((id) => id !== fact.id)
                          : [...current, fact.id];
                        onChange({
                          ...caseDocument,
                          objectives: objectives.map((item) =>
                            item.id === objective.id ? { ...item, expected_discoveries } : item,
                          ),
                        });
                      }}
                    />
                    <span>
                      {fact.id}: {fact.text || "Untitled fact"}
                    </span>
                  </label>
                );
              })}
            </fieldset>
            <ActionChecks
              objectiveId={objective.id}
              selected={objective.expected_actions ?? []}
              vocab={vocab}
              onChange={(expected_actions) =>
                onChange({
                  ...caseDocument,
                  objectives: objectives.map((item) => (item.id === objective.id ? { ...item, expected_actions } : item)),
                })
              }
            />
            <ReviewRow
              status={objective.status}
              approveLabel={objective.id}
              onApprove={() => onApprove("objectives", objective.id, "approved")}
              onReturn={() => onApprove("objectives", objective.id, "draft")}
            />
          </div>
        ))}
        <div>
          <button
            type="button"
            className="text-sm font-medium text-ink underline"
            onClick={() =>
              onChange({
                ...caseDocument,
                objectives: [
                  ...objectives,
                  {
                    id: nextObjectiveId(objectives),
                    text: "",
                    status: "draft",
                    expected_discoveries: [],
                    expected_actions: [],
                  },
                ],
              })
            }
          >
            Add learning objective
          </button>
        </div>
      </Section>
      <SaveBar phase={savePhase} reviewMessage={reviewMessage} onSave={onSave} />
    </div>
  );
}

// The save control shared by the patient and objective tabs. Saved is separate from the button.
function SaveBar({
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

// Name, age, sex, and the personality the phraser is allowed to use.
function ProfileSection({ caseDocument, onChange }: EditorProps) {
  const profile = caseDocument.profile;
  const personality = profile.personality ?? {
    summary: "",
    communication_style: "",
    health_literacy: "medium" as const,
    mood: "neutral",
    traits: {},
    example_lines: [],
  };
  const traitKeys = [...new Set([...TRAITS, ...Object.keys(personality.traits ?? {})])];
  return (
    <Section title="Patient">
      <p>{caseDocument.description}</p>
      <Field label="Name" id="profile-name">
        <input
          id="profile-name"
          value={profile.name}
          onChange={(event) => onChange({ ...caseDocument, profile: { ...profile, name: event.target.value } })}
          className={FIELD}
        />
      </Field>
      <Field label="Age" id="profile-age">
        <input
          id="profile-age"
          inputMode="numeric"
          value={String(profile.age)}
          onChange={(event) => {
            const age = Number(event.target.value);
            // Leave the stored age alone until the field is a whole number.
            if (!Number.isInteger(age) || age < 0) return;
            onChange({ ...caseDocument, profile: { ...profile, age } });
          }}
          className={FIELD}
        />
      </Field>
      <Field label="Sex" id="profile-sex">
        <select
          id="profile-sex"
          value={profile.sex}
          onChange={(event) =>
            onChange({
              ...caseDocument,
              profile: { ...profile, sex: event.target.value as CaseDocument["profile"]["sex"] },
            })
          }
          className={FIELD}
        >
          <option value="female">Female</option>
          <option value="male">Male</option>
          <option value="other">Other</option>
        </select>
      </Field>
      <Field label="Occupation" id="profile-occupation">
        <input
          id="profile-occupation"
          value={profile.occupation ?? ""}
          onChange={(event) =>
            onChange({ ...caseDocument, profile: { ...profile, occupation: event.target.value || null } })
          }
          className={FIELD}
        />
      </Field>
      <Field label="Personality" id="personality-summary">
        <textarea
          id="personality-summary"
          value={personality.summary}
          onChange={(event) =>
            onChange({
              ...caseDocument,
              profile: { ...profile, personality: { ...personality, summary: event.target.value } },
            })
          }
          className={`${FIELD} min-h-20`}
        />
      </Field>
      <Field label="Communication style" id="personality-style">
        <input
          id="personality-style"
          value={personality.communication_style}
          onChange={(event) =>
            onChange({
              ...caseDocument,
              profile: { ...profile, personality: { ...personality, communication_style: event.target.value } },
            })
          }
          className={FIELD}
        />
      </Field>
      <Field label="Health literacy" id="personality-literacy">
        <select
          id="personality-literacy"
          value={personality.health_literacy}
          onChange={(event) =>
            onChange({
              ...caseDocument,
              profile: {
                ...profile,
                personality: {
                  ...personality,
                  health_literacy: event.target.value as (typeof LITERACY)[number],
                },
              },
            })
          }
          className={FIELD}
        >
          {LITERACY.map((level) => (
            <option key={level} value={level}>
              {literacyLabel(level)}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Mood" id="personality-mood">
        <input
          id="personality-mood"
          value={personality.mood}
          onChange={(event) =>
            onChange({
              ...caseDocument,
              profile: { ...profile, personality: { ...personality, mood: event.target.value } },
            })
          }
          className={FIELD}
        />
      </Field>
      {traitKeys.map((trait) => (
        <Field key={trait} label={traitLabel(trait)} id={`personality-trait-${trait}`}>
          <input
            id={`personality-trait-${trait}`}
            inputMode="decimal"
            value={personality.traits?.[trait] ?? ""}
            onChange={(event) => {
              const raw = event.target.value.trim();
              const traits = { ...(personality.traits ?? {}) };
              if (raw === "") {
                delete traits[trait];
              } else {
                const value = Number(raw);
                if (!Number.isFinite(value)) return;
                traits[trait] = value;
              }
              onChange({
                ...caseDocument,
                profile: { ...profile, personality: { ...personality, traits } },
              });
            }}
            className={FIELD}
          />
        </Field>
      ))}
    </Section>
  );
}

// What the student sees before the encounter. These fields are the briefing, not a new case.
function BriefingSection({ caseDocument, onChange }: EditorProps) {
  const briefing = caseDocument.briefing ?? {
    setting: "",
    reason_for_visit: "",
    goal: "",
    student_role: "",
    show_doorway_vitals: true,
  };
  // One briefing field at a time, so the other doorway fields stay as they were.
  function setBriefing(patch: Partial<typeof briefing>) {
    onChange({ ...caseDocument, briefing: { ...briefing, ...patch } });
  }
  return (
    <Section title="Briefing">
      <Field label="Setting" id="briefing-setting">
        <input
          id="briefing-setting"
          value={briefing.setting}
          onChange={(event) => setBriefing({ setting: event.target.value })}
          className={FIELD}
        />
      </Field>
      <Field label="Reason for the visit" id="briefing-reason">
        <input
          id="briefing-reason"
          value={briefing.reason_for_visit}
          onChange={(event) => setBriefing({ reason_for_visit: event.target.value })}
          className={FIELD}
        />
      </Field>
      <Field label="Goal" id="briefing-goal">
        <input
          id="briefing-goal"
          value={briefing.goal}
          onChange={(event) => setBriefing({ goal: event.target.value })}
          className={FIELD}
        />
      </Field>
      <Field label="Student role" id="briefing-role">
        <input
          id="briefing-role"
          value={briefing.student_role}
          onChange={(event) => setBriefing({ student_role: event.target.value })}
          className={FIELD}
        />
      </Field>
    </Section>
  );
}

// Facts keep their ids. Removing one that is still named shows those names first.
function FactSection({ caseDocument, vocab, factHold, onChange, onApprove, onRemoveFact }: EditorProps) {
  const facts = caseDocument.facts ?? [];
  return (
    <Section title="Facts">
      {factHold ? (
        <p role="alert" className="text-sm text-ink">
          {factHold}
        </p>
      ) : null}
      {facts.length === 0 ? <p className="text-muted">No facts yet</p> : null}
      {facts.map((fact) => (
        <div key={fact.id} className="flex flex-col gap-2 border-t border-hair pt-3">
          <p className="text-[12.5px] text-muted">{fact.id}</p>
          <Field label="Fact" id={`fact-text-${fact.id}`}>
            <textarea
              id={`fact-text-${fact.id}`}
              value={fact.text}
              onChange={(event) => replaceFact(caseDocument, onChange, fact.id, { text: event.target.value }, true)}
              className={`${FIELD} min-h-20`}
            />
          </Field>
          <Field label="What the patient can say" id={`fact-say-${fact.id}`}>
            <textarea
              id={`fact-say-${fact.id}`}
              value={fact.say ?? ""}
              onChange={(event) =>
                replaceFact(caseDocument, onChange, fact.id, { say: event.target.value || null }, true)
              }
              className={`${FIELD} min-h-16`}
            />
          </Field>
          <Field label="Category" id={`fact-category-${fact.id}`}>
            <select
              id={`fact-category-${fact.id}`}
              value={fact.category || "history"}
              onChange={(event) => replaceFact(caseDocument, onChange, fact.id, { category: event.target.value })}
              className={FIELD}
            >
              {categoryOptions(fact.category).map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Disclosure" id={`fact-tier-${fact.id}`}>
            <select
              id={`fact-tier-${fact.id}`}
              value={fact.tier || "discoverable"}
              onChange={(event) =>
                replaceFact(caseDocument, onChange, fact.id, { tier: event.target.value as Fact["tier"] })
              }
              className={FIELD}
            >
              {TIERS.map((tier) => (
                <option key={tier} value={tier}>
                  {tierLabel(tier)}
                </option>
              ))}
            </select>
          </Field>
          {vocab ? (
            <Field label="Topics that can open this fact" id={`fact-topics-${fact.id}`}>
              <select
                id={`fact-topics-${fact.id}`}
                multiple
                value={fact.unlock?.topics ?? []}
                onChange={(event) => {
                  const topics = [...event.target.selectedOptions].map((option) => option.value);
                  replaceFact(caseDocument, onChange, fact.id, {
                    unlock: {
                      topics,
                      min_trust: fact.unlock?.min_trust ?? null,
                      requires_facts: fact.unlock?.requires_facts ?? [],
                    },
                  });
                }}
                className={`${FIELD} min-h-24`}
              >
                {vocab.topics.map((topic) => (
                  <option key={topic.id} value={topic.id}>
                    {topic.description}
                  </option>
                ))}
              </select>
            </Field>
          ) : (
            <p className="text-[12.5px] text-muted">Topics: {(fact.unlock?.topics ?? []).join(", ") || "none"}</p>
          )}
          <ReviewRow
            status={fact.status}
            source={fact.source}
            approveLabel={fact.id}
            onApprove={() => onApprove("facts", fact.id, "approved")}
            onReturn={() => onApprove("facts", fact.id, "draft")}
          />
          <button type="button" className="self-start text-sm font-medium underline" onClick={() => onRemoveFact(fact.id)}>
            Remove {fact.id}
          </button>
        </div>
      ))}
      <div>
        <button
          type="button"
          className="text-sm font-medium underline"
          onClick={() =>
            onChange({
              ...caseDocument,
              facts: [
                ...facts,
                {
                  id: nextFactId(facts),
                  category: "history",
                  cue: false,
                  safety: false,
                  text: "",
                  tier: "discoverable",
                  status: "draft",
                  source: { kind: "faculty", ref: null, by: null },
                },
              ],
            })
          }
        >
          Add fact
        </button>
      </div>
    </Section>
  );
}

// Vital signs the faculty typed. Auto-fill will not replace a key that is already here.
function VitalSection({ caseDocument, onChange, onApprove }: EditorProps) {
  const vitals = caseDocument.vitals ?? [];
  return (
    <Section title="Vital signs">
      {vitals.length === 0 ? <p className="text-muted">No vital signs yet</p> : null}
      {vitals.map((vital) => (
        <div key={vital.key} className="flex flex-col gap-2 border-t border-hair pt-3">
          <p className="font-medium">{vital.label}</p>
          <Field label="Value" id={`vital-value-${vital.key}`}>
            <input
              id={`vital-value-${vital.key}`}
              value={vital.value}
              onChange={(event) =>
                onChange({
                  ...caseDocument,
                  vitals: vitals.map((item) =>
                    item.key === vital.key
                      ? { ...item, value: event.target.value, source: keepFacultySource(item.source) }
                      : item,
                  ),
                })
              }
              className={FIELD}
            />
          </Field>
          <ReviewRow
            status={vital.status}
            source={vital.source}
            approveLabel={vital.key}
            onApprove={() => onApprove("vitals", vital.key, "approved")}
            onReturn={() => onApprove("vitals", vital.key, "draft")}
          />
        </div>
      ))}
      <AddVital
        onAdd={(key) => {
          if (vitals.some((vital) => vital.key === key)) return;
          const known = VITALS.find((vital) => vital.key === key);
          onChange({
            ...caseDocument,
            vitals: [
              ...vitals,
              {
                key,
                label: known?.label ?? key,
                value: "",
                unit: "",
                status: "draft",
                source: { kind: "faculty", ref: null, by: null },
              },
            ],
          });
        }}
      />
    </Section>
  );
}

// Labs, including values auto-fill proposed. Faculty numbers stay when auto-fill runs again.
function LabSection({ caseDocument, vocab, notes, onChange, onApprove, onAutofill }: EditorProps) {
  const labs = caseDocument.labs ?? [];
  const [panels, setPanels] = useState<string[]>(["bmp"]);
  const [includeVitals, setIncludeVitals] = useState(true);
  return (
    <Section title="Labs">
      {notes.length > 0 ? (
        <div>
          <p className="font-medium">Auto-fill notes</p>
          <ul className="mt-1 flex flex-col gap-1">
            {notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <fieldset className="flex flex-col gap-1">
        <legend className="font-medium">Panels to propose</legend>
        {(vocab?.lab_panels ?? ["bmp"]).map((panel) => (
          <label key={panel} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={panels.includes(panel)}
              onChange={() =>
                setPanels((current) =>
                  current.includes(panel) ? current.filter((item) => item !== panel) : [...current, panel],
                )
              }
            />
            {panel}
          </label>
        ))}
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={includeVitals} onChange={() => setIncludeVitals((current) => !current)} />
          Propose vital signs
        </label>
      </fieldset>
      <div>
        <button type="button" className="text-sm font-medium underline" onClick={() => onAutofill(panels, includeVitals)}>
          Propose values
        </button>
      </div>
      {labs.length === 0 ? <p className="text-muted">No labs yet</p> : null}
      {labs.map((lab) => {
        const flag = labFlag(lab);
        return (
          <div key={lab.id} className="flex flex-col gap-2 border-t border-hair pt-3">
            <p className="font-medium">
              {lab.name}
              {flag ? ` · ${flag}` : ""}
            </p>
            <p>
              {String(lab.value)} {lab.unit}
            </p>
            <Field label="Value" id={`lab-value-${lab.id}`}>
              <input
                id={`lab-value-${lab.id}`}
                value={String(lab.value)}
                onChange={(event) =>
                  onChange({
                    ...caseDocument,
                    labs: labs.map((item) =>
                      item.id === lab.id
                        ? { ...item, value: labValueFromInput(event.target.value), source: keepFacultySource(item.source) }
                        : item,
                    ),
                  })
                }
                className={FIELD}
              />
            </Field>
            <ReviewRow
              status={lab.status}
              source={lab.source}
              approveLabel={lab.id}
              onApprove={() => onApprove("labs", lab.id, "approved")}
              onReturn={() => onApprove("labs", lab.id, "draft")}
            />
          </div>
        );
      })}
    </Section>
  );
}

// Exam findings. The maneuver list is the catalog; the finding text is what faculty store.
function ExamSection({ caseDocument, vocab, vocabError, onChange, onApprove }: EditorProps) {
  const exam = caseDocument.exam ?? [];
  return (
    <Section title="Exam">
      {vocabError ? <p className="text-sm text-ink">{vocabError}</p> : null}
      {exam.map((finding) => (
        <div key={finding.maneuver} className="flex flex-col gap-2 border-t border-hair pt-3">
          <p className="font-medium">{maneuverLabel(vocab, finding.maneuver)}</p>
          <Field label="Finding" id={`exam-finding-${finding.maneuver}`}>
            <textarea
              id={`exam-finding-${finding.maneuver}`}
              value={finding.finding}
              onChange={(event) =>
                onChange({
                  ...caseDocument,
                  exam: exam.map((item) =>
                    item.maneuver === finding.maneuver
                      ? { ...item, finding: event.target.value, source: keepFacultySource(item.source) }
                      : item,
                  ),
                })
              }
              className={`${FIELD} min-h-16`}
            />
          </Field>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={finding.abnormal}
              onChange={(event) =>
                onChange({
                  ...caseDocument,
                  exam: exam.map((item) =>
                    item.maneuver === finding.maneuver ? { ...item, abnormal: event.target.checked } : item,
                  ),
                })
              }
            />
            Abnormal finding
          </label>
          <ReviewRow
            status={finding.status}
            source={finding.source}
            approveLabel={finding.maneuver}
            onApprove={() => onApprove("exam", finding.maneuver, "approved")}
            onReturn={() => onApprove("exam", finding.maneuver, "draft")}
          />
        </div>
      ))}
      {vocab ? (
        <Field label="Add a maneuver" id="exam-add">
          <select
            id="exam-add"
            value=""
            onChange={(event) => {
              const maneuver = event.target.value;
              if (!maneuver || exam.some((item) => item.maneuver === maneuver)) return;
              const chosen = vocab.maneuvers.find((item) => item.id === maneuver);
              onChange({
                ...caseDocument,
                exam: [
                  ...exam,
                  {
                    maneuver,
                    // The catalog sentence is the normal finding. Faculty can replace it.
                    finding: chosen?.normal ?? "",
                    abnormal: false,
                    status: "draft",
                    source: { kind: "default", ref: "exam catalog", by: null },
                  },
                ],
              });
            }}
            className={FIELD}
          >
            <option value="">Choose a maneuver</option>
            {vocab.maneuvers.map((maneuver) => (
              <option key={maneuver.id} value={maneuver.id}>
                {maneuver.label}
              </option>
            ))}
          </select>
        </Field>
      ) : null}
    </Section>
  );
}

// Diagnosis search uses the existing lookup. Choosing a row stores that code; nothing is invented.
function DiagnosisSection({ caseDocument, lookupResults, lookupMessage, onApprove, onLookup, onUseDiagnosis }: EditorProps) {
  const [query, setQuery] = useState("");
  const diagnoses = caseDocument.diagnoses ?? [];
  return (
    <Section title="Diagnoses">
      <Field label="Look up a diagnosis" id="diagnosis-query">
        <input
          id="diagnosis-query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className={FIELD}
        />
      </Field>
      <div>
        <button type="button" className="text-sm font-medium underline" onClick={() => onLookup(query)}>
          Look up diagnosis
        </button>
      </div>
      {lookupMessage ? <p className="text-sm text-ink">{lookupMessage}</p> : null}
      {lookupResults.map((match) => (
        <div key={match.code} className="flex flex-wrap items-center gap-2">
          <span>{match.code}</span>
          <button type="button" className="text-sm font-medium underline" onClick={() => onUseDiagnosis(match)}>
            Use {match.display}
          </button>
        </div>
      ))}
      {diagnoses.length === 0 ? <p className="text-muted">No diagnoses yet</p> : null}
      {diagnoses.map((diagnosis) => (
        <div key={diagnosis.name} className="flex flex-col gap-2 border-t border-hair pt-3">
          <p className="font-medium">{diagnosis.name}</p>
          <p className="text-[12.5px] text-muted">{(diagnosis.codes ?? []).map((code) => code.code).join(", ")}</p>
          <ReviewRow
            status={diagnosis.status}
            source={diagnosis.source}
            approveLabel={diagnosis.name}
            onApprove={() => onApprove("diagnoses", diagnosis.name, "approved")}
            onReturn={() => onApprove("diagnoses", diagnosis.name, "draft")}
          />
        </div>
      ))}
    </Section>
  );
}

// There is no medication lookup in this version. Faculty type the medicine; the screen does not invent one.
function MedicationSection({ caseDocument, onChange, onApprove }: EditorProps) {
  const medications = caseDocument.medications ?? [];
  return (
    <Section title="Medications">
      <p>Medication lookup is not available.</p>
      {medications.map((medication, index) => (
        <div key={`${medication.name}-${index}`} className="flex flex-col gap-2 border-t border-hair pt-3">
          <Field label="Medicine" id={`medication-name-${index}`}>
            <input
              id={`medication-name-${index}`}
              value={medication.name}
              onChange={(event) => updateMedication(caseDocument, onChange, index, { name: event.target.value })}
              className={FIELD}
            />
          </Field>
          <Field label="Dose" id={`medication-dose-${index}`}>
            <input
              id={`medication-dose-${index}`}
              value={medication.dose ?? ""}
              onChange={(event) => updateMedication(caseDocument, onChange, index, { dose: event.target.value || null })}
              className={FIELD}
            />
          </Field>
          <ReviewRow
            status={medication.status}
            source={medication.source}
            approveLabel={medication.name}
            onApprove={() => onApprove("medications", medication.name, "approved")}
            onReturn={() => onApprove("medications", medication.name, "draft")}
          />
        </div>
      ))}
      <div>
        <button
          type="button"
          className="text-sm font-medium underline"
          onClick={() =>
            onChange({
              ...caseDocument,
              medications: [
                ...medications,
                { name: "", dose: null, status: "draft", source: { kind: "faculty", ref: null, by: null } },
              ],
            })
          }
        >
          Add medication
        </button>
      </div>
    </Section>
  );
}

// There is no allergy lookup in this version. Faculty type the substance.
function AllergySection({ caseDocument, onChange, onApprove }: EditorProps) {
  const allergies = caseDocument.allergies ?? [];
  return (
    <Section title="Allergies">
      <p>Allergy lookup is not available.</p>
      {allergies.map((allergy, index) => (
        <div key={`${allergy.substance}-${index}`} className="flex flex-col gap-2 border-t border-hair pt-3">
          <Field label="Substance" id={`allergy-substance-${index}`}>
            <input
              id={`allergy-substance-${index}`}
              value={allergy.substance}
              onChange={(event) => updateAllergy(caseDocument, onChange, index, { substance: event.target.value })}
              className={FIELD}
            />
          </Field>
          <Field label="Reaction" id={`allergy-reaction-${index}`}>
            <input
              id={`allergy-reaction-${index}`}
              value={allergy.reaction ?? ""}
              onChange={(event) => updateAllergy(caseDocument, onChange, index, { reaction: event.target.value || null })}
              className={FIELD}
            />
          </Field>
          <ReviewRow
            status={allergy.status}
            source={allergy.source}
            approveLabel={allergy.substance}
            onApprove={() => onApprove("allergies", allergy.substance, "approved")}
            onReturn={() => onApprove("allergies", allergy.substance, "draft")}
          />
        </div>
      ))}
      <div>
        <button
          type="button"
          className="text-sm font-medium underline"
          onClick={() =>
            onChange({
              ...caseDocument,
              allergies: [
                ...allergies,
                { substance: "", reaction: null, status: "draft", source: { kind: "faculty", ref: null, by: null } },
              ],
            })
          }
        >
          Add allergy
        </button>
      </div>
    </Section>
  );
}

// Expected actions come from the closed action list. Already-saved ids stay visible if the list has not loaded.
function ActionChecks({
  objectiveId,
  selected,
  vocab,
  onChange,
}: {
  objectiveId: string;
  selected: string[];
  vocab: StudioVocab | null;
  onChange: (actions: string[]) => void;
}) {
  const actions = vocab?.actions ?? selected.map((id) => ({ id, description: id }));
  return (
    <fieldset className="flex flex-col gap-1">
      <legend className="font-medium">Expected actions</legend>
      {actions.map((action) => {
        const checked = selected.includes(action.id);
        return (
          <label key={`${objectiveId}-${action.id}`} className="flex items-start gap-2">
            <input
              type="checkbox"
              checked={checked}
              onChange={() => onChange(checked ? selected.filter((id) => id !== action.id) : [...selected, action.id])}
            />
            <span>{action.description}</span>
          </label>
        );
      })}
    </fieldset>
  );
}

// Review state is a word, and the source is written out. The buttons call the approval operation.
function ReviewRow({
  status,
  source,
  approveLabel,
  onApprove,
  onReturn,
}: {
  status: ItemStatus;
  source?: Source;
  approveLabel: string;
  onApprove: () => void;
  onReturn: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-[12.5px]">
      <span>{statusWord(status)}</span>
      {source ? <span className="text-muted">{sourceLabel(source)}</span> : null}
      {status === "draft" ? (
        <button type="button" className="font-medium underline" onClick={onApprove}>
          Approve {approveLabel}
        </button>
      ) : (
        <button type="button" className="font-medium underline" onClick={onReturn}>
          Return {approveLabel} to draft
        </button>
      )}
    </div>
  );
}

// A labeled control. The id is on the control, so the label text is not the only name.
function Field({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <label htmlFor={id} className="flex flex-col gap-1">
      <span className="font-medium">{label}</span>
      {children}
    </label>
  );
}

// One card for a group of fields, so the editor is not one long unlabeled form.
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <CardHead title={title} />
      <div className="flex flex-col gap-3 px-5 py-5 text-sm">{children}</div>
    </Card>
  );
}

// A new vital starts blank. The label is the field name, not a measurement.
function AddVital({ onAdd }: { onAdd: (key: string) => void }) {
  return (
    <label className="flex flex-col gap-1" htmlFor="vital-add">
      <span className="font-medium">Add a vital sign</span>
      <select id="vital-add" value="" onChange={(event) => event.target.value && onAdd(event.target.value)} className={FIELD}>
        <option value="">Choose a vital sign</option>
        {VITALS.map((vital) => (
          <option key={vital.key} value={vital.key}>
            {vital.label}
          </option>
        ))}
      </select>
    </label>
  );
}

// Replace one fact. clinical marks a change to the words or the number, which can change the source.
function replaceFact(
  caseDocument: CaseDocument,
  onChange: (next: CaseDocument) => void,
  factId: string,
  patch: Partial<Fact>,
  clinical = false,
) {
  onChange({
    ...caseDocument,
    facts: (caseDocument.facts ?? []).map((fact) => {
      if (fact.id !== factId) return fact;
      const next = { ...fact, ...patch };
      if (clinical) next.source = keepFacultySource(fact.source);
      return next;
    }),
  });
}

// A typed dose or schedule is faculty content, so the source stops citing a rule.
function updateMedication(
  caseDocument: CaseDocument,
  onChange: (next: CaseDocument) => void,
  index: number,
  patch: Partial<NonNullable<CaseDocument["medications"]>[number]>,
) {
  const medications = caseDocument.medications ?? [];
  onChange({
    ...caseDocument,
    medications: medications.map((medication, itemIndex) =>
      itemIndex === index ? { ...medication, ...patch, source: keepFacultySource(medication.source) } : medication,
    ),
  });
}

// A typed reaction is faculty content, so the source stops citing a rule.
function updateAllergy(
  caseDocument: CaseDocument,
  onChange: (next: CaseDocument) => void,
  index: number,
  patch: Partial<NonNullable<CaseDocument["allergies"]>[number]>,
) {
  const allergies = caseDocument.allergies ?? [];
  onChange({
    ...caseDocument,
    allergies: allergies.map((allergy, itemIndex) =>
      itemIndex === index ? { ...allergy, ...patch, source: keepFacultySource(allergy.source) } : allergy,
    ),
  });
}

// Keep a category the case already uses, even if it is not in the usual list.
function categoryOptions(current: string | undefined): string[] {
  if (!current || FACT_CATEGORIES.includes(current)) return FACT_CATEGORIES;
  return [current, ...FACT_CATEGORIES];
}

// Show the catalog name when the vocabulary loaded. The stored id stays the value.
function maneuverLabel(vocab: StudioVocab | null, maneuver: string): string {
  return vocab?.maneuvers.find((item) => item.id === maneuver)?.label ?? maneuver;
}

// The id is chosen when the objective is added. Editing the text does not change it.
function nextObjectiveId(objectives: { id: string }[]): string {
  const used = new Set(objectives.map((objective) => objective.id));
  let n = objectives.length + 1;
  while (used.has(`obj_${n}`)) n += 1;
  return `obj_${n}`;
}

// The review state in words. The stored value stays draft or approved.
function statusWord(status: ItemStatus): string {
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

// The disclosure tier in words. The stored value stays the engine's name for it.
function tierLabel(tier: Fact["tier"]): string {
  switch (tier) {
    case "initial":
      return "Initial";
    case "discoverable":
      return "Discoverable";
    case "reluctant":
      return "Reluctant";
    case "hidden":
      return "Hidden";
    default: {
      const unreachable: never = tier;
      return unreachable;
    }
  }
}

// The health-literacy level in words. The stored value stays low, medium, or high.
function literacyLabel(level: (typeof LITERACY)[number]): string {
  switch (level) {
    case "low":
      return "Low";
    case "medium":
      return "Medium";
    case "high":
      return "High";
    default: {
      const unreachable: never = level;
      return unreachable;
    }
  }
}

// The personality trait in words. An unknown key is shown as stored.
function traitLabel(trait: string): string {
  switch (trait) {
    case "openness":
      return "Openness";
    case "irritability":
      return "Irritability";
    case "verbosity":
      return "Verbosity";
    case "humor":
      return "Humor";
    default:
      return trait;
  }
}
