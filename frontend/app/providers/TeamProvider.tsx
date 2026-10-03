"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { fetchDashboard } from "@/lib/api";
import type { DashboardEnvelope } from "@/lib/contracts";


export const TEAM_STORAGE_KEY = "fpl-ai-team-id";
const REFRESH_INTERVAL_MS = 60_000;


type TeamContextValue = {
  /** False until the browser has checked for a saved Team ID. */
  ready: boolean;
  teamId: string | null;
  dashboard: DashboardEnvelope | null;
  loading: boolean;
  error: string | null;
  lastLoadedAt: number | null;
  connect: (teamId: string) => Promise<void>;
  disconnect: () => void;
  refresh: () => Promise<void>;
};


const TeamContext = createContext<TeamContextValue | null>(null);


function readSavedTeamId(): string | null {
  try {
    return window.localStorage.getItem(TEAM_STORAGE_KEY);
  } catch {
    return null;
  }
}


export function TeamProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [teamId, setTeamId] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<DashboardEnvelope | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastLoadedAt, setLastLoadedAt] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async (value: string, persist: boolean) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchDashboard(value, controller.signal);
      setTeamId(value);
      setDashboard(result);
      setLastLoadedAt(Date.now());
      if (persist) {
        try { window.localStorage.setItem(TEAM_STORAGE_KEY, value); } catch { /* Private mode: keep the session-only connection. */ }
      }
    } catch (caught) {
      if (controller.signal.aborted) return;
      setError(caught instanceof Error ? caught.message : "Could not load FPL team");
      throw caught;
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);

  const connect = useCallback(async (value: string) => {
    await load(value.trim(), true);
  }, [load]);

  const refresh = useCallback(async () => {
    if (!teamId) return;
    try {
      await load(teamId, false);
    } catch {
      // The provider exposes the error while retaining the last good dashboard.
    }
  }, [load, teamId]);

  const disconnect = useCallback(() => {
    abortRef.current?.abort();
    try { window.localStorage.removeItem(TEAM_STORAGE_KEY); } catch { /* ignore */ }
    setTeamId(null);
    setDashboard(null);
    setError(null);
    setLoading(false);
    setLastLoadedAt(null);
  }, []);

  useEffect(() => {
    let active = true;
    const saved = readSavedTeamId();
    queueMicrotask(() => {
      if (!active) return;
      if (saved) {
        setTeamId(saved);
        void load(saved, false).catch(() => undefined);
      }
      setReady(true);
    });
    return () => {
      active = false;
      abortRef.current?.abort();
    };
  }, [load]);

  useEffect(() => {
    if (!teamId) return;
    const interval = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, REFRESH_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [refresh, teamId]);

  return (
    <TeamContext.Provider value={{
      ready,
      teamId,
      dashboard,
      loading,
      error,
      lastLoadedAt,
      connect,
      disconnect,
      refresh,
    }}>
      {children}
    </TeamContext.Provider>
  );
}


export function useTeam(): TeamContextValue {
  const context = useContext(TeamContext);
  if (!context) throw new Error("useTeam must be used within TeamProvider");
  return context;
}
