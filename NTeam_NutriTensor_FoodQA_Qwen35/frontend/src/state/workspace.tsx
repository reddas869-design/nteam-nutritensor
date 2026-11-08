import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { LiveApi } from "../lib/api";
import { DemoApi } from "../lib/demo";
import { defaultPreferences } from "../lib/defaults";
import { errorMessage } from "../lib/export";
import type {
  Capabilities,
  Page,
  Preferences,
  WorkspaceApi,
} from "../lib/types";

interface Toast {
  id: string;
  message: string;
  tone: "success" | "error" | "info";
}

interface Workspace {
  api: WorkspaceApi;
  page: Page;
  setPage(page: Page): void;
  preferences: Preferences;
  savePreferences(preferences: Preferences): Promise<void>;
  capabilities: Capabilities | null;
  refreshCapabilities(): Promise<void>;
  connected: boolean;
  serverAvailable: boolean;
  connect(base: string, password: string, username?: string): Promise<void>;
  disconnect(): Promise<void>;
  toast(message: string, tone?: Toast["tone"]): void;
  toasts: Toast[];
  dismissToast(id: string): void;
  revision: number;
  changed(): void;
}

const Context = createContext<Workspace | null>(null);
const demo = new DemoApi();

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [api, setApi] = useState<WorkspaceApi>(demo);
  const [page, setPage] = useState<Page>("capture");
  const [preferences, setPreferences] = useState(defaultPreferences);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [connected, setConnected] = useState(false);
  const [serverAvailable, setServerAvailable] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [revision, setRevision] = useState(0);

  const toast = useCallback((message: string, tone: Toast["tone"] = "info") => {
    const id = crypto.randomUUID();
    setToasts((current) => [...current.slice(-3), { id, message, tone }]);
    window.setTimeout(
      () => setToasts((current) => current.filter((item) => item.id !== id)),
      tone === "error" ? 9000 : 5000,
    );
  }, []);

  const refreshCapabilities = useCallback(async () => {
    setCapabilities(await api.capabilities());
  }, [api]);

  useEffect(() => {
    let active = true;
    Promise.all([api.preferences(), api.capabilities()])
      .then(([settings, capability]) => {
        if (active) {
          setPreferences(settings);
          setCapabilities(capability);
        }
      })
      .catch((error) => toast(errorMessage(error), "error"));
    return () => {
      active = false;
    };
  }, [api, toast]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 1500);
    fetch("/api/v1/health", { signal: controller.signal })
      .then(async (response) => {
        if (response.ok) {
          const payload = await response.json();
          setServerAvailable(payload.status === "ok");
          if (
            payload.status === "ok" &&
            payload.mode === "live" &&
            !controller.signal.aborted
          ) {
            const candidate = new LiveApi();
            const session = await candidate.session().catch(() => null);
            if (session?.authenticated && !controller.signal.aborted) {
              setApi(candidate);
              setConnected(true);
            }
          }
        }
      })
      .catch(() => undefined)
      .finally(() => window.clearTimeout(timer));
    return () => controller.abort();
  }, []);

  const connect = useCallback(
    async (base: string, password: string, username = "owner") => {
      const candidate = new LiveApi(base);
      await candidate.health();
      await candidate.login(password, username);
      const settings = await candidate.preferences();
      const capability = await candidate.capabilities();
      setPreferences(settings);
      setCapabilities(capability);
      setApi(candidate);
      setConnected(true);
      setPage("capture");
      setRevision((value) => value + 1);
      toast(
        candidate.mode === "live"
          ? "Connected to our local workspace"
          : "Connected to the backend demo",
        "success",
      );
    },
    [toast],
  );

  const disconnect = useCallback(async () => {
    await api.logout();
    setApi(demo);
    setConnected(false);
    setPage("capture");
    setRevision((value) => value + 1);
    toast("Returned to the browser demo");
  }, [api, toast]);

  const savePreferences = useCallback(
    async (value: Preferences) => {
      setPreferences(await api.savePreferences(value));
      toast("Preferences saved", "success");
    },
    [api, toast],
  );

  const value = useMemo<Workspace>(
    () => ({
      api,
      page,
      setPage,
      preferences,
      savePreferences,
      capabilities,
      refreshCapabilities,
      connected,
      serverAvailable,
      connect,
      disconnect,
      toast,
      toasts,
      dismissToast: (id) =>
        setToasts((current) => current.filter((item) => item.id !== id)),
      revision,
      changed: () => setRevision((current) => current + 1),
    }),
    [
      api,
      page,
      preferences,
      capabilities,
      refreshCapabilities,
      connected,
      serverAvailable,
      connect,
      disconnect,
      toast,
      toasts,
      revision,
      savePreferences,
    ],
  );

  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useWorkspace(): Workspace {
  const value = useContext(Context);
  if (!value) throw new Error("WorkspaceProvider is missing");
  return value;
}
