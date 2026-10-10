import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  ApiError,
  buildCase,
  lookupDiagnosis,
  suggestCase,
  typicalVitals,
  type ApiClient,
  type BuilderForm,
  type BuilderVital,
  type Icd10Match,
} from "../../api/client";
import type { Go } from "../../app/types";
import { GhostButton, PrimaryButton } from "../../components/ui";

type Source = BuilderVital["source"];
type VitalKey = "temp_f" | "hr" | "rr" | "bp" | "spo2" | "height" | "weight";
// A null source means the faculty member typed the value.
type VitalEntry = { value: string; source: Source | null };
type StepId = "describe" | "patient" | "visit" | "history" | "voice" | "vitals" | "finish";
type TextKey = Exclude<
  { [K in keyof BuilderForm]: BuilderForm[K] extends string ? K : never }[keyof BuilderForm],
  "sex" | "health_literacy" | "difficulty" | "documentation_template" | "description" | undefined
>;

export type CreatePhase = { kind: "editing" } | { kind: "saving" } | { kind: "error"; message: string };

type Work = { kind: "idle" } | { kind: "working" } | { kind: "error"; message: string };

const STEPS: { id: StepId; title: string; why: string }[] = [
  { id: "describe", title: "Description", why: "A few sentences is enough. Rounds suggests the rest of the form, and you check every suggestion." },
  { id: "patient", title: "Who they are", why: "The basics a learner would see on the chart before walking in." },
  { id: "visit", title: "The visit", why: "What the learner is told at the door, and what they are there to do." },
  { id: "history", title: "History", why: "What the patient can tell the learner. The patient never says anything that is not written here." },
  { id: "voice", title: "How they talk", why: "Personality shapes the wording, never the facts." },
  { id: "vitals", title: "Vitals", why: "Taken by the nurse before the visit. Leave a value blank to skip it." },
  { id: "finish", title: "Goals and save", why: "What a learner should come away with. The debrief checks for these." },
];

const VITALS: { key: VitalKey; label: string; unit: string; example: string }[] = [
  { key: "temp_f", label: "Temperature", unit: "°F", example: "98.4" },
  { key: "hr", label: "Heart rate", unit: "bpm", example: "76" },
  { key: "rr", label: "Breathing rate", unit: "breaths/min", example: "16" },
  { key: "bp", label: "Blood pressure", unit: "mmHg", example: "124/78" },
  { key: "spo2", label: "Oxygen saturation", unit: "%", example: "98" },
  { key: "height", label: "Height", unit: "in", example: "67" },
  { key: "weight", label: "Weight", unit: "lb", example: "172" },
];

const EMPTY_FORM: BuilderForm = {
  description: "",
  notes: "",
  name: "",
  age: null,
  sex: "other",
  pronouns: "",
  occupation: "",
  speaker: "",
  setting: "",
  reason_for_visit: "",
  student_role: "",
  goal: "",
  chief_complaint: "",
  social: "",
  goals_fears: "",
  hidden: "",
  personal_cue: "",
  objectives: "",
  conditions: [],
  medications: [],
  allergies: [],
  no_known_allergies: false,
  personality: "",
  communication_style: "",
  health_literacy: "medium",
  mood: "",
  difficulty: "typical",
  documentation_template: "SOAP",
  show_doorway_vitals: true,
  vitals: [],
};

const TEXT_KEYS: TextKey[] = [
  "name", "pronouns", "occupation", "speaker", "setting", "reason_for_visit", "student_role", "goal",
  "chief_complaint", "social", "goals_fears", "hidden", "personal_cue", "objectives", "personality", "communication_style", "mood",
];

