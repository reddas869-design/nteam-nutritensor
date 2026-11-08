import rawFoods from "./demo-foods.json";
import * as storage from "./storage";
import { defaultPreferences, emptyStats, stageLabels } from "./defaults";
import {
  calculatePortion,
  coverageOf,
  emptyNutrients,
  scale,
  sumNutrients,
  summarize,
} from "./nutrition";
import { toCsv } from "./export";
import type {
  AnalysisRequest,
  AnalysisResult,
  Capabilities,
  ChatAnswer,
  Food,
  FoodMatch,
  ImageUpload,
  Job,
  JobEvent,
  JournalEntry,
  JournalPatch,
  LabelResult,
  Preferences,
  Recipe,
  RecipeInput,
  Session,
  Stage,
  Summary,
  WorkspaceApi,
} from "./types";

const foods = rawFoods as Food[];
const id = () => crypto.randomUUID().replaceAll("-", "");
const now = () => new Date().toISOString();
const normalize = (value: string) =>
  value
    .normalize("NFKC")
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();

export class DemoApi implements WorkspaceApi {
  mode = "demo" as const;
  private jobs = new Map<string, Job>();
  private listeners = new Map<string, Set<(event: JobEvent) => void>>();
  private completion = new Map<string, Set<() => void>>();

  async login(): Promise<Session> {
    return { authenticated: true, mode: "demo" };
  }

  async session(): Promise<Session> {
    return this.login();
  }

  async logout(): Promise<void> {
    return;
  }

  async capabilities(): Promise<Capabilities> {
    return {
      backend: "browser-demo",
      model_label: "Interactive demo · no model connected",
      loaded: false,
      vision: false,
      thinking: false,
      quantization: "none",
      context_tokens: 0,
      max_new_tokens: 0,
      device: "This browser",
      catalog_count: foods.length,
      catalog_version: "demo-fixtures-v1",
    };
  }

  async foods(query: string, category?: string): Promise<FoodMatch[]> {
    const needle = normalize(query);
    const results: FoodMatch[] = [];
    for (const food of foods) {
      if (category && food.category !== category) continue;
      let score = needle ? 0 : 0.1;
      let matched = food.name;
      for (const alias of [food.name, ...food.aliases]) {
        const term = normalize(alias);
        let next = 0;
        if (term === needle) next = 1;
        else if (term.includes(needle) && needle) next = 0.85;
        else if (needle.includes(term) && term) next = 0.8;
        else {
          const left = new Set(needle.split(" "));
          const right = term.split(" ");
          const common = right.filter((word) => left.has(word)).length;
          next = common / Math.max(left.size, right.length, 1);
        }
        if (next > score) {
          score = next;
          matched = alias;
        }
      }
      if (score > 0)
        results.push({
          food: structuredClone(food),
          score,
          matched_alias: matched,
          exact: score === 1,
        });
    }
    return results.sort(
      (a, b) => b.score - a.score || a.food.name.localeCompare(b.food.name),
    );
  }

  async categories(): Promise<string[]> {
    return [...new Set(foods.map((food) => food.category))].sort();
  }

  async upload(file: Blob): Promise<ImageUpload> {
    if (file.size > 10 * 1024 * 1024)
      throw new Error("Choose an image smaller than 10 MB");
    return { id: id(), width: 0, height: 0, bytes: file.size };
  }

  async analyse(request: AnalysisRequest): Promise<string> {
    if (request.image_id && !request.items.length) {
      throw new Error("Something went wrong. Try again.");
    }
    const jobId = id();
    const job: Job = {
      id: jobId,
      status: "queued",
      created_at: now(),
      updated_at: now(),
      error: null,
      result: null,
      events: [],
    };
    this.jobs.set(jobId, job);
    // Short visual staging is illustrative and never reported as GPU benchmark data.
    window.setTimeout(() => void this.run(job, request), 30);
    return jobId;
  }

