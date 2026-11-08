import { useCallback, useEffect, useRef, useState } from "react";
import { useWorkspace } from "../state/workspace";
import { errorMessage } from "../lib/export";
import type { AnalysisRequest, AnalysisResult, JobEvent } from "../lib/types";

export function useAnalysis() {
  const { api, toast, refreshCapabilities } = useWorkspace();
  const [jobId, setJobId] = useState<string | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const attempt = useRef(0);
  const activeId = useRef<string | null>(null);

  const run = useCallback(
    async (request: AnalysisRequest) => {
      const current = ++attempt.current;
      setBusy(true);
      setError(null);
      setEvents([]);
      setResult(null);
      setJobId(null);
      try {
        const id = await api.analyse(request);
        if (attempt.current !== current) {
          await api.cancel(id);
          return;
        }
        activeId.current = id;
        setJobId(id);
      } catch (cause) {
        if (attempt.current === current) {
          setError(errorMessage(cause));
          setBusy(false);
        }
      }
    },
    [api],
  );

  useEffect(() => {
    if (!jobId) return;
    let mounted = true;
    let loading = false;
    const finish = async () => {
      if (loading || !mounted) return;
      loading = true;
      try {
        const job = await api.job(jobId);
        if (!mounted) return;
        setEvents(job.events);
        if (job.status === "complete") {
          setResult(job.result);
          setBusy(false);
          activeId.current = null;
          void refreshCapabilities().catch(() => undefined);
        } else if (job.status === "failed" || job.status === "cancelled") {
          setError(
            job.error ??
              (job.status === "cancelled"
                ? "Analysis cancelled"
                : "Analysis failed"),
          );
          setBusy(false);
          activeId.current = null;
        }
      } catch (cause) {
        if (mounted) {
          setError(errorMessage(cause));
          setBusy(false);
        }
      } finally {
        loading = false;
      }
    };
    const unsubscribe = api.subscribe(
      jobId,
      (event) => {
        if (!mounted) return;
        setEvents((current) =>
          current.some((item) => item.sequence === event.sequence)
            ? current
            : [...current, event],
        );
      },
      () => void finish(),
    );
    const polling = window.setInterval(() => {
      if (activeId.current === jobId) void finish();
    }, 4000);
    void finish();
    return () => {
      mounted = false;
      unsubscribe();
      window.clearInterval(polling);
    };
  }, [api, jobId, refreshCapabilities]);

  const cancel = useCallback(async () => {
    attempt.current += 1;
    if (activeId.current) {
      try {
        await api.cancel(activeId.current);
      } catch (cause) {
        toast(errorMessage(cause), "error");
      }
    }
    activeId.current = null;
    setBusy(false);
  }, [api, toast]);

  const reset = useCallback(() => {
    void cancel();
    setJobId(null);
    setResult(null);
    setEvents([]);
    setError(null);
  }, [cancel]);

  useEffect(
    () => () => {
      attempt.current += 1;
      if (activeId.current)
        void api.cancel(activeId.current).catch(() => undefined);
    },
    [api],
  );

  return { jobId, events, result, busy, error, run, cancel, reset, setResult };
}
