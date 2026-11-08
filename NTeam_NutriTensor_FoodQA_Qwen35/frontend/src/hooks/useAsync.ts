import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../lib/export";

export function useAsync<T>(
  loader: () => Promise<T>,
  dependencies: unknown[] = [],
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const sequence = useRef(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const reload = useCallback(async () => {
    const current = ++sequence.current;
    setLoading(true);
    setError(null);
    try {
      const result = await loaderRef.current();
      if (current === sequence.current) setData(result);
    } catch (cause) {
      if (current === sequence.current) setError(errorMessage(cause));
    } finally {
      if (current === sequence.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
    return () => {
      sequence.current += 1;
    };
  }, [...dependencies, reload]);

  return { data, setData, loading, error, reload };
}

export function useDebounce<T>(value: T, delay = 200): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
