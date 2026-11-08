import { describe, expect, it } from "vitest";
import foods from "./demo-foods.json";
import { emptyStats } from "./defaults";
import {
  calculatePortion,
  coverageOf,
  emptyNutrients,
  formatNutrient,
  localDay,
  macroShares,
  scale,
  sumNutrients,
  summarize,
} from "./nutrition";
import type { AnalysisResult, Food, JournalEntry } from "./types";

const rice = foods.find((food) => food.id === "demo:rice") as Food;
const chicken = foods.find((food) => food.id === "demo:chicken") as Food;
const portion = (food: Food, grams: number) =>
  calculatePortion(food, {
    food_id: food.id,
    grams,
    portion_source: "weighed",
    uncertainty_percent: 2,
  });

function entry(
  id: string,
  eaten_at: string,
  energy: number | null,
): JournalEntry {
  const result: AnalysisResult = {
    id,
    created_at: eaten_at,
    meal_name: "Test meal",
    meal_type: "lunch",
    mode: "demo",
    needs_confirmation: false,
    candidates: [],
    portions: [],
    totals: { ...emptyNutrients(), energy_kcal: energy },
    lower: emptyNutrients(),
    upper: emptyNutrients(),
    coverage: coverageOf([]),
    flags: [],
    evidence: { statements: [], assumptions: [], missing_information: [] },
    explanation: "",
    stats: emptyStats(),
    catalog_version: "test",
  };
  return {
    id,
    analysis_id: id,
    meal_name: "Test meal",
    meal_type: "lunch",
    eaten_at,
    notes: "",
    result,
  };
}

describe("nutrition arithmetic and uncertainty", () => {
  it("matches the independently calculated backend golden meal", () => {
    const values = [portion(rice, 150), portion(chicken, 120)];
    const totals = sumNutrients(values.map((value) => value.nutrients));
    expect(totals.energy_kcal).toBe(393);
    expect(totals.protein_g).toBe(41.25);
    expect(sumNutrients(values.map((value) => value.lower)).energy_kcal).toBe(
      385.14,
    );
    expect(sumNutrients(values.map((value) => value.upper)).energy_kcal).toBe(
      400.86,
    );
  });

  it("preserves unknown nutrients when another ingredient is known", () => {
    const totals = sumNutrients([
      rice.nutrients,
      { ...chicken.nutrients, sodium_mg: null },
    ]);
    expect(totals.sodium_mg).toBeNull();
    expect(totals.energy_kcal).toBe(295);
    expect(
      coverageOf([rice.nutrients, { ...chicken.nutrients, sodium_mg: null }])
        .sodium_mg,
    ).toBe(0.5);
  });

  it("does not turn an empty meal into a zero-calorie observation", () => {
    expect(sumNutrients([])).toEqual(emptyNutrients());
    expect(coverageOf([]).energy_kcal).toBe(0);
    expect(formatNutrient(null)).toBe("—");
    expect(formatNutrient(0)).toBe("0");
  });

  it.each([NaN, Infinity, -1, 0, 5001])(
    "rejects an invalid portion %s",
    (grams) => {
      expect(() => portion(rice, grams)).toThrow();
    },
  );

  it("does not label image estimates as exact weights", () => {
    const value = calculatePortion(rice, {
      food_id: rice.id,
      grams: 100,
      portion_source: "image_estimate",
      uncertainty_percent: 0,
    });
    expect(value.uncertainty_percent).toBe(25);
    expect(value.lower.energy_kcal).toBe(97.5);
    expect(value.upper.energy_kcal).toBe(162.5);
  });

  it("requires finite nonnegative scaling", () => {
    expect(() => scale(rice.nutrients, Infinity)).toThrow();
    expect(() => scale(rice.nutrients, -1)).toThrow();
    expect(
      scale({ ...rice.nutrients, sodium_mg: null }, 2).sodium_mg,
    ).toBeNull();
  });

  it("uses macro energy shares without replacing the source energy", () => {
    const source = {
      ...emptyNutrients(),
      protein_g: 10,
      carbohydrate_g: 20,
      fat_g: 10,
      energy_kcal: 200,
    };
    const shares = macroShares(source);
    expect(shares.reduce((total, item) => total + item.share, 0)).toBeCloseTo(
      1,
    );
    expect(shares[0].share).toBeCloseTo(40 / 210);
    expect(source.energy_kcal).toBe(200);
    expect(macroShares({ ...source, fat_g: null })).toEqual([]);
  });
});

describe("journal dates and incomplete data", () => {
  it("assigns India midnight on the correct side of the UTC boundary", () => {
    expect(localDay("2026-10-17T18:29:59Z", "Asia/Kolkata")).toBe("2026-10-17");
    expect(localDay("2026-10-17T18:30:00Z", "Asia/Kolkata")).toBe("2026-10-18");
  });

  it("keeps one record per calendar day across a daylight-saving change", () => {
    const entries = [
      entry("a", "2026-03-08T04:59:00Z", 300),
      entry("b", "2026-03-08T05:00:00Z", 200),
    ];
    const result = summarize(
      entries,
      "2026-03-07",
      "2026-03-09",
      "America/New_York",
    );
    expect(result.days.map((day) => day.date)).toEqual([
      "2026-03-07",
      "2026-03-08",
      "2026-03-09",
    ]);
    expect(result.days.map((day) => day.meal_count)).toEqual([1, 1, 0]);
    expect(result.days[2].totals.energy_kcal).toBeNull();
    expect(result.recorded_days).toBe(2);
    expect(result.totals.energy_kcal).toBe(500);
  });

  it("does not silently drop an unknown-energy meal from totals", () => {
    const result = summarize(
      [
        entry("a", "2026-10-18T12:00:00Z", 100),
        entry("b", "2026-10-18T13:00:00Z", null),
      ],
      "2026-10-18",
      "2026-10-18",
      "UTC",
    );
    expect(result.meal_count).toBe(2);
    expect(result.totals.energy_kcal).toBeNull();
    expect(result.coverage.energy_kcal).toBe(0.5);
  });

  it("bounds date windows before allocating a long timeline", () => {
    expect(() => summarize([], "2026-01-01", "2026-12-31", "UTC")).toThrow();
    expect(() => summarize([], "invalid", "2026-12-31", "UTC")).toThrow();
    expect(() => summarize([], "2026-10-20", "2026-10-18", "UTC")).toThrow();
  });
});
