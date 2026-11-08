export type Mode = "demo" | "live";
export type Page =
  | "capture"
  | "manual"
  | "journal"
  | "insights"
  | "recipes"
  | "catalog"
  | "settings"
  | "about";
export type MealType = "breakfast" | "lunch" | "dinner" | "snack";
export type Stage =
  | "intake"
  | "identify"
  | "retrieve"
  | "calculate"
  | "review"
  | "explain"
  | "complete";
export type JobStatus =
  "queued" | "running" | "complete" | "failed" | "cancelled";
export type PortionSource =
  "weighed" | "user_estimate" | "label" | "image_estimate";
export type NutrientKey = keyof Nutrients;

export interface Nutrients {
  energy_kcal: number | null;
  protein_g: number | null;
  carbohydrate_g: number | null;
  fat_g: number | null;
  fiber_g: number | null;
  sugar_g: number | null;
  sodium_mg: number | null;
}

export interface Source {
  provider: string;
  record_id: string;
  title: string;
  url: string | null;
  retrieved_at: string;
  license: string;
  basis: "per_100g" | "recipe";
  is_demo: boolean;
}

export interface Serving {
  label: string;
  grams: number;
}

export interface Food {
  id: string;
  name: string;
  aliases: string[];
  category: string;
  preparation: string;
  nutrients: Nutrients;
  source: Source;
  servings: Serving[];
  allergens: string[];
  notes: string;
}

export interface FoodMatch {
  food: Food;
  score: number;
  matched_alias: string;
  exact: boolean;
}

export interface FoodSelection {
  food_id: string;
  grams: number;
  portion_source: PortionSource;
  uncertainty_percent: number;
}

export interface Candidate {
  label: string;
  confidence: number;
  grams: number | null;
  evidence: string;
  food_id: string | null;
  alternatives: FoodMatch[];
}

export interface AnalysisRequest {
  image_id?: string | null;
  source_analysis_id?: string | null;
  description: string;
  items: FoodSelection[];
  meal_name: string;
  meal_type: MealType;
  language: "en" | "bn";
  detailed: boolean;
  confirmed: boolean;
}

export interface Portion {
  food: Food;
  grams: number;
  portion_source: PortionSource;
  uncertainty_percent: number;
  nutrients: Nutrients;
  lower: Nutrients;
  upper: Nutrients;
}

export interface QualityFlag {
  code: string;
  severity: "info" | "warning" | "error";
  message: string;
  item_id?: string | null;
}

export interface Evidence {
  statements: string[];
  assumptions: string[];
  missing_information: string[];
}

export interface RuntimeStats {
  queue_ms: number;
  total_ms: number;
  model_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  tokens_per_second: number | null;
  gpu_peak_mb: number | null;
  cache_hit: boolean;
  backend: string;
}

export interface AnalysisResult {
  id: string;
  created_at: string;
  meal_name: string;
  meal_type: MealType;
  mode: Mode;
  needs_confirmation: boolean;
  candidates: Candidate[];
  portions: Portion[];
  totals: Nutrients;
  lower: Nutrients;
  upper: Nutrients;
  coverage: Record<NutrientKey, number>;
  flags: QualityFlag[];
  evidence: Evidence;
  explanation: string;
  stats: RuntimeStats;
  catalog_version: string;
  image_id?: string | null;
}

export interface JobEvent {
  sequence: number;
  job_id: string;
  stage: Stage;
  state: "started" | "completed" | "warning" | "failed" | "cancelled";
  message: string;
  timestamp: string;
  progress: number;
  detail: Record<string, unknown>;
}

export interface Job {
  id: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  error: string | null;
  result: AnalysisResult | null;
  events: JobEvent[];
}

export interface JournalEntry {
  id: string;
  analysis_id: string;
  meal_name: string;
  meal_type: MealType;
  eaten_at: string;
  notes: string;
  result: AnalysisResult;
}

export interface Preferences {
  language: "en" | "bn";
  units: "metric";
  reduced_motion: boolean;
  save_images: boolean;
  energy_target: number | null;
  protein_target: number | null;
  dietary_notes: string;
  timezone: string;
}

export interface RecipeIngredient {
  food_id: string;
  grams: number;
}

export interface RecipeInput {
  name: string;
  ingredients: RecipeIngredient[];
  cooked_weight_g: number;
  servings: number;
  notes: string;
}

export interface Recipe extends RecipeInput {
  id: string;
  created_at: string;
  per_100g: Nutrients;
  total: Nutrients;
  sources: Source[];
  coverage: Record<NutrientKey, number>;
}

export interface Capabilities {
  backend: string;
  model_label: string;
  loaded: boolean;
  vision: boolean;
  thinking: boolean;
  quantization: string;
  context_tokens: number;
  max_new_tokens: number;
  device: string;
  catalog_count: number;
  catalog_version: string;
}

export interface ChatAnswer {
  answer: string;
  evidence: string[];
  mode: Mode;
  stats: RuntimeStats;
}

export interface DaySummary {
  date: string;
  meal_count: number;
  totals: Nutrients;
  coverage: Record<NutrientKey, number>;
}

export interface Summary {
  start: string;
  end: string;
  timezone: string;
  meal_count: number;
  recorded_days: number;
  totals: Nutrients;
  coverage: Record<NutrientKey, number>;
  days: DaySummary[];
  note: string;
}

export interface LabelResult {
  available?: boolean;
  text?: string;
  nutrients?: Nutrients;
  basis?: string;
  serving_grams?: number | null;
  needs_confirmation?: boolean;
  warning?: string;
  message?: string;
}

export interface Session {
  username?: string;
  authenticated: boolean;
  csrf_token?: string | null;
  mode: Mode;
  expires_at?: string | null;
}

export interface ImageUpload {
  id: string;
  width: number;
  height: number;
  bytes: number;
}

export interface JournalPatch {
  meal_name?: string;
  meal_type?: MealType;
  eaten_at?: string;
  notes?: string;
}

export interface WorkspaceApi {
  mode: Mode;
  login(password?: string, username?: string): Promise<Session>;
  session(): Promise<Session>;
  logout(): Promise<void>;
  capabilities(): Promise<Capabilities>;
  foods(query: string, category?: string): Promise<FoodMatch[]>;
  categories(): Promise<string[]>;
  upload(file: Blob): Promise<ImageUpload>;
  analyse(request: AnalysisRequest): Promise<string>;
  job(id: string): Promise<Job>;
  cancel(id: string): Promise<void>;
  subscribe(
    id: string,
    listener: (event: JobEvent) => void,
    done: () => void,
  ): () => void;
  journal(start?: string, end?: string): Promise<JournalEntry[]>;
  saveMeal(id: string, notes?: string): Promise<JournalEntry>;
  editMeal(id: string, patch: JournalPatch): Promise<JournalEntry>;
  deleteMeal(id: string): Promise<void>;
  summary(start: string, end: string): Promise<Summary>;
  preferences(): Promise<Preferences>;
  savePreferences(value: Preferences): Promise<Preferences>;
  recipes(): Promise<Recipe[]>;
  createRecipe(input: RecipeInput): Promise<Recipe>;
  deleteRecipe(id: string): Promise<void>;
  chat(message: string, analysisId?: string): Promise<ChatAnswer>;
  parseLabel(text: string): Promise<LabelResult>;
  imageLabel(id: string): Promise<LabelResult>;
  exportData(format: "json" | "csv"): Promise<Blob>;
  erase(): Promise<void>;
}
