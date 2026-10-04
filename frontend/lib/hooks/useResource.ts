"use client";

import { useCallback, useEffect, useState } from "react";

type Entry<T> = { data?: T; error?: string; at: number; promise?: Promise<T> };

const cache = new Map<string, Entry<unknown>>();
const refreshers = new Set<() => void>();
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
    let timer: number | undefined;
    const schedule = (at: number) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        if (active && document.visibilityState === "visible") setNonce((value) => value + 1);
      }, Math.max(1, at + ttl - Date.now()));
    };
    const refresh = () => setNonce((value) => value + 1);
    const refreshExpired = () => {
      if (document.visibilityState === "visible" && Date.now() - (cache.get(key)?.at ?? 0) >= ttl) refresh();
    };
    refreshers.add(refresh);
    window.addEventListener("focus", refreshExpired);
    document.addEventListener("visibilitychange", refreshExpired);
    const cleanup = () => {
      active = false;
      window.clearTimeout(timer);
      refreshers.delete(refresh);
      window.removeEventListener("focus", refreshExpired);
      document.removeEventListener("visibilitychange", refreshExpired);
    };
    const entry = cache.get(key) as Entry<T> | undefined;
    const fresh = entry?.data !== undefined && Date.now() - entry.at < ttl && nonce === 0;
    if (fresh) {
      queueMicrotask(() => {
        if (active) setState({ key, data: entry!.data ?? null, error: entry!.error ?? null, loading: false });
      });
      schedule(entry.at);
      return cleanup;
    }
    const controller = new AbortController();
    const promise = entry?.promise ?? fetcher(controller.signal);
    cache.set(key, { ...entry, at: entry?.at ?? 0, promise });
    queueMicrotask(() => {
      if (active) setState((current) => ({ key, data: current.key === key ? current.data : null, error: null, loading: true }));
    });
    promise
      .then((data) => {
        cache.set(key, { data, at: Date.now() });
        if (active) {
          setState({ key, data, error: null, loading: false });
          schedule(Date.now());
        }
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted && !active) return;
        const message = caught instanceof Error ? caught.message : "Request failed";
        cache.set(key, { ...(cache.get(key) as Entry<T>), at: Date.now(), error: message, promise: undefined });
        if (active) {
          setState((current) => ({ key, data: current.key === key ? current.data : null, error: message, loading: false }));
          schedule(Date.now());
        }
      });
    return cleanup;
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

/** The shared refresh control also refreshes currently mounted page resources. */
export function refreshResources() {
  for (const entry of cache.values()) entry.at = 0;
  for (const refresh of refreshers) refresh();
}

/** Test helper. */
export function clearResourceCache() {
  cache.clear();
}
