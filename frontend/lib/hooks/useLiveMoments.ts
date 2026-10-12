import { createContext, useEffect, useRef, useState } from "react";

import type { DashboardLive } from "@/lib/contracts";

export type LiveMoment = {
  /** Increases with every new moment, so effects can react to repeats of the same kind. */
  id: number;
  kind: "goal" | "assist";
  playerId: number;
  playerName: string;
  teamShort: string;
  count: number;
};

const KINDS = { GOAL: "goal", ASSIST: "assist" } as const;

/**
 * Goals and assists by your own active picks, noticed between two refreshes of the
 * live data (every minute while the page is open). The first load only sets the
 * baseline: nothing that already happened is announced again.
 */
export function useLiveMoments(live: DashboardLive | null | undefined): LiveMoment | null {
  const [moment, setMoment] = useState<LiveMoment | null>(null);
  const seen = useRef<{ event: number | null; counts: Map<string, number> }>({ event: null, counts: new Map() });
  const nextId = useRef(1);

  useEffect(() => {
    if (!live) return;
    const memory = seen.current;
    const baseline = memory.event !== live.current_event;
    if (baseline) memory.counts = new Map();
    let latest: LiveMoment | null = null;
    for (const event of live.events ?? []) {
      const kind = KINDS[event.event_type as keyof typeof KINDS];
      if (!kind || !event.active) continue;
      const key = `${event.player_id}:${event.event_type}`;
      const before = memory.counts.get(key) ?? 0;
      memory.counts.set(key, event.count);
      // A goal outranks an assist when both arrive in the same refresh.
      if (!baseline && event.count > before && (!latest || (latest.kind === "assist" && kind === "goal"))) {
        latest = { id: 0, kind, playerId: event.player_id, playerName: event.player_name, teamShort: event.team_short, count: event.count - before };
      }
    }
    memory.event = live.current_event;
    if (latest) setMoment({ ...latest, id: nextId.current++ });
  }, [live]);

  return moment;
}

/** The latest moment, shared from the app shell so the pitch and other views can react to it. */
export const LiveMomentContext = createContext<LiveMoment | null>(null);
