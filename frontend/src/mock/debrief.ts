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

export const DEBRIEF_SAFETY_CHECK = "Ibuprofen risk found and explained";

export const DEBRIEF_NOTE_CHECK = {
  title: "1 claim never said in the visit",
  quote: "“Eats breakfast daily”",
};
