import type { Portrait } from "../components/Avatar";

// Prototype fixtures for the student home screen. Swapped for the student API later.

export const UP_NEXT: { who: Portrait; banner: string; name: string; summary: string; chips: string[] } = {
  who: "walter",
  banner: "Up next · due in 7 days",
  name: "Walter Greene, 72",
  summary: "Assess diet and medicines; agree on one change.",
  chips: ["Visit 1 of 2", "Nutrition clinic", "About 15 min"],
};

export const STUDENT_VISITS: { name: string; meta: string; due: string; who: Portrait }[] = [
  { name: "Alina Reyes, 21", meta: "Visit 1 of 2 · Student health clinic", due: "Oct 24", who: "alina" },
  { name: "Eli Brooks, 6", meta: "Visit 1 of 1 · Pediatric clinic", due: "Nov 1", who: "eli" },
];

export const RECENT_FEEDBACK = {
  who: "Practice · Dominic Rivera, 22",
  next: "Try next: ask him to say the plan back",
  score: "19/28",
};
