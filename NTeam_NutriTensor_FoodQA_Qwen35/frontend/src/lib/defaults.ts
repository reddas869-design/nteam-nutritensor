import type { Preferences, RuntimeStats } from "./types";

export const defaultPreferences: Preferences = {
  language: "en",
  units: "metric",
  reduced_motion: false,
  save_images: false,
  energy_target: null,
  protein_target: null,
  dietary_notes: "",
  timezone: "Asia/Kolkata",
};

export function emptyStats(): RuntimeStats {
  return {
    queue_ms: 0,
    total_ms: 0,
    model_ms: 0,
    prompt_tokens: 0,
    completion_tokens: 0,
    tokens_per_second: null,
    gpu_peak_mb: null,
    cache_hit: false,
    backend: "demo",
  };
}

export const stageLabels = {
  intake: "Preparing your meal",
  identify: "Identifying foods",
  retrieve: "Finding source records",
  calculate: "Calculating nutrition",
  review: "Checking assumptions",
  explain: "Preparing your summary",
  complete: "Ready to review",
};
