// Prototype fixtures for the faculty screens (home, case library, import).
// Swapped for the cases API later.

export const FACULTY_STATS: { label: string; value: string; note: string; accent: "none" | "danger" }[] = [
  { label: "Needs your review", value: "3", note: "visits flagged", accent: "danger" },
  { label: "Visits completed", value: "28", note: "of 48 assigned", accent: "none" },
];

export const WEAKEST_DOMAIN = {
  label: "Weakest rubric domain",
  title: "Professionalism, safety, and closure",
  note: "Class average 1.8 of 4",
};

export type CaseRow = {
  name: string;
  learner: string;
  visits: number;
  status: "Published" | "Draft";
  tag: string;
  updated: string;
  who: "walter" | "alina" | "eli" | "generic";
};

export const CASE_ROWS: CaseRow[] = [
  { name: "Walter Greene, 72", learner: "Dietetics student", visits: 2, status: "Published", tag: "Typical", updated: "Oct 3", who: "walter" },
  { name: "Alina Reyes, 21", learner: "Third-year medical student", visits: 2, status: "Published", tag: "Typical", updated: "Sep 28", who: "alina" },
  { name: "Eli Brooks, 6", learner: "Physician assistant student", visits: 1, status: "Published", tag: "Typical", updated: "Sep 20", who: "eli" },
  { name: "Depression follow-up", learner: "Psychiatry clerkship", visits: 2, status: "Draft", tag: "Branching · decision tree", updated: "Today", who: "generic" },
];

export const FACULTY_CASES: { name: string; meta: string; who: "walter" | "alina" | "eli" }[] = [
  { name: "Walter Greene, 72", meta: "Published", who: "walter" },
  { name: "Alina Reyes, 21", meta: "Published", who: "alina" },
  { name: "Eli Brooks, 6", meta: "Published", who: "eli" },
];

export const REVIEW_QUEUE: { initials: string; who: string; caseName: string; when: string }[] = [
  { initials: "14", who: "Student 14", caseName: "Walter Greene, visit 1", when: "Yesterday, 4:12 pm" },
  { initials: "3", who: "Student 3", caseName: "Walter Greene, visit 1", when: "Yesterday, 11:40 am" },
  { initials: "21", who: "Student 21", caseName: "Walter Greene, visit 2", when: "Oct 8" },
];

export const ASSIGNMENTS: { name: string; done: string; pct: string; due: string }[] = [
  { name: "Walter Greene · Dietetics cohort A", done: "18/24", pct: "75%", due: "Oct 17" },
  { name: "Alina Reyes · Medicine year 3", done: "10/24", pct: "42%", due: "Oct 24" },
];

export type SamplePatient = {
  name: string;
  age: number;
  summary: string;
  flags: string[];
};

export const SAMPLE_PATIENTS: SamplePatient[] = [
  { name: "Dominic Rivera", age: 22, summary: "College athlete with low energy during training season.", flags: [] },
  { name: "Yvette Armstrong", age: 64, summary: "Newly diagnosed celiac disease, lives with her daughter.", flags: ["Gluten-free diet started before biopsy date"] },
  { name: "Nisha Patel", age: 29, summary: "Gestational diabetes at 28 weeks, vegetarian.", flags: [] },
  { name: "Omar Sinclair", age: 45, summary: "Six months after bariatric surgery. Protein and supplements.", flags: ["B12 listed twice with different doses"] },
  { name: "Marcus Ramirez", age: 59, summary: "COPD with unintended weight loss.", flags: [] },
  {
    name: "Walter Greene",
    age: 72,
    summary: "Heart failure, kidney disease and type 2 diabetes.",
    flags: [
      "Notes say high sodium, but the lab shows Na 136",
      "Widowed, but one line mentions his kids",
      "Unknown drug name: Epirocil",
      "Weight change described two different ways",
    ],
  },
  { name: "Wyatt Nelson", age: 18, summary: "Type 1 diabetes, moving out for college.", flags: [] },
  { name: "Vladko Bareche", age: 31, summary: "Crohn’s disease flare, low-residue diet questions.", flags: [] },
];
