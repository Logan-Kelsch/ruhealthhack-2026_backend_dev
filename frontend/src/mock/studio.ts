import type { Portrait } from "../components/Avatar";

// Prototype fixtures for the Patient Studio. Swapped for the studio API later.

export const STUDIO_CASES: Record<"patient" | "tree", { name: string; meta: string; who: Portrait }> = {
  patient: { name: "Walter Greene, 72", meta: "Dietetics student · 2 visits", who: "walter" },
  tree: { name: "Depression follow-up", meta: "Psychiatry clerkship · 2 visits", who: "generic" },
};

export type StudioItem = {
  name: string;
  code: string;
  sub: string;
  issue?: boolean;
  danger?: boolean;
  muted?: boolean;
};

export type StudioColumn = {
  title: string;
  count: number;
  add: string;
  items: StudioItem[];
};

// The medicine column changes when the faculty member fixes the RxNorm mismatch.
export function studioPatientColumns(drugFixed: boolean): StudioColumn[] {
  return [
    {
      title: "Diagnoses",
      count: 3,
      add: "Add diagnosis",
      items: [
        { name: "Type 2 diabetes with hyperglycemia", code: "E11.65", sub: "" },
        { name: "Chronic systolic heart failure", code: "I50.22", sub: "" },
        { name: "Essential hypertension", code: "I10", sub: "" },
      ],
    },
    {
      title: "Medicines",
      count: 4,
      add: "Add medicine",
      items: [
        { name: "Metformin", code: "", sub: "500 mg twice daily with meals" },
        { name: "Lisinopril", code: "", sub: "20 mg once daily" },
        { name: "Eplerenone", code: "", sub: "25 mg once daily" },
        drugFixed
          ? { name: "Epirocil", code: "", sub: "Kept as written", muted: true }
          : { name: "Epirocil", code: "", sub: "Not found in RxNorm. Did you mean eplerenone?", issue: true },
      ],
    },
    {
      title: "Allergies",
      count: 3,
      add: "Add allergy",
      items: [
        { name: "Penicillin", code: "", sub: "Hives" },
        { name: "Shellfish", code: "", sub: "Anaphylaxis", danger: true },
        { name: "Sulfa", code: "", sub: "Rash" },
      ],
    },
  ];
}

export const STUDIO_OBJECTIVES: { n: number; text: string; facts: string[]; checks: string[] }[] = [
  {
    n: 1,
    text: "Connect his medicines to nutrition care, including over-the-counter pain relievers",
    facts: ["Ibuprofen for back pain", "Skips metformin for nausea"],
    checks: ["explains the ibuprofen risk"],
  },
  { n: 2, text: "Find his eating pattern, beliefs and barriers", facts: ["Dinner club twice a week", "Canned soups"], checks: [] },
  { n: 3, text: "Identify social and money barriers", facts: ["Fixed income", "Lives alone"], checks: [] },
];

export const STUDIO_SUGGESTED_FACTS: { id: "a" | "b"; page: number; text: string }[] = [
  { id: "a", page: 42, text: "Sodium under 2,300 mg a day is a common target for people with diabetes and high blood pressure." },
  { id: "b", page: 56, text: "Ask about over-the-counter pain relievers when kidney function is reduced." },
];

export type TreeNodeKind = "start" | "decision" | "outcome";

export type TreeNode = {
  kind: TreeNodeKind;
  x: number;
  y: number;
  w: number;
  title: string;
  detail: string;
};

export type TreeNodeId = "start" | "q1" | "o1" | "q2" | "o2" | "o3";

export const TREE_START_NODES: Record<TreeNodeId, TreeNode> = {
  start: { kind: "start", x: 380, y: 24, w: 200, title: "Visit 1 begins", detail: "Outpatient psychiatry follow-up." },
  q1: { kind: "decision", x: 340, y: 112, w: 280, title: "Asked about mania history?", detail: "The student asks about past high-energy or manic periods." },
  o1: { kind: "outcome", x: 70, y: 300, w: 300, title: "Visit 2", detail: "Mood improving, no signs of hypomania." },
  q2: { kind: "decision", x: 560, y: 300, w: 290, title: "Assessed for suicidal ideation?", detail: "The student asks directly about thoughts of self-harm or suicide." },
  o2: { kind: "outcome", x: 330, y: 500, w: 290, title: "Visit 2", detail: "Sleeping less, talking fast, PHQ-9 improved." },
  o3: { kind: "outcome", x: 700, y: 500, w: 290, title: "Visit 2", detail: "Same hypomanic signs, and suicidal thoughts were never checked." },
};

export const TREE_EDGES: [TreeNodeId, TreeNodeId, string][] = [
  ["start", "q1", ""],
  ["q1", "o1", "Yes"],
  ["q1", "q2", "No"],
  ["q2", "o2", "Yes"],
  ["q2", "o3", "No"],
];
