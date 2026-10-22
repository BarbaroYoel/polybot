import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiError } from "./api/client";
import { toApiError } from "./api/client";

export type AsyncStatus = "loading" | "ready" | "error";

export interface AsyncState<T> {
  status: AsyncStatus;
  data: T | null;
  error: ApiError | null;
  reload: () => void;
}

interface LoadedState<T> {
  /** Version plus dependencies of the load this state belongs to. */
  signature: string;
  status: AsyncStatus;
  data: T | null;
  error: ApiError | null;
}

/**
 * Minimal async loader for the screens that read from the API: it exposes exactly the three
 * states the UI must show (loading, empty, error) plus an explicit `reload`.
 *
 * A change in `deps` (or a `reload`) makes the previous data unavailable immediately — even before
 * the effect runs — so a previous language's list can never be painted under a new heading.
 *
 * `deps` must be JSON-serializable values (ids, strings, numbers): they are compared through a
 * signature, the same way React compares dependency arrays.
 */
export function useAsync<T>(load: () => Promise<T>, deps: readonly unknown[] = []): AsyncState<T> {
  const [version, setVersion] = useState(0);
  const signature = `${version}:${JSON.stringify(deps)}`;

  const [state, setState] = useState<LoadedState<T>>({
    signature,
    status: "loading",
    data: null,
    error: null,
  });

  // `load` is usually an inline closure: keep the newest one so a reload never runs stale code,
  // without forcing every caller to memoize it.
  const loadRef = useRef(load);
  useEffect(() => {
    loadRef.current = load;
  });

  const reload = useCallback(() => setVersion((current) => current + 1), []);

  useEffect(() => {
    let current = true;

    loadRef.current().then(
      (data) => {
        if (current) setState({ signature, status: "ready", data, error: null });
      },
      (error: unknown) => {
        if (current) setState({ signature, status: "error", data: null, error: toApiError(error) });
      },
    );

    return () => {
      current = false;
    };
  }, [signature]);

  // The effect runs after the paint: until it answers, the state of the previous load is not shown.
  const stale = state.signature !== signature;

  return {
    status: stale ? "loading" : state.status,
    data: stale ? null : state.data,
    error: stale ? null : state.error,
    reload,
  };
}
