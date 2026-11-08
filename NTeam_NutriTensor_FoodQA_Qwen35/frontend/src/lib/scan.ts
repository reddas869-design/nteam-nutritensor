import type { AnalysisRequest, AnalysisResult, WorkspaceApi } from "./types";

export const RETRY_MESSAGE = "Something went wrong. Try again.";

export function scanRequest(
  imageId: string,
  language: "en" | "bn",
): AnalysisRequest {
  return {
    image_id: imageId,
    description: "",
    items: [],
    meal_name: "Food scan",
    meal_type: "snack",
    language,
    detailed: false,
    confirmed: false,
  };
}

function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer);
      reject(new DOMException("Cancelled", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, ms);
    if (signal.aborted) abort();
    else signal.addEventListener("abort", abort, { once: true });
  });
}

export async function waitForAnalysis(
  api: WorkspaceApi,
  id: string,
  signal: AbortSignal,
  timeoutMs = 480000,
): Promise<AnalysisResult> {
  const deadline = Date.now() + timeoutMs;
  try {
    while (!signal.aborted && Date.now() < deadline) {
      const job = await api.job(id);
      if (signal.aborted) throw new DOMException("Cancelled", "AbortError");
      if (job.status === "complete") {
        if (!job.result?.portions.length) throw new Error(RETRY_MESSAGE);
        return job.result;
      }
      if (job.status === "failed" || job.status === "cancelled")
        throw new Error(job.error || RETRY_MESSAGE);
      await pause(600, signal);
    }
    if (signal.aborted) throw new DOMException("Cancelled", "AbortError");
    throw new Error("The analysis timed out. Try again.");
  } catch (error) {
    await api.cancel(id).catch(() => undefined);
    throw error;
  }
}
