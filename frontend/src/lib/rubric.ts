// The official SHP 7-domain rubric, in order. The backend ships the same labels
// in backend/app/data/rubric_shp_v1.json; this list becomes the API version when
// Studio and the debrief read real data.
export const RUBRIC_DOMAINS = [
  "Opening and purpose",
  "Rapport, respect, and empathy",
  "Information gathering",
  "Listening and response to cues",
  "Explanation and shared decisions",
  "Clinical reasoning and synthesis",
  "Professionalism, safety, and closure",
] as const;
