import { useEffect, useRef } from "react";

interface PollOptions<T> {
  fetcher: () => Promise<T>;
  intervalMs: number;
  isDone: (data: T) => boolean;
  onDone?: (data: T) => void;
  onError?: (error: unknown) => void;
  enabled?: boolean;
}

/**
 * Background polling that stops once `isDone` returns true.
 * Re-runs the fetch immediately each time a value arrives.
 */
export function usePolling<T>({
  fetcher,
  intervalMs,
  isDone,
  onDone,
  onError,
  enabled = true,
}: PollOptions<T>) {
  const stopRef = useRef(false);
  const fetcherRef = useRef(fetcher);
  const isDoneRef = useRef(isDone);
  const onDoneRef = useRef(onDone);
  const onErrorRef = useRef(onError);

  fetcherRef.current = fetcher;
  isDoneRef.current = isDone;
  onDoneRef.current = onDone;
  onErrorRef.current = onError;

  useEffect(() => {
    if (!enabled) return;
    stopRef.current = false;

    let cancelled = false;
    let timeoutId: number | undefined;

    const tick = async () => {
      if (cancelled || stopRef.current) return;
      try {
        const data = await fetcherRef.current();
        if (cancelled || stopRef.current) return;
        if (isDoneRef.current(data)) {
          onDoneRef.current?.(data);
          return;
        }
      } catch (error) {
        if (cancelled || stopRef.current) return;
        onErrorRef.current?.(error);
      }
      timeoutId = window.setTimeout(tick, intervalMs);
    };

    tick();

    return () => {
      cancelled = true;
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
    };
  }, [intervalMs, enabled]);

  return {
    stop: () => {
      stopRef.current = true;
    },
  };
}