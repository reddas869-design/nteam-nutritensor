import type {
  AnalysisRequest,
  Capabilities,
  ChatAnswer,
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
  Summary,
  WorkspaceApi,
} from "./types";
import { consumeEvents } from "./sse";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code = "request_failed",
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class LiveApi implements WorkspaceApi {
  mode: "demo" | "live" = "live";
  private csrf: string | null = null;
  private base: string;

  constructor(base = "") {
    this.base = base.replace(/\/$/, "");
    if (this.base) {
      const parsed = new URL(this.base);
      if (
        !["http:", "https:"].includes(parsed.protocol) ||
        parsed.username ||
        parsed.password
      ) {
        throw new Error("Enter a valid HTTP or HTTPS workspace URL");
      }
      if (
        window.location.protocol === "https:" &&
        parsed.protocol !== "https:"
      ) {
        throw new Error(
          "An HTTPS page requires an HTTPS backend. Run the app locally with its same-origin proxy.",
        );
      }
    }
  }

  private async request<T>(
    path: string,
    options: RequestInit = {},
  ): Promise<T> {
    const controller = new AbortController();
    const timeout = window.setTimeout(
      () => controller.abort(),
      path === "/chat" ? 180000 : 30000,
    );
    const headers = new Headers(options.headers);
    if (options.body && !(options.body instanceof FormData))
      headers.set("Content-Type", "application/json");
    if (this.csrf && options.method && options.method !== "GET")
      headers.set("X-CSRF-Token", this.csrf);
    try {
      const response = await fetch(`${this.base}/api/v1${path}`, {
        ...options,
        headers,
        credentials: "include",
        signal: options.signal ?? controller.signal,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new ApiError(
          response.status,
          payload.message ??
            payload.detail ??
            `Request failed (${response.status})`,
          payload.error,
        );
      }
      if (response.status === 204) return undefined as T;
      return (await response.json()) as T;
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new ApiError(
          408,
          "The connection timed out. Check your local server.",
        );
      }
      throw error;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  async health(): Promise<{ mode: "demo" | "live" }> {
    return this.request("/health");
  }

  async login(password = "", username = "owner"): Promise<Session> {
    const session = await this.request<Session>("/session", {
      method: "POST",
      body: JSON.stringify({ password, username }),
    });
    this.csrf = session.csrf_token ?? null;
    this.mode = session.mode;
    return session;
  }

  async session(): Promise<Session> {
    const session = await this.request<Session>("/session");
    this.csrf = session.csrf_token ?? null;
    this.mode = session.mode;
    return session;
  }

  async logout(): Promise<void> {
    await this.request("/session", { method: "DELETE" });
    this.csrf = null;
  }

  capabilities(): Promise<Capabilities> {
    return this.request("/capabilities");
  }

  async foods(query: string, category?: string): Promise<FoodMatch[]> {
    const params = new URLSearchParams({ q: query, limit: "50" });
    if (category) params.set("category", category);
    return (await this.request<{ items: FoodMatch[] }>(`/foods?${params}`))
      .items;
  }

  async categories(): Promise<string[]> {
    return (await this.request<{ items: string[] }>("/foods/categories")).items;
  }

  async upload(file: Blob): Promise<ImageUpload> {
    const body = new FormData();
    body.set("file", file, "meal.jpg");
    return this.request("/images", { method: "POST", body });
  }

  async analyse(request: AnalysisRequest): Promise<string> {
    const response = await this.request<{ id: string }>("/analyses", {
      method: "POST",
      body: JSON.stringify(request),
      headers: { "Idempotency-Key": crypto.randomUUID() },
    });
    return response.id;
  }

  job(id: string): Promise<Job> {
    return this.request(`/analyses/${encodeURIComponent(id)}`);
  }

  async cancel(id: string): Promise<void> {
    await this.request(`/analyses/${encodeURIComponent(id)}/cancel`, {
      method: "POST",
    });
  }

  subscribe(
    id: string,
    listener: (event: JobEvent) => void,
    done: () => void,
  ): () => void {
    const controller = new AbortController();
    let sequence = 0;
    let retries = 0;
    const connect = async () => {
      while (!controller.signal.aborted && retries < 4) {
        try {
          let finished = false;
          const response = await fetch(
            `${this.base}/api/v1/analyses/${encodeURIComponent(id)}/events?after=${sequence}`,
            {
              credentials: "include",
              signal: controller.signal,
              headers: { Accept: "text/event-stream" },
            },
          );
          await consumeEvents(
            response,
            (event) => {
              if (event.event === "progress") {
                const payload = JSON.parse(event.data) as JobEvent;
                if (payload.sequence > sequence) {
                  sequence = payload.sequence;
                  listener(payload);
                }
              } else if (event.event === "finished") {
                finished = true;
              }
            },
            controller.signal,
          );
          if (finished) {
            done();
            return;
          }
        } catch {
          if (controller.signal.aborted) return;
        }
        retries += 1;
        await new Promise((resolve) =>
          window.setTimeout(resolve, Math.min(1000 * 2 ** retries, 8000)),
        );
      }
      if (!controller.signal.aborted) done();
    };
    void connect();
    return () => controller.abort();
  }

  async journal(start?: string, end?: string): Promise<JournalEntry[]> {
    const params = new URLSearchParams({ limit: "1000" });
    if (start) params.set("start", start);
    if (end) params.set("end", end);
    return (await this.request<{ items: JournalEntry[] }>(`/journal?${params}`))
      .items;
  }

  saveMeal(id: string, notes = ""): Promise<JournalEntry> {
    return this.request("/journal", {
      method: "POST",
      body: JSON.stringify({
        analysis_id: id,
        notes,
        eaten_at: new Date().toISOString(),
      }),
    });
  }

  editMeal(id: string, patch: JournalPatch): Promise<JournalEntry> {
    return this.request(`/journal/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  }

  deleteMeal(id: string): Promise<void> {
    return this.request(`/journal/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  }

  summary(start: string, end: string): Promise<Summary> {
    return this.request(`/summary?${new URLSearchParams({ start, end })}`);
  }

  preferences(): Promise<Preferences> {
    return this.request("/preferences");
  }

  savePreferences(value: Preferences): Promise<Preferences> {
    return this.request("/preferences", {
      method: "PUT",
      body: JSON.stringify(value),
    });
  }

  async recipes(): Promise<Recipe[]> {
    return (await this.request<{ items: Recipe[] }>("/recipes")).items;
  }

  createRecipe(input: RecipeInput): Promise<Recipe> {
    return this.request("/recipes", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  deleteRecipe(id: string): Promise<void> {
    return this.request(`/recipes/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  }

  chat(message: string, analysisId?: string): Promise<ChatAnswer> {
    return this.request("/chat", {
      method: "POST",
      body: JSON.stringify({ message, analysis_id: analysisId }),
    });
  }

  parseLabel(text: string): Promise<LabelResult> {
    return this.request("/labels/parse", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
  }

  imageLabel(id: string): Promise<LabelResult> {
    return this.request(`/images/${encodeURIComponent(id)}/label`, {
      method: "POST",
    });
  }

  async exportData(format: "json" | "csv"): Promise<Blob> {
    const response = await fetch(
      `${this.base}/api/v1/export?format=${format}`,
      { credentials: "include" },
    );
    if (!response.ok)
      throw new ApiError(response.status, "Could not export your workspace");
    return response.blob();
  }

  erase(): Promise<void> {
    return this.request("/account", { method: "DELETE" });
  }
}
