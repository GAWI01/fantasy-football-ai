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
import { overrideApplies, readFreeTransferOverride, writeFreeTransferOverride, type FreeTransferOverride } from "@/lib/freeTransfers";


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
  /** Set the manager's own free-transfer count for the planned Gameweek, or null to use the estimate. */
  setFreeTransfers: (value: number | null) => Promise<void>;
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
  const overridesRef = useRef(new Map<string, FreeTransferOverride | null>());

  const load = useCallback(async (value: string, persist: boolean) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const override = overridesRef.current.has(value) ? overridesRef.current.get(value) : readFreeTransferOverride(value);
      overridesRef.current.set(value, override ?? null);
      let result = await fetchDashboard(value, controller.signal, override?.value);
      if (controller.signal.aborted) return;
      const targetEvent = result.meta.prediction_event ?? result.meta.next_event ?? result.data.team.prediction_event;
      if (override && !overrideApplies(override, targetEvent)) {
        // The count was set for an earlier Gameweek: fall back to the estimate.
        writeFreeTransferOverride(null);
        overridesRef.current.set(value, null);
        result = await fetchDashboard(value, controller.signal);
      } else if (override?.event == null && override && targetEvent != null) {
        const bound = { ...override, event: targetEvent };
        overridesRef.current.set(value, bound);
        writeFreeTransferOverride(bound);
      }
      if (controller.signal.aborted) return;
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

  const setFreeTransfers = useCallback(async (value: number | null) => {
    if (!teamId) return;
    const override = value == null ? null : {
      teamId,
      event: dashboard?.meta.prediction_event ?? dashboard?.meta.next_event ?? dashboard?.data.team.prediction_event ?? null,
      value,
    };
    overridesRef.current.set(teamId, override);
    writeFreeTransferOverride(override);
    try {
      await load(teamId, false);
    } catch {
      // The provider exposes the error while retaining the last good dashboard.
    }
  }, [dashboard, load, teamId]);

  const disconnect = useCallback(() => {
    abortRef.current?.abort();
    try { window.localStorage.removeItem(TEAM_STORAGE_KEY); } catch { /* ignore */ }
    writeFreeTransferOverride(null);
    overridesRef.current.clear();
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
      setFreeTransfers,
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