  private async run(job: Job, request: AnalysisRequest): Promise<void> {
    try {
      job.status = "running";
      const stages: Stage[] = [
        "intake",
        "identify",
        "retrieve",
        "calculate",
        "review",
        "explain",
      ];
      for (const [index, stage] of stages.entries()) {
        if ((job.status as string) === "cancelled") return;
        const event: JobEvent = {
          sequence: index + 1,
          job_id: job.id,
          stage,
          state: "completed",
          message: `Demo · ${stageLabels[stage]}`,
          timestamp: now(),
          progress: (index + 1) / 7,
          detail: {},
        };
        job.events.push(event);
        this.listeners.get(job.id)?.forEach((listener) => listener(event));
        await new Promise((resolve) => window.setTimeout(resolve, 95));
      }
      let selections = request.items;
      if (!selections.length) {
        const matches = await this.foods(request.description);
        selections = matches
          .filter((match) => match.exact)
          .slice(0, 12)
          .map((match) => ({
            food_id: match.food.id,
            grams: 100,
            portion_source: "user_estimate" as const,
            uncertainty_percent: 25,
          }));
      }
      if (!selections.length)
        throw new Error("No foods matched. Choose foods from the search list.");
      const portions = selections.map((selection) => {
        const food = foods.find(
          (candidate) => candidate.id === selection.food_id,
        );
        if (!food)
          throw new Error("This food is unavailable in the demo catalog");
        return calculatePortion(food, selection);
      });
      const result: AnalysisResult = {
        id: job.id,
        created_at: now(),
        meal_name: request.meal_name,
        meal_type: request.meal_type,
        mode: "demo",
        needs_confirmation: !request.confirmed,
        candidates: portions.map((portion) => ({
          label: portion.food.name,
          confidence: 1,
          grams: portion.grams,
          evidence: "Example food selection; not image recognition",
          food_id: portion.food.id,
          alternatives: [],
        })),
        portions,
        totals: sumNutrients(portions.map((portion) => portion.nutrients)),
        lower: sumNutrients(portions.map((portion) => portion.lower)),
        upper: sumNutrients(portions.map((portion) => portion.upper)),
        coverage: coverageOf(portions.map((portion) => portion.nutrients)),
        flags: [
          {
            code: "demo_data",
            severity: "warning",
            message:
              "Illustrative demo data. Connect a verified catalog for real nutrition.",
          },
        ],
        evidence: {
          statements: [
            "Each nutrient = source value per 100 g × portion grams ÷ 100.",
            "Meal totals sum the selected foods.",
            "Unknown nutrient values remain unknown.",
          ],
          assumptions: portions
            .filter((portion) => portion.portion_source !== "weighed")
            .map(
              (portion) =>
                `${portion.food.name}: ${portion.grams} g is an estimated portion.`,
            ),
          missing_information: [
            "Cooking oil, sauces and preparation may change the result.",
            "This example is not a food-recognition result.",
          ],
        },
        explanation:
          "A clearer picture starts with the portion. These example foods combine a grain, a protein and vegetables. Adjust the grams to see how the calculated nutrients change. The range reflects portion uncertainty, not a statistical confidence interval.",
        stats: emptyStats(),
        catalog_version: "demo-fixtures-v1",
        image_id: null,
      };
      if ((job.status as string) === "cancelled") return;
      job.status = "complete";
      job.result = result;
      job.updated_at = now();
      await storage.write(`job:${job.id}`, job);
    } catch (error) {
      job.status = "failed";
      job.error =
        error instanceof Error ? error.message : "Demo analysis failed";
    } finally {
      this.completion.get(job.id)?.forEach((listener) => listener());
      this.listeners.delete(job.id);
      this.completion.delete(job.id);
    }
  }

  async job(jobId: string): Promise<Job> {
    const job =
      this.jobs.get(jobId) ??
      (await storage.read<Job | null>(`job:${jobId}`, null));
    if (!job) throw new Error("Analysis not found in this browser");
    return structuredClone(job);
  }

  async cancel(jobId: string): Promise<void> {
    const job = this.jobs.get(jobId);
    if (!job || !["queued", "running"].includes(job.status)) return;
    job.status = "cancelled";
    this.completion.get(jobId)?.forEach((listener) => listener());
  }

  subscribe(
    jobId: string,
    listener: (event: JobEvent) => void,
    done: () => void,
  ): () => void {
    const listeners = this.listeners.get(jobId) ?? new Set();
    const finishers = this.completion.get(jobId) ?? new Set();
    listeners.add(listener);
    finishers.add(done);
    this.listeners.set(jobId, listeners);
    this.completion.set(jobId, finishers);
    for (const event of this.jobs.get(jobId)?.events ?? []) listener(event);
    const status = this.jobs.get(jobId)?.status;
    if (status && ["complete", "failed", "cancelled"].includes(status))
      queueMicrotask(done);
    return () => {
      listeners.delete(listener);
      finishers.delete(done);
    };
  }

  async journal(start?: string, end?: string): Promise<JournalEntry[]> {
    const entries = await storage.read<JournalEntry[]>("journal", []);
    if (!start || !end)
      return entries.sort((a, b) => b.eaten_at.localeCompare(a.eaten_at));
    const first = new Date(`${start}T00:00:00`).getTime();
    const last = new Date(`${end}T23:59:59.999`).getTime();
    return entries.filter((entry) => {
      const when = new Date(entry.eaten_at).getTime();
      return when >= first && when <= last;
    });
  }

  async saveMeal(jobId: string, notes = ""): Promise<JournalEntry> {
    const job = await this.job(jobId);
    if (!job.result || job.result.needs_confirmation)
      throw new Error("Confirm foods and portions before saving");
    const entry: JournalEntry = {
      id: id(),
      analysis_id: jobId,
      meal_name: job.result.meal_name,
      meal_type: job.result.meal_type,
      eaten_at: now(),
      notes,
      result: job.result,
    };
    const entries = await storage.mutate<JournalEntry[]>(
      "journal",
      [],
      (current) => {
        if (current.some((item) => item.analysis_id === jobId)) return current;
        return [entry, ...current];
      },
    );
    return entries.find((item) => item.analysis_id === jobId)!;
  }

