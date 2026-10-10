// Prototype fixtures for faculty screens that are not on the API yet.
// The Case Library and the sample-set import do not use these.

export const FACULTY_STATS: { label: string; value: string; note: string; accent: "none" | "danger" }[] = [
  { label: "Needs your review", value: "3", note: "visits flagged", accent: "danger" },
  { label: "Visits completed", value: "28", note: "of 48 assigned", accent: "none" },
];

export const WEAKEST_DOMAIN = {
  label: "Weakest rubric domain",
  title: "Professionalism, safety, and closure",
  note: "Class average 1.8 of 4",
};

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
