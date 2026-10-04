export const PLAN_HISTORY_KEY = "fpl-ai-plan-history";

export type PlanSnapshot = {
  event: number;
  action: string;
  captain: string;
  netGain: number | null;
  confidenceScore?: number | null;
  confidenceLabel?: string | null;
  modelVersion: string | null;
  recordedAt: string;
};

type StorageLike = Pick<Storage, "getItem" | "setItem">;

function validSnapshot(value: unknown): value is PlanSnapshot {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<PlanSnapshot>;
  return Number.isInteger(item.event)
    && typeof item.action === "string"
    && typeof item.captain === "string"
    && (item.netGain === null || typeof item.netGain === "number")
    && (item.confidenceScore === undefined || item.confidenceScore === null || typeof item.confidenceScore === "number")
    && (item.confidenceLabel === undefined || item.confidenceLabel === null || typeof item.confidenceLabel === "string")
    && (item.modelVersion === null || typeof item.modelVersion === "string")
    && typeof item.recordedAt === "string";
}

function numericDelta(left?: number | null, right?: number | null) {
  if (typeof left !== "number" || typeof right !== "number") return left === right ? 0 : Number.POSITIVE_INFINITY;
  return Math.abs(left - right);
}

function isMeaningfulChange(previous: PlanSnapshot, next: PlanSnapshot) {
  return previous.event !== next.event
    || previous.action !== next.action
    || previous.captain !== next.captain
    || numericDelta(previous.netGain, next.netGain) >= 0.5
    || previous.confidenceLabel !== next.confidenceLabel
    || numericDelta(previous.confidenceScore, next.confidenceScore) >= 0.05;
}

export function readPlanHistory(storage: StorageLike, teamId: string): PlanSnapshot[] {
  try {
    const parsed = JSON.parse(storage.getItem(`${PLAN_HISTORY_KEY}:${teamId}`) ?? "[]") as unknown;
    return Array.isArray(parsed) ? parsed.filter(validSnapshot).slice(0, 6) : [];
  } catch {
    return [];
  }
}

export function recordPlanSnapshot(
  storage: StorageLike,
  snapshot: PlanSnapshot,
  teamId: string,
): PlanSnapshot[] {
  const current = readPlanHistory(storage, teamId);
  if (current[0] && !isMeaningfulChange(current[0], snapshot)) return current;
  const next = [snapshot, ...current].slice(0, 6);
  storage.setItem(`${PLAN_HISTORY_KEY}:${teamId}`, JSON.stringify(next));
  return next;
}