  async editMeal(entryId: string, patch: JournalPatch): Promise<JournalEntry> {
    const entries = await storage.mutate<JournalEntry[]>(
      "journal",
      [],
      (current) =>
        current.map((entry) =>
          entry.id === entryId ? { ...entry, ...patch } : entry,
        ),
    );
    const found = entries.find((entry) => entry.id === entryId);
    if (!found) throw new Error("Meal not found");
    return found;
  }

  async deleteMeal(entryId: string): Promise<void> {
    await storage.mutate<JournalEntry[]>("journal", [], (current) =>
      current.filter((entry) => entry.id !== entryId),
    );
  }

  async summary(start: string, end: string): Promise<Summary> {
    const preferences = await this.preferences();
    return summarize(await this.journal(), start, end, preferences.timezone);
  }

  preferences(): Promise<Preferences> {
    return storage.read("preferences", defaultPreferences);
  }

  savePreferences(value: Preferences): Promise<Preferences> {
    return storage.write("preferences", value);
  }

  recipes(): Promise<Recipe[]> {
    return storage.read("recipes", []);
  }

  async createRecipe(input: RecipeInput): Promise<Recipe> {
    if (!input.ingredients.length || input.cooked_weight_g <= 0)
      throw new Error("Add ingredients and the final cooked weight");
    const portions = input.ingredients.map((ingredient) => {
      const food = foods.find((item) => item.id === ingredient.food_id);
      if (!food) throw new Error("Ingredient is unavailable");
      return calculatePortion(food, {
        ...ingredient,
        portion_source: "weighed",
        uncertainty_percent: 0,
      });
    });
    const total = sumNutrients(portions.map((portion) => portion.nutrients));
    const recipe: Recipe = {
      ...input,
      id: id(),
      created_at: now(),
      per_100g: scale(total, 100 / input.cooked_weight_g),
      total,
      sources: portions.map((portion) => portion.food.source),
      coverage: coverageOf(portions.map((portion) => portion.nutrients)),
    };
    await storage.mutate<Recipe[]>("recipes", [], (current) => [
      recipe,
      ...current,
    ]);
    return recipe;
  }

  async deleteRecipe(recipeId: string): Promise<void> {
    await storage.mutate<Recipe[]>("recipes", [], (current) =>
      current.filter((recipe) => recipe.id !== recipeId),
    );
  }

  async chat(message: string, analysisId?: string): Promise<ChatAnswer> {
    const allowed = [
      "how many calories are in this meal",
      "how much protein is in this meal",
      "explain the portions",
      "why are some values unknown",
      "এই খাবারে কত ক্যালোরি",
      "এই খাবারে কত প্রোটিন",
    ];
    if (
      !analysisId ||
      !allowed.includes(
        message
          .toLowerCase()
          .trim()
          .replace(/[?.!।]+$/, "")
          .replace(/\s+/g, " "),
      )
    )
      throw new Error("Sir, something went wrong. plz try again.");
    const job = analysisId ? await this.job(analysisId) : null;
    return {
      answer:
        "This interactive demo uses example foods. We can edit portions, inspect sources, build recipes and save a meal.",
      evidence:
        job?.result?.portions.map((portion) => portion.food.source.title) ?? [],
      mode: "demo",
      stats: emptyStats(),
    };
  }

  async parseLabel(text: string): Promise<LabelResult> {
    const nutrients = emptyNutrients();
    const patterns = [
      ["energy_kcal", /(?:energy|calories)\s*:?\s*(\d+(?:\.\d+)?)\s*kcal/i],
      ["protein_g", /protein\s*:?\s*(\d+(?:\.\d+)?)\s*g/i],
      ["carbohydrate_g", /carbohydrates?\s*:?\s*(\d+(?:\.\d+)?)\s*g/i],
      ["fat_g", /(?:total\s+)?fat\s*:?\s*(\d+(?:\.\d+)?)\s*g/i],
      ["sodium_mg", /sodium\s*:?\s*(\d+(?:\.\d+)?)\s*mg/i],
    ] as const;
    for (const [field, expression] of patterns) {
      const match = text.match(expression);
      if (match) nutrients[field] = Number(match[1]);
    }
    return {
      nutrients,
      basis: /per\s*100\s*g/i.test(text) ? "100g" : "unknown",
      needs_confirmation: true,
      warning:
        "Verify the basis, decimals and units against the package. Label parsing is not food recognition.",
    };
  }

  async imageLabel(): Promise<LabelResult> {
    return {
      available: false,
      text: "",
      message: "Photo OCR requires the local backend. Paste label text below.",
    };
  }

  async exportData(format: "json" | "csv"): Promise<Blob> {
    const entries = await this.journal();
    if (format === "json") {
      return new Blob(
        [
          JSON.stringify(
            {
              schema_version: 1,
              application: "NTeam NutriTensor",
              mode: "demo",
              exported_at: now(),
              journal: entries,
              preferences: await this.preferences(),
              recipes: await this.recipes(),
            },
            null,
            2,
          ),
        ],
        { type: "application/json" },
      );
    }
    return new Blob([toCsv(entries)], { type: "text/csv;charset=utf-8" });
  }

  async erase(): Promise<void> {
    for (const job of this.jobs.values()) job.status = "cancelled";
    this.jobs.clear();
    await storage.clear();
  }
}
