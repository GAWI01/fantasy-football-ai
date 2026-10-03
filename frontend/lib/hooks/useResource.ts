"use client";

import { useCallback, useEffect, useState } from "react";

type Entry<T> = { data?: T; error?: string; at: number; promise?: Promise<T> };

const cache = new Map<string, Entry<unknown>>();
const DEFAULT_TTL_MS = 60_000;

export type Resource<T> = {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
};

/** Shares one in-flight request and a short-lived result per key across components. */
export function useResource<T>(key: string | null, fetcher: (signal: AbortSignal) => Promise<T>, ttl = DEFAULT_TTL_MS): Resource<T> {
  const cached = key ? (cache.get(key) as Entry<T> | undefined) : undefined;
  const [state, setState] = useState<{ key: string | null; data: T | null; error: string | null; loading: boolean }>(() => ({
    key,
    data: cached?.data ?? null,
    error: cached?.error ?? null,
    loading: Boolean(key) && !cached?.data,
  }));
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!key) return;
    let active = true;
    const entry = cache.get(key) as Entry<T> | undefined;
    const fresh = entry?.data !== undefined && Date.now() - entry.at < ttl && nonce === 0;
    if (fresh) {
      queueMicrotask(() => {
        if (active) setState({ key, data: entry!.data ?? null, error: null, loading: false });
      });
      return () => { active = false; };
    }
    const controller = new AbortController();
    const promise = entry?.promise && nonce === 0 ? entry.promise : fetcher(controller.signal);
    cache.set(key, { ...entry, at: entry?.at ?? 0, promise });
    queueMicrotask(() => {
      if (active) setState((current) => ({ key, data: current.key === key ? current.data : null, error: null, loading: true }));
    });
    promise
      .then((data) => {
        cache.set(key, { data, at: Date.now() });
        if (active) setState({ key, data, error: null, loading: false });
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted && !active) return;
        const message = caught instanceof Error ? caught.message : "Request failed";
        cache.set(key, { ...(cache.get(key) as Entry<T>), error: message, promise: undefined });
        if (active) setState((current) => ({ key, data: current.key === key ? current.data : null, error: message, loading: false }));
      });
    return () => {
      active = false;
    };
    // The fetcher is intentionally keyed by `key`; callers pass inline functions.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, nonce, ttl]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);
  const matches = state.key === key;
  return {
    data: matches ? state.data : null,
    error: matches ? state.error : null,
    loading: matches ? state.loading : Boolean(key),
    reload,
  };
}

/** Test helper. */
export function clearResourceCache() {
  cache.clear();
}