// Guided case builder. One step at a time, every field editable, suggestions marked until changed.
// The description box and the "Create draft" path are shared with Studio's original flow.
export function CaseBuilder({
  go,
  client,
  description,
  onDescriptionChange,
  createPhase,
  onCreateDraft,
}: {
  go: Go;
  client: ApiClient;
  description: string;
  onDescriptionChange: (value: string) => void;
  createPhase: CreatePhase;
  onCreateDraft: () => void;
}) {
  const [step, setStep] = useState<StepId>("describe");
  const [form, setForm] = useState<BuilderForm>(EMPTY_FORM);
  const [vitals, setVitals] = useState<Record<VitalKey, VitalEntry>>(() =>
    Object.fromEntries(VITALS.map((v) => [v.key, { value: "", source: null }])) as Record<VitalKey, VitalEntry>,
  );
  const [suggested, setSuggested] = useState<Set<string>>(new Set());
  const [suggestWork, setSuggestWork] = useState<Work>({ kind: "idle" });
  const [suggestNote, setSuggestNote] = useState<string | null>(null);
  const [vitalsWork, setVitalsWork] = useState<Work>({ kind: "idle" });
  const [vitalsNotes, setVitalsNotes] = useState<string[]>([]);
  const [saveWork, setSaveWork] = useState<Work>({ kind: "idle" });

  const bodyRef = useRef<HTMLDivElement | null>(null);

  // A new step starts at its first field, not wherever the last step was scrolled to.
  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = 0;
  }, [step]);

  const described = description.trim().length >= 10;
  const index = STEPS.findIndex((s) => s.id === step);

  function set<K extends keyof BuilderForm>(key: K, value: BuilderForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setSuggested((current) => {
      if (!current.has(key)) return current;
      const next = new Set(current);
      next.delete(key);
      return next;
    });
  }

  function setVital(key: VitalKey, value: string) {
    setVitals((current) => ({ ...current, [key]: { value, source: null } }));
  }

  // Fill only what is still empty, so nothing the faculty member typed is replaced.
  async function suggest() {
    if (!described) return;
    setSuggestWork({ kind: "working" });
    try {
      const result = await suggestCase(client, description, form.notes ?? "");
      const incoming = result.form;
      const next = { ...form };
      const marked = new Set(suggested);
      for (const key of TEXT_KEYS) {
        const value = incoming[key];
        if (typeof value === "string" && value.trim() && !(form[key] ?? "").trim()) {
          next[key] = value;
          marked.add(key);
        }
      }
      if (!form.age && incoming.age) {
        next.age = incoming.age;
        marked.add("age");
      }
      if (form.sex === "other" && incoming.sex !== "other") {
        next.sex = incoming.sex;
        marked.add("sex");
      }
      for (const key of ["conditions", "medications", "allergies"] as const) {
        if ((form[key] ?? []).length === 0 && (incoming[key] ?? []).length > 0) {
          (next[key] as unknown) = incoming[key];
          marked.add(key);
        }
      }
      if (incoming.no_known_allergies && (next.allergies ?? []).length === 0) {
        next.no_known_allergies = true;
        marked.add("no_known_allergies");
      }
      if (result.used_model) {
        next.health_literacy = incoming.health_literacy;
        next.documentation_template = incoming.documentation_template;
      }
      setForm(next);
      setSuggested(marked);
      setSuggestNote(result.note ?? (marked.size > 0 ? `${marked.size} fields filled from your description. Each is marked Suggested until you change it.` : "Nothing more could be read from the description. Fill in the fields below."));
      setSuggestWork({ kind: "idle" });
      setStep("patient");
    } catch (error: unknown) {
      setSuggestWork({ kind: "error", message: messageOf(error, "Suggestions could not be loaded. You can fill in the fields yourself.") });
    }
  }

  async function suggestVitals() {
    if (!form.age) {
      setVitalsWork({ kind: "error", message: "Add the patient's age first. Typical values depend on it." });
      return;
    }
    setVitalsWork({ kind: "working" });
    try {
      const result = await typicalVitals(client, {
        description,
        age: form.age,
        sex: form.sex,
        conditions: form.conditions ?? [],
      });
      setVitals((current) => {
        const next = { ...current };
        for (const vital of result.vitals) {
          const key = (vital.key === "temp_c" ? "temp_f" : vital.key) as VitalKey;
          if (!(key in next) || next[key].value.trim()) continue;
          const value = vital.key === "temp_c" ? toFahrenheit(vital.value) : vital.value;
          next[key] = { value, source: vital.source };
        }
        return next;
      });
      setVitalsNotes(result.notes);
      setVitalsWork({ kind: "idle" });
    } catch (error: unknown) {
      setVitalsWork({ kind: "error", message: messageOf(error, "Typical values could not be loaded.") });
    }
  }

  async function save() {
    if (!described) {
      setStep("describe");
      return;
    }
    setSaveWork({ kind: "working" });
    try {
      const result = await buildCase(client, { ...form, description, vitals: vitalList(vitals) });
      go("f-studio", { studioTab: "patient", caseId: result.case.case_id, version: result.case.version });
    } catch (error: unknown) {
      setSaveWork({ kind: "error", message: messageOf(error, "The case could not be saved.") });
    }
  }

  const missing = missingForPublish(form, description);
  const done: Record<StepId, boolean> = {
    describe: described,
    patient: Boolean(form.name?.trim() && form.age),
    visit: Boolean(form.setting?.trim() && form.reason_for_visit?.trim() && form.student_role?.trim() && form.goal?.trim()),
    history: Boolean(form.chief_complaint?.trim() && ((form.allergies ?? []).length > 0 || form.no_known_allergies)),
    voice: Boolean(form.mood?.trim() || form.personality?.trim() || form.communication_style?.trim()),
    vitals: Object.values(vitals).some((v) => v.value.trim()),
    finish: Boolean(form.objectives?.trim()),
  };

  return (
    <div className="grid min-h-0 flex-1 items-start gap-5 lg:grid-cols-[250px_minmax(0,1fr)] lg:items-stretch">
      <nav aria-label="Builder steps" className="self-start rounded-[18px] border border-white/80 bg-card/90 p-3 shadow-[0_18px_40px_-28px_rgba(25,31,92,.5)] backdrop-blur-md">
        <div className="px-3 pt-2 pb-3 font-sans text-[13px] text-ink-soft">
          {Object.values(done).filter(Boolean).length} of {STEPS.length} steps filled
        </div>
        <ol className="flex flex-col gap-1">
          {STEPS.map((s, i) => {
            const active = s.id === step;
            return (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => setStep(s.id)}
                  aria-current={active ? "step" : undefined}
                  className={`flex w-full items-center gap-3 rounded-[12px] px-3 py-2.5 text-left transition-colors ${active ? "bg-indigo-soft" : "hover:bg-indigo-soft/50"}`}
                >
                  <span
                    className={`flex size-7 shrink-0 items-center justify-center rounded-full font-sans text-[13px] font-semibold ${
                      done[s.id] ? "bg-panel text-white" : active ? "border-2 border-panel text-ink" : "border border-line-2 text-ink-soft"
                    }`}
                  >
                    {done[s.id] ? <CheckGlyph /> : i + 1}
                  </span>
                  <span className={`font-serif text-[18px] leading-tight ${active ? "text-ink" : "text-ink-soft"}`}>{s.title}</span>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      <section className="flex min-h-0 flex-col rounded-[18px] border border-white/80 bg-card/95 shadow-[0_24px_60px_-36px_rgba(25,31,92,.55)] backdrop-blur-md">
        <div ref={bodyRef} className="min-h-0 flex-1 overflow-y-auto px-[clamp(20px,2.6vw,40px)] pt-5 pb-5">
        <div className="font-sans text-[13px] font-semibold tracking-[0.5px] text-indigo uppercase">
          Step {index + 1} of {STEPS.length}
        </div>
        <h2 className="m-0 mt-1 font-serif text-[clamp(26px,2.2vw,32px)] leading-tight font-normal tracking-[-0.6px]">{STEPS[index].title}</h2>
        <p className="mt-1.5 max-w-[680px] font-sans text-[15.5px] leading-snug text-ink-soft">{STEPS[index].why}</p>
        {suggestNote && step !== "describe" ? (
          <p className="mt-4 rounded-[12px] bg-indigo-soft/70 px-4 py-2.5 font-sans text-[14px] text-ink">{suggestNote}</p>
        ) : null}

        <div className="mt-5">
          {step === "describe" ? (
            <div className="flex flex-col gap-5">
              <Field id="patient-description" label="Describe the patient">
                <textarea
                  id="patient-description"
                  value={description}
                  onChange={(event) => onDescriptionChange(event.target.value)}
                  disabled={createPhase.kind === "saving" || suggestWork.kind === "working"}
                  placeholder="A 58-year-old truck driver with type 2 diabetes who keeps missing doses of metformin. He is embarrassed about it and only admits it once the learner earns his trust."
                  className={`${INPUT} min-h-[104px] text-[17px]`}
                />
              </Field>
              <Field id="builder-notes" label="Notes for this case" hint="Optional: what learners should catch, how hard it should be.">
                <textarea
                  id="builder-notes"
                  value={form.notes ?? ""}
                  onChange={(event) => set("notes", event.target.value)}
                  placeholder="Learners should ask about side effects before assuming he doesn't care."
                  className={`${INPUT} min-h-[56px]`}
                />
              </Field>
              <div className="flex flex-wrap items-center gap-3">
                <PrimaryButton size="lg" onClick={() => void suggest()} disabled={!described || suggestWork.kind === "working"}>
                  {suggestWork.kind === "working" ? "Reading your description" : "Suggest the details"}
                </PrimaryButton>
                <GhostButton onClick={() => setStep("patient")}>Fill it in myself</GhostButton>
                <GhostButton onClick={onCreateDraft}>
                  {createPhase.kind === "saving" ? "Saving draft" : createPhase.kind === "error" ? "Try again" : "Create draft"}
                </GhostButton>
              </div>
              <p className="-mt-2 font-sans text-[13px] leading-snug text-muted">
                {described
                  ? "Create draft skips the steps: Rounds drafts the whole case and opens it in Studio for you to edit."
                  : "Write at least a sentence to get suggestions."}
              </p>
              {suggestWork.kind === "error" ? <Alert>{suggestWork.message}</Alert> : null}
              {createPhase.kind === "error" ? <Alert>{createPhase.message}</Alert> : null}
            </div>
          ) : null}

          {step === "patient" ? (
            <Grid>
              <TextField k="name" label="Name" example="Ray Ortiz" form={form} suggested={suggested} onSet={set} />
              <Field id="builder-age" label="Age" mark={suggested.has("age")}>
                <input
                  id="builder-age"
                  inputMode="numeric"
                  value={form.age ?? ""}
                  onChange={(event) => {
                    const digits = event.target.value.replace(/\D/g, "").slice(0, 3);
                    set("age", digits ? Number(digits) : null);
                  }}
                  placeholder="58"
                  className={INPUT}
                />
              </Field>
              <Field id="builder-sex" label="Sex" mark={suggested.has("sex")}>
                <Segmented
                  value={form.sex}
                  options={[
                    ["female", "Female"],
                    ["male", "Male"],
                    ["other", "Other or not stated"],
                  ]}
                  onChange={(value) => set("sex", value)}
                />
              </Field>
              <TextField k="pronouns" label="Pronouns" example="he/him" form={form} suggested={suggested} onSet={set} />
              <TextField k="occupation" label="Work" example="Delivery truck driver, night shifts" form={form} suggested={suggested} onSet={set} />
              <TextField
                k="speaker"
                label="Who does the talking"
                hint="Only if it is not the patient, for example a parent."
                example="Her mother, Dana"
                form={form}
                suggested={suggested}
                onSet={set}
              />
            </Grid>
          ) : null}

          {step === "visit" ? (
            <Grid>
              <TextField k="setting" label="Setting" example="Primary care clinic, follow-up appointment" form={form} suggested={suggested} onSet={set} />
              <TextField k="reason_for_visit" label="Reason for visit" hint="As it would appear on the schedule." example="Diabetes follow-up" form={form} suggested={suggested} onSet={set} />
              <TextField k="student_role" label="Learner's role" hint="Profession and training level." example="Third-year medical student" form={form} suggested={suggested} onSet={set} />
              <TextField k="goal" label="Goal for the learner" example="Find out why doses are missed and agree on one change" form={form} suggested={suggested} onSet={set} long />
              <Field id="builder-template" label="Note the learner writes afterwards">
                <Segmented
                  value={form.documentation_template}
                  options={[
                    ["SOAP", "SOAP"],
                    ["SBAR", "SBAR"],
                    ["ADIME", "ADIME"],
                    ["PES", "PES"],
                  ]}
                  onChange={(value) => set("documentation_template", value)}
                />
              </Field>
              <Field id="builder-doorway" label="Doorway vitals">
                <label className="flex items-center gap-3 font-sans text-[15px]">
                  <input
                    id="builder-doorway"
                    type="checkbox"
                    checked={form.show_doorway_vitals}
                    onChange={(event) => set("show_doorway_vitals", event.target.checked)}
                    className="size-5 accent-[#252d78]"
                  />
                  Show vitals on the briefing card before the visit
                </label>
              </Field>
            </Grid>
          ) : null}

          {step === "history" ? (
            <div className="flex flex-col gap-6">
              <TextField
                k="chief_complaint"
                label="Why they are here, in their own words"
                example="My sugar's been running high and the doctor wanted me to come in."
                form={form}
                suggested={suggested}
                onSet={set}
                long
              />
              <Conditions client={client} form={form} mark={suggested.has("conditions")} onChange={(value) => set("conditions", value)} />
              <Medications form={form} mark={suggested.has("medications")} onChange={(value) => set("medications", value)} />
              <Allergies form={form} mark={suggested.has("allergies") || suggested.has("no_known_allergies")} onSet={set} />
              <Grid>
                <TextField k="social" label="Daily life" hint="Who they live with, work, money, support." example="Lives alone. Drives nights. Money is tight since his hours were cut." form={form} suggested={suggested} onSet={set} long />
                <TextField k="goals_fears" label="What they want and what worries them" example="Wants to keep driving. Worried about ending up on insulin like his father." form={form} suggested={suggested} onSet={set} long />
                <TextField k="hidden" label="What they hold back until they trust the learner" example="Skips metformin on work nights because it upsets his stomach." form={form} suggested={suggested} onSet={set} long />
                <TextField k="personal_cue" label="A personal detail they might mention" hint="Following up on it builds trust." example="His granddaughter's softball games on Saturdays." form={form} suggested={suggested} onSet={set} long />
              </Grid>
            </div>
          ) : null}

          {step === "voice" ? (
            <Grid>
              <Field id="builder-literacy" label="Health literacy" hint="Sets how plain the patient's words are.">
                <Segmented
                  value={form.health_literacy}
                  options={[
                    ["low", "Low"],
                    ["medium", "Medium"],
                    ["high", "High"],
                  ]}
                  onChange={(value) => set("health_literacy", value)}
                />
              </Field>
              <Field id="builder-difficulty" label="How hard to interview" hint={DIFFICULTY_HINT[form.difficulty]}>
                <Segmented
                  value={form.difficulty}
                  options={[
                    ["straightforward", "Straightforward"],
                    ["typical", "Typical"],
                    ["difficult", "Difficult"],
                  ]}
                  onChange={(value) => set("difficulty", value)}
                />
              </Field>
              <TextField k="mood" label="Mood today" example="Tired and a bit defensive" form={form} suggested={suggested} onSet={set} />
              <TextField k="communication_style" label="How they talk" example="Short answers, jokes when uncomfortable" form={form} suggested={suggested} onSet={set} />
              <TextField k="personality" label="Personality" example="Proud, private, warms up when asked about family" form={form} suggested={suggested} onSet={set} long />
            </Grid>
          ) : null}

          {step === "vitals" ? (
            <div className="flex flex-col gap-5">
              <div className="flex flex-wrap items-center gap-3">
                <PrimaryButton onClick={() => void suggestVitals()} disabled={vitalsWork.kind === "working"}>
                  {vitalsWork.kind === "working" ? "Finding typical values" : "Suggest typical values"}
                </PrimaryButton>
                <span className="max-w-[520px] font-sans text-[13.5px] leading-snug text-ink-soft">
                  From published resting ranges for this age, shifted by any condition with a guideline rule. Blank fields only. Each value names its source.
                </span>
              </div>
              {vitalsWork.kind === "error" ? <Alert>{vitalsWork.message}</Alert> : null}
              {vitalsNotes.map((note) => (
                <Alert key={note}>{note}</Alert>
              ))}
              <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(180px,1fr))]">
                {VITALS.map((v) => {
                  const entry = vitals[v.key];
                  return (
                    <Field key={v.key} id={`vital-${v.key}`} label={v.label} mark={entry.source !== null}>
                      <div className="flex items-center gap-2">
                        <input
                          id={`vital-${v.key}`}
                          value={entry.value}
                          onChange={(event) => setVital(v.key, event.target.value)}
                          placeholder={v.example}
                          className={`${INPUT} tabular-nums`}
                        />
                        <span className="shrink-0 font-sans text-[13px] text-ink-soft">{v.unit}</span>
                      </div>
                      {entry.source ? <div className="mt-1 font-sans text-[12px] leading-snug text-muted">Source: {entry.source.ref ?? entry.source.kind}</div> : null}
                    </Field>
                  );
                })}
              </div>
              <p className="font-sans text-[13px] text-muted">Labs, imaging, and exam findings are added in Studio after you save.</p>
            </div>
          ) : null}

          {step === "finish" ? (
            <div className="flex flex-col gap-6">
              <TextField
                k="objectives"
                label="Learning goals"
                hint="One per line."
                example={"Ask about adherence without judgment\nAgree on one realistic change"}
                form={form}
                suggested={suggested}
                onSet={set}
                long
              />
              <div className="rounded-[14px] border border-line px-5 py-4">
                <div className="font-serif text-[20px]">{missing.length === 0 ? "Ready for Studio" : "Still needed before it can be published"}</div>
                {missing.length === 0 ? (
                  <p className="mt-1 font-sans text-[14px] text-ink-soft">Save it, then approve each item in Studio and publish.</p>
                ) : (
                  <ul className="mt-2 flex flex-col gap-1.5">
                    {missing.map((item) => (
                      <li key={item.label} className="flex items-center gap-2 font-sans text-[14.5px]">
                        <span className="size-1.5 rounded-full bg-warn" />
                        <button type="button" onClick={() => setStep(item.step)} className="text-left underline decoration-line-2 underline-offset-4 hover:decoration-ink">
                          {item.label}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                {missing.length > 0 ? (
                  <p className="mt-2 font-sans text-[13px] text-muted">You can save now and finish these in Studio.</p>
                ) : null}
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <PrimaryButton size="lg" onClick={() => void save()} disabled={saveWork.kind === "working"}>
                  {saveWork.kind === "working" ? "Saving" : "Save and open in Studio"}
                </PrimaryButton>
                {saveWork.kind === "error" ? <Alert>{saveWork.message}</Alert> : null}
              </div>
            </div>
          ) : null}
        </div>

        </div>
        {step !== "describe" ? (
          <div className="flex shrink-0 items-center justify-between border-t border-hair px-[clamp(20px,2.6vw,40px)] py-4">
            <GhostButton onClick={() => setStep(STEPS[index - 1].id)}>Back</GhostButton>
            {index < STEPS.length - 1 ? (
              <PrimaryButton onClick={() => setStep(STEPS[index + 1].id)}>Next: {STEPS[index + 1].title}</PrimaryButton>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}

const INPUT =
  "w-full rounded-[12px] border border-line-2 bg-white px-3.5 py-2.5 font-sans text-[16px] text-ink outline-none transition-colors placeholder:text-[#a9adbf] focus:border-indigo focus:ring-2 focus:ring-indigo-soft";

const DIFFICULTY_HINT: Record<BuilderForm["difficulty"], string> = {
  straightforward: "Shares most things when asked. Good for a first attempt.",
  typical: "Holds a few things back until the learner earns trust.",
  difficult: "Guarded and tangential. Learners have to work for the history.",
};

function Grid({ children }: { children: ReactNode }) {
  return <div className="grid gap-5 [grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr))]">{children}</div>;
}

function Field({ id, label, hint, mark = false, children }: { id: string; label: string; hint?: string; mark?: boolean; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={id} className="font-serif text-[19px] leading-tight text-ink">
          {label}
        </label>
        {mark ? <SuggestedTag /> : null}
      </div>
      {hint ? <p className="-mt-0.5 font-sans text-[13px] leading-snug text-ink-soft">{hint}</p> : null}
      {children}
    </div>
  );
}

function SuggestedTag() {
  return (
    <span title="Filled for you. Check it, then change anything that is wrong." className="rounded-full bg-indigo-soft px-2 py-0.5 font-sans text-[11.5px] font-semibold text-indigo">
      Suggested
    </span>
  );
}

function TextField({
  k,
  label,
  hint,
  example,
  long = false,
  form,
  suggested,
  onSet,
}: {
  k: TextKey;
  label: string;
  hint?: string;
  example: string;
  long?: boolean;
  form: BuilderForm;
  suggested: Set<string>;
  onSet: (key: TextKey, value: string) => void;
}) {
  const id = `builder-${k}`;
  const value = (form[k] as string | undefined) ?? "";
  return (
    <Field id={id} label={label} hint={hint} mark={suggested.has(k)}>
      {long ? (
        <textarea id={id} value={value} onChange={(event) => onSet(k, event.target.value)} placeholder={example} className={`${INPUT} min-h-[88px]`} />
      ) : (
        <input id={id} value={value} onChange={(event) => onSet(k, event.target.value)} placeholder={example} className={INPUT} />
      )}
    </Field>
  );
}

function Segmented<T extends string>({ value, options, onChange }: { value: T; options: [T, string][]; onChange: (value: T) => void }) {
  return (
    <div role="radiogroup" className="inline-flex flex-wrap gap-1 rounded-[12px] bg-segment p-1">
      {options.map(([option, label]) => (
        <button
          key={option}
          type="button"
          role="radio"
          aria-checked={value === option}
          onClick={() => onChange(option)}
          className={`rounded-[9px] px-3.5 py-2 font-sans text-[14.5px] transition-colors ${value === option ? "bg-card text-ink shadow-[0_2px_8px_-4px_rgba(25,31,92,.4)]" : "text-ink-soft hover:text-ink"}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function Conditions({
  client,
  form,
  mark,
  onChange,
}: {
  client: ApiClient;
  form: BuilderForm;
  mark: boolean;
  onChange: (value: NonNullable<BuilderForm["conditions"]>) => void;
}) {
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<Icd10Match[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const conditions = form.conditions ?? [];

  async function search() {
    if (query.trim().length < 2) {
      setMessage("Type at least two letters.");
      return;
    }
    try {
      const found = await lookupDiagnosis(client, query.trim());
      setMatches(found);
      setMessage(found.length === 0 ? "No coded match. You can add it as typed." : null);
    } catch (error: unknown) {
      setMatches([]);
      setMessage(messageOf(error, "Lookup failed. You can add it as typed."));
    }
  }

  function add(name: string, code: string | null) {
    if (!name.trim() || conditions.some((c) => c.name.toLowerCase() === name.trim().toLowerCase())) return;
    onChange([...conditions, { name: name.trim(), code }]);
    setQuery("");
    setMatches([]);
    setMessage(null);
  }

  return (
    <Field id="builder-conditions" label="Conditions" hint="Search for a coded diagnosis, or add it in your own words." mark={mark}>
      {conditions.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {conditions.map((c) => (
            <span key={c.name} className="inline-flex items-center gap-2 rounded-full border border-indigo-line bg-indigo-soft py-1 pr-1.5 pl-3.5 font-sans text-[14px]">
              {c.name}
              {c.code ? <span className="text-[12px] text-ink-soft">{c.code}</span> : null}
              <RemoveButton label={`Remove ${c.name}`} onClick={() => onChange(conditions.filter((other) => other !== c))} />
            </span>
          ))}
        </div>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <input
          id="builder-conditions"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              void search();
            }
          }}
          placeholder="Type 2 diabetes"
          className={`${INPUT} max-w-[420px] flex-1`}
        />
        <GhostButton onClick={() => void search()}>Search codes</GhostButton>
        <GhostButton onClick={() => add(query, null)}>Add as typed</GhostButton>
      </div>
      {message ? <p className="font-sans text-[13px] text-ink-soft">{message}</p> : null}
      {matches.length > 0 ? (
        <ul className="max-w-[640px] overflow-hidden rounded-[12px] border border-line">
          {matches.slice(0, 6).map((match) => (
            <li key={match.code}>
              <button type="button" onClick={() => add(match.display, match.code)} className="flex w-full items-center justify-between gap-3 border-t border-hair px-4 py-2.5 text-left font-sans text-[14.5px] first:border-t-0 hover:bg-raised">
                {match.display}
                <span className="text-[12.5px] text-ink-soft">{match.code}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </Field>
  );
}

function Medications({
  form,
  mark,
  onChange,
}: {
  form: BuilderForm;
  mark: boolean;
  onChange: (value: NonNullable<BuilderForm["medications"]>) => void;
}) {
  const rows = form.medications ?? [];
  const update = (i: number, key: "name" | "dose" | "frequency" | "purpose", value: string) =>
    onChange(rows.map((row, j) => (j === i ? { ...row, [key]: value } : row)));
  return (
    <Field id="builder-med-0" label="Medications" hint="Include how they actually take them in the history below if it differs." mark={mark}>
      {rows.map((row, i) => (
        <div key={i} className="grid items-center gap-2 [grid-template-columns:minmax(140px,1.4fr)_minmax(90px,.8fr)_minmax(110px,1fr)_minmax(110px,1fr)_auto]">
          <input id={`builder-med-${i}`} aria-label="Medication" value={row.name} onChange={(e) => update(i, "name", e.target.value)} placeholder="Metformin" className={INPUT} />
          <input aria-label="Dose" value={row.dose ?? ""} onChange={(e) => update(i, "dose", e.target.value)} placeholder="1000 mg" className={INPUT} />
          <input aria-label="How often" value={row.frequency ?? ""} onChange={(e) => update(i, "frequency", e.target.value)} placeholder="Twice daily" className={INPUT} />
          <input aria-label="What for" value={row.purpose ?? ""} onChange={(e) => update(i, "purpose", e.target.value)} placeholder="Diabetes" className={INPUT} />
          <RemoveButton label={`Remove ${row.name || "medication"}`} onClick={() => onChange(rows.filter((_, j) => j !== i))} />
        </div>
      ))}
      <div>
        <GhostButton size="sm" onClick={() => onChange([...rows, { name: "", dose: null, frequency: null, purpose: null }])}>
          Add medication
        </GhostButton>
      </div>
    </Field>
  );
}

function Allergies({
  form,
  mark,
  onSet,
}: {
  form: BuilderForm;
  mark: boolean;
  onSet: <K extends keyof BuilderForm>(key: K, value: BuilderForm[K]) => void;
}) {
  const rows = form.allergies ?? [];
  const none = Boolean(form.no_known_allergies);
  return (
    <Field id="builder-nka" label="Allergies" mark={mark}>
      <label className="flex items-center gap-3 font-sans text-[15px]">
        <input
          id="builder-nka"
          type="checkbox"
          checked={none}
          onChange={(event) => {
            onSet("no_known_allergies", event.target.checked);
            if (event.target.checked) onSet("allergies", []);
          }}
          className="size-5 accent-[#252d78]"
        />
        No known allergies
      </label>
      {none
        ? null
        : rows.map((row, i) => (
            <div key={i} className="grid max-w-[640px] items-center gap-2 [grid-template-columns:minmax(140px,1fr)_minmax(140px,1fr)_auto]">
              <input aria-label="Allergy" value={row.substance} onChange={(e) => onSet("allergies", rows.map((r, j) => (j === i ? { ...r, substance: e.target.value } : r)))} placeholder="Penicillin" className={INPUT} />
              <input aria-label="Reaction" value={row.reaction ?? ""} onChange={(e) => onSet("allergies", rows.map((r, j) => (j === i ? { ...r, reaction: e.target.value } : r)))} placeholder="Hives" className={INPUT} />
              <RemoveButton label={`Remove ${row.substance || "allergy"}`} onClick={() => onSet("allergies", rows.filter((_, j) => j !== i))} />
            </div>
          ))}
      {none ? null : (
        <div>
          <GhostButton size="sm" onClick={() => onSet("allergies", [...rows, { substance: "", reaction: null }])}>
            Add allergy
          </GhostButton>
        </div>
      )}
    </Field>
  );
}

function RemoveButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button type="button" aria-label={label} title={label} onClick={onClick} className="flex size-7 items-center justify-center rounded-full text-ink-soft hover:bg-white hover:text-ink">
      <svg width="12" height="12" viewBox="0 0 12 12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
        <path d="M2 2l8 8M10 2l-8 8" />
      </svg>
    </button>
  );
}

function Alert({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="font-sans text-[14px] text-ink">
      {children}
    </p>
  );
}

function CheckGlyph() {
  return (
    <svg width="13" height="13" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M2.5 6.3l2.3 2.3 4.7-5" />
    </svg>
  );
}

// The same required items the publish check asks for, pointed at the step that fills each one.
function missingForPublish(form: BuilderForm, description: string): { label: string; step: StepId }[] {
  const out: { label: string; step: StepId }[] = [];
  if (description.trim().length < 10) out.push({ label: "A description of the patient", step: "describe" });
  if (!form.name?.trim()) out.push({ label: "Name", step: "patient" });
  if (!form.age) out.push({ label: "Age", step: "patient" });
  if (!form.reason_for_visit?.trim()) out.push({ label: "Reason for visit", step: "visit" });
  if (!form.student_role?.trim()) out.push({ label: "Learner's role", step: "visit" });
  if (!form.goal?.trim()) out.push({ label: "Goal for the learner", step: "visit" });
  if (!form.chief_complaint?.trim()) out.push({ label: "Why they are here, in their own words", step: "history" });
  if (!form.objectives?.trim()) out.push({ label: "Learning goals", step: "finish" });
  return out;
}

// Vitals in the case's stored units. Temperature is entered in Fahrenheit and stored in Celsius.
function vitalList(vitals: Record<VitalKey, VitalEntry>): BuilderVital[] {
  const faculty: Source = { kind: "faculty", ref: "case builder", by: null };
  const out: BuilderVital[] = [];
  for (const v of VITALS) {
    const entry = vitals[v.key];
    const value = entry.value.trim();
    if (!value) continue;
    if (v.key === "temp_f") {
      const f = Number(value);
      out.push({ key: "temp_c", label: "Temperature", value: Number.isFinite(f) ? (((f - 32) * 5) / 9).toFixed(1) : value, unit: "°C", source: entry.source ?? faculty });
      continue;
    }
    out.push({ key: v.key, label: v.label, value, unit: v.unit, source: entry.source ?? faculty });
  }
  return out;
}

function toFahrenheit(celsius: string): string {
  const c = Number(celsius);
  return Number.isFinite(c) ? ((c * 9) / 5 + 32).toFixed(1) : celsius;
}

function messageOf(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.message.trim()) return error.message;
  return fallback;
}
