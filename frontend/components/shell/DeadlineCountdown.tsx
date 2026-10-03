"use client";

import { Clock3 } from "lucide-react";
import { useEffect, useState } from "react";


export function formatDeadlineRemaining(deadline: string, now = Date.now()) {
  const target = Date.parse(deadline);
  if (!Number.isFinite(target)) return "Deadline unavailable";
  const seconds = Math.floor((target - now) / 1000);
  if (seconds <= 0) return "Deadline passed";
  const days = Math.floor(seconds / 86_400);
  const hours = Math.floor((seconds % 86_400) / 3_600);
  const minutes = Math.floor((seconds % 3_600) / 60);
  const remainingSeconds = seconds % 60;
  if (days > 0) return `${days}d ${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${remainingSeconds}s`;
  return `${remainingSeconds}s`;
}


/** Urgency drives colour only; the text always carries the remaining time. */
export function deadlineUrgency(deadline: string, now = Date.now()): "calm" | "soon" | "urgent" | "passed" {
  const target = Date.parse(deadline);
  if (!Number.isFinite(target)) return "calm";
  const hours = (target - now) / 3_600_000;
  if (hours <= 0) return "passed";
  if (hours < 3) return "urgent";
  if (hours < 24) return "soon";
  return "calm";
}


export function DeadlineCountdown({
  deadline,
  event,
  now,
  compact = false,
}: {
  deadline?: string | null;
  event?: number | null;
  now?: number;
  compact?: boolean;
}) {
  const [clock, setClock] = useState<number | null>(now ?? null);

  useEffect(() => {
    if (!deadline || now !== undefined) return;
    const initial = window.setTimeout(() => setClock(Date.now()), 0);
    const interval = window.setInterval(() => setClock(Date.now()), 1_000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(interval);
    };
  }, [deadline, now]);

  if (!deadline) return null;
  const urgency = clock == null ? "calm" : deadlineUrgency(deadline, clock);
  return (
    <span className={`deadline deadline-${urgency}${compact ? " deadline-compact" : ""}`}>
      <Clock3 size={14} aria-hidden="true" />
      <span>
        <small>{event ? `GW${event} deadline` : "Next deadline"}</small>
        <time role="timer" aria-live="off" dateTime={deadline}>{clock == null ? "Calculating…" : formatDeadlineRemaining(deadline, clock)}</time>
      </span>
    </span>
  );
}
