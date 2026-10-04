"use client";

import { useEffect, useState } from "react";

import type { DashboardEnvelope } from "@/lib/contracts";
import { deriveGameState } from "@/lib/model/phase";

/** Rechecks the action lock at the deadline even when the API response has not changed. */
export function useGameState(dashboard: DashboardEnvelope | null) {
  const [now, setNow] = useState(() => Date.now());
  const deadline = dashboard?.meta.target_deadline_time ?? dashboard?.data.live?.next_deadline_time;
  useEffect(() => {
    const update = () => setNow(Date.now());
    const first = window.setTimeout(update, 0);
    const remaining = deadline ? Date.parse(deadline) - Date.now() : Number.NaN;
    const timer = Number.isFinite(remaining) && remaining > 0
      ? window.setTimeout(update, Math.min(remaining, 2_147_483_647)) : null;
    window.addEventListener("focus", update);
    document.addEventListener("visibilitychange", update);
    return () => {
      window.clearTimeout(first);
      if (timer != null) window.clearTimeout(timer);
      window.removeEventListener("focus", update);
      document.removeEventListener("visibilitychange", update);
    };
  }, [deadline]);
  return deriveGameState(dashboard, now);
}
