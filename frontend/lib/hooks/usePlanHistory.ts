"use client";

import { useEffect, useState } from "react";

import { readPlanHistory, recordPlanSnapshot, type PlanSnapshot } from "@/lib/planHistory";

export type PlanChange = {
  previous: PlanSnapshot;
  current: PlanSnapshot;
  reasons: string[];
};

export function describePlanChange(previous: PlanSnapshot, current: PlanSnapshot): string[] {
  return [
    previous.action !== current.action ? `Transfer call changed from “${previous.action}”` : null,
    previous.captain !== current.captain ? `Captain changed from ${previous.captain}` : null,
    typeof previous.netGain === "number" && typeof current.netGain === "number" && Math.abs(previous.netGain - current.netGain) >= 0.5
      ? `Expected edge moved by ${(current.netGain - previous.netGain) > 0 ? "+" : "−"}${Math.abs(current.netGain - previous.netGain).toFixed(1)} pts`
      : null,
    previous.confidenceLabel !== current.confidenceLabel
      || (typeof previous.confidenceScore === "number" && typeof current.confidenceScore === "number" && Math.abs(previous.confidenceScore - current.confidenceScore) >= 0.05)
      ? "Model confidence changed"
      : null,
  ].filter((reason): reason is string => Boolean(reason));
}

/** Records meaningful plan changes in this browser and reports the latest one for the same Gameweek. */
export function usePlanHistory(snapshot: PlanSnapshot | null) {
  const [history, setHistory] = useState<PlanSnapshot[]>([]);
  const key = snapshot ? JSON.stringify({ ...snapshot, recordedAt: undefined }) : null;

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      try {
        setHistory(snapshot ? recordPlanSnapshot(window.localStorage, snapshot) : readPlanHistory(window.localStorage));
      } catch {
        setHistory([]);
      }
    });
    return () => { cancelled = true; };
    // `key` captures every meaningful field of the snapshot.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const current = history[0];
  const previous = history[1] && current && history[1].event === current.event ? history[1] : null;
  const change: PlanChange | null = previous && current ? { previous, current, reasons: describePlanChange(previous, current) } : null;
  return { history, change: change && change.reasons.length ? change : null };
}
