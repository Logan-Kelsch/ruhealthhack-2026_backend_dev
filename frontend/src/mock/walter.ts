import type { VisitNumber } from "../app/types";

// Prototype fixture for the Walter Greene visit. Swapped for the case and
// encounter APIs when they land. Values stay in one place so the briefing,
// encounter and between-visits screens cannot drift apart.

type Fact = { k: string; v: string };
type VitalTone = "danger" | "ink";
type Vital = { k: string; v: string; note: string; tone: VitalTone };

export const WALTER_GOAL: Record<VisitNumber, string> = {
  1: "Assess diet and medicines; agree on one change.",
  2: "Review what changed since the first visit and adjust the plan.",
};

export const WALTER_BRIEFING_FACTS: Record<VisitNumber, Fact[]> = {
  1: [
    { k: "Setting", v: "Outpatient nutrition clinic" },
    { k: "Your role", v: "Dietetics student" },
    { k: "From primary care", v: "Heart failure, kidney disease and type 2 diabetes. Review sodium and diet." },
  ],
  2: [
    { k: "Setting", v: "Outpatient nutrition clinic" },
    { k: "Your role", v: "Dietetics student" },
    { k: "Your note from visit 1", v: "Excessive sodium intake related to frequent restaurant meals and canned soups." },
  ],
};

export const WALTER_BRIEFING_VITALS: Record<VisitNumber, Vital[]> = {
  1: [
    { k: "BP", v: "158/92", note: "Elevated", tone: "danger" },
    { k: "HR", v: "78", note: "bpm", tone: "ink" },
    { k: "RR", v: "18", note: "/min", tone: "ink" },
    { k: "Temp", v: "37.0", note: "°C", tone: "ink" },
    { k: "SpO₂", v: "96%", note: "Room air", tone: "ink" },
  ],
  2: [
    { k: "BP", v: "146/88", note: "Elevated", tone: "danger" },
    { k: "HR", v: "78", note: "bpm", tone: "ink" },
    { k: "RR", v: "18", note: "/min", tone: "ink" },
    { k: "Temp", v: "37.0", note: "°C", tone: "ink" },
    { k: "SpO₂", v: "96%", note: "Room air", tone: "ink" },
  ],
};

export const WALTER_ENCOUNTER_VITALS: Record<VisitNumber, { k: string; v: string; tone: VitalTone }[]> = {
  1: [
    { k: "BP", v: "158/92", tone: "danger" },
    { k: "HR", v: "78", tone: "ink" },
    { k: "RR", v: "18", tone: "ink" },
    { k: "Temp", v: "37.0°", tone: "ink" },
    { k: "SpO₂", v: "96%", tone: "ink" },
    { k: "Weight", v: "198 lb", tone: "ink" },
  ],
  2: [
    { k: "BP", v: "146/88", tone: "danger" },
    { k: "HR", v: "78", tone: "ink" },
    { k: "RR", v: "18", tone: "ink" },
    { k: "Temp", v: "37.0°", tone: "ink" },
    { k: "SpO₂", v: "96%", tone: "ink" },
    { k: "Weight", v: "198 lb", tone: "ink" },
  ],
};

export const WALTER_BETWEEN_VISITS_EVENTS: { text: string; tag: string; tone: "ok" | "warn" }[] = [
  { text: "Stopped the Advil", tag: "Followed plan", tone: "ok" },
  { text: "Same dinner-club meals twice a week", tag: "No change", tone: "warn" },
  { text: "Ankle swelling about the same", tag: "No change", tone: "warn" },
];

// Encounter script. New lines appear on a timer while the visit runs.
export const WALTER_SCRIPT: [string, string][] = [
  ["Walter", "Morning. The doctor said I should come talk about my salt."],
  ["You", "Thanks for coming in, Mr. Greene. I’m Jordan, a dietetics student. What would you like to get out of today?"],
  ["Walter", "You look like a kid."],
  ["You", "What do you enjoy about dinner club?"],
  ["Walter", "Seeing the guys. We do the diner Tuesdays and Fridays."],
  ["You", "Are you taking anything for pain right now?"],
  ["Walter", "Advil for my back, a couple times a week."],
  ["You", "I’m going to listen to your lungs now."],
];

export const WALTER_EXAMS: { label: string; text: string; flag: boolean }[] = [
  { label: "Check ankles for swelling", text: "Pedal edema 2+ both ankles", flag: true },
  { label: "Listen to lungs", text: "Fine crackles at both bases", flag: true },
  { label: "Check skin turgor", text: "Skin turgor normal", flag: false },
];

export const WALTER_MEDS: { id: "metformin" | "lisinopril" | "ibuprofen"; name: string; sub: string }[] = [
  { id: "metformin", name: "Metformin 500 mg", sub: "Twice daily" },
  { id: "lisinopril", name: "Lisinopril 20 mg", sub: "Daily" },
  { id: "ibuprofen", name: "Ibuprofen 400 mg", sub: "As needed" },
];

export const WALTER_ORDERS: { id: "ecg" | "cxr"; name: string }[] = [
  { id: "ecg", name: "12-lead ECG" },
  { id: "cxr", name: "Chest X-ray" },
];
