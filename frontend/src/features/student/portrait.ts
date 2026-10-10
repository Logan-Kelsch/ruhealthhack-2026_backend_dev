import type { Portrait } from "../../components/Avatar";

// Picks a drawn portrait from the patient name or file. Unknown patients stay generic.
export function portraitFor(patient: { name: string; portrait?: string | null }): Portrait {
  const hint = `${patient.portrait ?? ""} ${patient.name}`.toLowerCase();
  if (hint.includes("walter")) return "walter";
  if (hint.includes("alina")) return "alina";
  if (hint.includes("eli")) return "eli";
  return "generic";
}
