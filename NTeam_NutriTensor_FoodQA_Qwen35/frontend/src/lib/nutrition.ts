import type {
  AnalysisResult,
  Food,
  FoodSelection,
  JournalEntry,
  NutrientKey,
  Nutrients,
  Portion,
  Summary,
} from "./types";

export const NUTRIENTS: {
  key: NutrientKey;
  label: string;
  short: string;
  unit: string;
  color: string;
}[] = [
  {
    key: "energy_kcal",
    label: "Energy",
    short: "Energy",
    unit: "kcal",
    color: "#a9c88b",
  },
  {
    key: "protein_g",
    label: "Protein",
    short: "Protein",
    unit: "g",
    color: "#bfd390",
  },
  {
    key: "carbohydrate_g",
    label: "Carbohydrate",
    short: "Carbs",
    unit: "g",
    color: "#e9bc79",
  },
  { key: "fat_g", label: "Fat", short: "Fat", unit: "g", color: "#c8afd9" },
  {
    key: "fiber_g",
    label: "Dietary fiber",
    short: "Fiber",
    unit: "g",
    color: "#8fb8a9",
  },
  {
    key: "sugar_g",
    label: "Total sugars",
    short: "Sugars",
    unit: "g",
    color: "#d69b92",
  },
  {
    key: "sodium_mg",
    label: "Sodium",
    short: "Sodium",
    unit: "mg",
    color: "#a4bdcc",
  },
];

export const emptyNutrients = (): Nutrients => ({
  energy_kcal: null,
  protein_g: null,
  carbohydrate_g: null,
  fat_g: null,
  fiber_g: null,
  sugar_g: null,
  sodium_mg: null,
});

export function scale(nutrients: Nutrients, factor: number): Nutrients {
  if (!Number.isFinite(factor) || factor < 0)
    throw new Error("Invalid portion multiplier");
  return Object.fromEntries(
    Object.entries(nutrients).map(([key, value]) => [
      key,
      value === null ? null : Math.round(value * factor * 1000) / 1000,
    ]),
  ) as unknown as Nutrients;
}

export function sumNutrients(items: Nutrients[]): Nutrients {
  const output = emptyNutrients();
  for (const { key } of NUTRIENTS) {
    const values = items.map((item) => item[key]);
    output[key] =
      values.length && values.every((value) => value !== null)
        ? Math.round(
            values.reduce<number>((total, value) => total + (value ?? 0), 0) *
              1000,
          ) / 1000
        : null;
  }
  return output;
}

export function coverageOf(items: Nutrients[]): Record<NutrientKey, number> {
  return Object.fromEntries(
    NUTRIENTS.map(({ key }) => [
      key,
      items.length
        ? items.filter((item) => item[key] !== null).length / items.length
        : 0,
    ]),
  ) as Record<NutrientKey, number>;
}

export function calculatePortion(
  food: Food,
  selection: FoodSelection,
): Portion {
  if (
    !Number.isFinite(selection.grams) ||
    selection.grams <= 0 ||
    selection.grams > 5000
  ) {
    throw new Error("Enter a portion between 0 and 5,000 g");
  }
  if (
    !Number.isFinite(selection.uncertainty_percent) ||
    selection.uncertainty_percent < 0 ||
    selection.uncertainty_percent > 80
  ) {
    throw new Error("Portion uncertainty must be between 0 and 80%");
  }
  const uncertainty =
    selection.portion_source === "image_estimate"
      ? Math.max(25, selection.uncertainty_percent)
      : selection.uncertainty_percent;
  return {
    food,
    grams: selection.grams,
    portion_source: selection.portion_source,
    uncertainty_percent: uncertainty,
    nutrients: scale(food.nutrients, selection.grams / 100),
    lower: scale(
      food.nutrients,
      (selection.grams / 100) * (1 - uncertainty / 100),
    ),
    upper: scale(
      food.nutrients,
      (selection.grams / 100) * (1 + uncertainty / 100),
    ),
  };
}

export function formatNutrient(
  value: number | null | undefined,
  digits = 1,
): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatEnergy(value: number | null): string {
  return formatNutrient(value, 0);
}

export function macroShares(
  nutrients: Nutrients,
): { name: string; energy: number; share: number; color: string }[] {
  const { protein_g: p, carbohydrate_g: c, fat_g: f } = nutrients;
  if (p === null || c === null || f === null) return [];
  const total = p * 4 + c * 4 + f * 9;
  return [
    {
      name: "Protein",
      energy: p * 4,
      share: total ? (p * 4) / total : 0,
      color: "#bfd390",
    },
    {
      name: "Carbs",
      energy: c * 4,
      share: total ? (c * 4) / total : 0,
      color: "#e9bc79",
    },
    {
      name: "Fat",
      energy: f * 9,
      share: total ? (f * 9) / total : 0,
      color: "#c8afd9",
    },
  ];
}

export function localDay(iso: string, timezone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(iso));
  const values = Object.fromEntries(
    parts.map((part) => [part.type, part.value]),
  );
  return `${values.year}-${values.month}-${values.day}`;
}

export function summarize(
  entries: JournalEntry[],
  start: string,
  end: string,
  timezone: string,
): Summary {
  const selected = entries.filter((entry) => {
    const day = localDay(entry.eaten_at, timezone);
    return day >= start && day <= end;
  });
  const days = [];
  const first = new Date(`${start}T12:00:00Z`);
  const last = new Date(`${end}T12:00:00Z`);
  if (
    !Number.isFinite(first.getTime()) ||
    !Number.isFinite(last.getTime()) ||
    first > last
  ) {
    throw new Error("Invalid summary date range");
  }
  if ((last.getTime() - first.getTime()) / 86400000 > 90)
    throw new Error("Choose at most 91 days");
  for (let day = first; day <= last; day = new Date(day.getTime() + 86400000)) {
    const date = day.toISOString().slice(0, 10);
    const matching = selected.filter(
      (entry) => localDay(entry.eaten_at, timezone) === date,
    );
    const nutrients = matching.map((entry) => entry.result.totals);
    days.push({
      date,
      meal_count: matching.length,
      totals: sumNutrients(nutrients),
      coverage: coverageOf(nutrients),
    });
  }
  return {
    start,
    end,
    timezone,
    meal_count: selected.length,
    recorded_days: days.filter((day) => day.meal_count > 0).length,
    totals: sumNutrients(selected.map((entry) => entry.result.totals)),
    coverage: coverageOf(selected.map((entry) => entry.result.totals)),
    days,
    note: "Logged meals only. Unlogged intake is not estimated.",
  };
}

export function resultSelections(result: AnalysisResult): FoodSelection[] {
  return result.portions.map((portion) => ({
    food_id: portion.food.id,
    grams: portion.grams,
    portion_source: portion.portion_source,
    uncertainty_percent: portion.uncertainty_percent,
  }));
}
