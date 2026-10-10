import type { PublicCase } from "../../api/client";

type DoorwayVital = NonNullable<PublicCase["doorway_vitals"]>[number];

export type VitalCell = {
  key: string;
  label: string;
  value: string;
  unit: string;
  // A second reading of the same value, such as Celsius beside Fahrenheit.
  alt?: string;
  source: string;
};

// The order a nurse reads them out at the door. Unknown keys keep their case order after these.
const ORDER = ["temp_c", "temp_f", "hr", "rr", "bp", "spo2", "height", "weight", "bmi"];

// Doorway vitals as one row: Fahrenheit first with Celsius beside it, and body mass index
// calculated from height and weight when the case has both. Values are never invented.
export function doorwayRow(vitals: DoorwayVital[]): VitalCell[] {
  const cells: VitalCell[] = vitals.map((vital) => ({
    key: vital.key,
    label: vital.label,
    value: vital.value,
    unit: vital.unit,
    source: vital.source.kind,
  }));
  const temp = cells.find((cell) => cell.key === "temp_c" || cell.key === "temp_f");
  if (temp) Object.assign(temp, fahrenheitFirst(temp));
  const bmi = bodyMassIndex(cells);
  if (bmi && !cells.some((cell) => cell.key === "bmi")) cells.push(bmi);
  const rank = (key: string) => {
    const index = ORDER.indexOf(key);
    return index === -1 ? ORDER.length : index;
  };
  return cells.map((cell, index) => ({ cell, index })).sort((a, b) => rank(a.cell.key) - rank(b.cell.key) || a.index - b.index).map((item) => item.cell);
}

function fahrenheitFirst(cell: VitalCell): Partial<VitalCell> {
  const reading = Number(cell.value);
  if (!Number.isFinite(reading)) return {};
  if (cell.unit.includes("C")) {
    return { value: ((reading * 9) / 5 + 32).toFixed(1), unit: "°F", alt: `${cell.value} °C` };
  }
  if (cell.unit.includes("F")) {
    return { alt: `${(((reading - 32) * 5) / 9).toFixed(1)} °C` };
  }
  return {};
}

// Standard formula: kg / m², or 703 × lb / in². Skipped when either value is missing or in another unit.
function bodyMassIndex(cells: VitalCell[]): VitalCell | null {
  const height = cells.find((cell) => cell.key === "height");
  const weight = cells.find((cell) => cell.key === "weight");
  if (!height || !weight) return null;
  const h = Number(height.value);
  const w = Number(weight.value);
  if (!(h > 0) || !(w > 0)) return null;
  let bmi: number | null = null;
  if (height.unit === "in" && weight.unit === "lb") bmi = (703 * w) / (h * h);
  if (height.unit === "cm" && weight.unit === "kg") bmi = w / ((h / 100) * (h / 100));
  if (bmi === null) return null;
  return { key: "bmi", label: "Body mass index", value: bmi.toFixed(1), unit: "kg/m²", source: "calculated from height and weight" };
}
