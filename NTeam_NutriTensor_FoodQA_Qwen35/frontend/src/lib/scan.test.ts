import { afterEach, describe, expect, it, vi } from "vitest";
import { RETRY_MESSAGE, scanRequest, waitForAnalysis } from "./scan";
import type { AnalysisResult, WorkspaceApi } from "./types";

const result = { id: "meal", portions: [{ grams: 100 }] } as AnalysisResult;
function apiFor(job: ReturnType<typeof vi.fn>) {
  return {
    job,
    cancel: vi.fn().mockResolvedValue(undefined),
  } as unknown as WorkspaceApi;
}
afterEach(() => vi.useRealTimers());

describe("scan request boundary", () => {
  it("uses a bounded image task without an unrestricted user prompt", () => {
    expect(scanRequest("a".repeat(32), "bn")).toMatchObject({
      image_id: "a".repeat(32),
      description: "",
      detailed: false,
      confirmed: false,
      items: [],
      language: "bn",
    });
  });
});

describe("confirmed result waiting", () => {
  it("returns a completed result", async () => {
    const api = apiFor(
      vi.fn().mockResolvedValue({ status: "complete", result }),
    );
    expect(
      await waitForAnalysis(api, "meal", new AbortController().signal),
    ).toBe(result);
    expect(api.cancel).not.toHaveBeenCalled();
  });
  it("never treats an empty result as a successful food scan", async () => {
    const api = apiFor(
      vi
        .fn()
        .mockResolvedValue({ status: "complete", result: { portions: [] } }),
    );
    await expect(
      waitForAnalysis(api, "meal", new AbortController().signal),
    ).rejects.toThrow(RETRY_MESSAGE);
  });
  it("preserves the fixed food-only failure response", async () => {
    const api = apiFor(
      vi.fn().mockResolvedValue({ status: "failed", error: RETRY_MESSAGE }),
    );
    await expect(
      waitForAnalysis(api, "meal", new AbortController().signal),
    ).rejects.toThrow(RETRY_MESSAGE);
  });
  it("cancels on navigation before polling", async () => {
    const api = apiFor(vi.fn());
    const controller = new AbortController();
    controller.abort();
    await expect(
      waitForAnalysis(api, "meal", controller.signal),
    ).rejects.toMatchObject({ name: "AbortError" });
    expect(api.job).not.toHaveBeenCalled();
    expect(api.cancel).toHaveBeenCalledWith("meal");
  });
  it("waits for queued work and cancels a timed-out job", async () => {
    vi.useFakeTimers();
    const api = apiFor(vi.fn().mockResolvedValue({ status: "queued" }));
    const task = waitForAnalysis(
      api,
      "meal",
      new AbortController().signal,
      1000,
    );
    const assertion = expect(task).rejects.toThrow("timed out");
    await vi.advanceTimersByTimeAsync(1200);
    await assertion;
    expect(api.cancel).toHaveBeenCalledWith("meal");
  });
  it("aborts a queued wait without another poll", async () => {
    vi.useFakeTimers();
    const api = apiFor(vi.fn().mockResolvedValue({ status: "queued" }));
    const controller = new AbortController();
    const task = waitForAnalysis(api, "meal", controller.signal);
    const assertion = expect(task).rejects.toMatchObject({
      name: "AbortError",
    });
    await vi.advanceTimersByTimeAsync(1);
    controller.abort();
    await assertion;
    expect(api.job).toHaveBeenCalledTimes(1);
    expect(api.cancel).toHaveBeenCalledTimes(1);
  });
});
