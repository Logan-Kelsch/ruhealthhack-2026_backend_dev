// Prototype fixture for the debrief of the Walter Greene visit 1 encounter.
// Swapped for the feedback API later.

// One score per domain, in the official rubric order (see lib/rubric.ts).
export const RUBRIC_SCORES = [3, 3, 3, 2, 2, 3, 1];

export const DEBRIEF_TRANSCRIPT: [string, string, string][] = [
  ["00:04", "Walter", "Morning. The doctor said I should come talk about my salt."],
  ["00:11", "You", "Thanks for coming in, Mr. Greene. I’m Jordan, a dietetics student. What would you like to get out of today?"],
  ["00:20", "Walter", "You look like a kid."],
  ["01:02", "You", "What do you enjoy about dinner club?"],
  ["01:09", "Walter", "Seeing the guys. We do the diner Tuesdays and Fridays."],
  ["02:15", "You", "Your sodium load is driving fluid retention."],
  ["02:21", "Walter", "I don't know what that means."],
  ["03:40", "You", "Are you taking anything for pain right now?"],
  ["03:44", "Walter", "Advil for my back, a couple times a week."],
];

export const DEBRIEF_NEXT_STEP = "Ask Walter to say the plan back in his own words.";

export const DEBRIEF_STRENGTHS = [
  "Followed up on the dinner club",
  "Asked about over-the-counter pain medicine",
  "Summarized what matters to him",
];

export const DEBRIEF_IMPROVEMENTS = [
  "Explain salt in plain words",
  "Check understanding with teach-back",
  "Ask about money for groceries",
];

export const DEBRIEF_SAFETY_CHECK = "Ibuprofen with heart failure and kidney disease: found and explained";

export const DEBRIEF_NOTE_CHECK = {
  title: "1 claim in your note was never said in the visit:",
  quote: "eats breakfast daily",
};

// Trust events for the timeline tab (PRD F-04). Each change quotes the span that caused it.
export const DEBRIEF_TRUST: { time: string; seconds: number; change: number; label: string; quote: string }[] = [
  { time: "00:11", seconds: 11, change: 1, label: "Open question about his goals", quote: "What would you like to get out of today?" },
  { time: "01:02", seconds: 62, change: 1, label: "Personal cue followed up", quote: "What do you enjoy about dinner club?" },
  { time: "02:15", seconds: 135, change: -1, label: "Jargon without explanation", quote: "Your sodium load is driving fluid retention." },
  { time: "03:40", seconds: 220, change: 1, label: "Asked about over-the-counter medicine", quote: "Are you taking anything for pain right now?" },
];
