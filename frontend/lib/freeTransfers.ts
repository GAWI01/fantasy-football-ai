/**
 * A manager's own free-transfer count. Public FPL data only lets the backend
 * estimate it, so the manager can correct it. The value applies to one team
 * and one target Gameweek and is dropped once the next Gameweek is planned.
 */
export const FREE_TRANSFERS_KEY = "fpl-ai-free-transfers";
export const MAX_FREE_TRANSFERS = 5;

export type FreeTransferOverride = {
  teamId: string;
  /** Target Gameweek the value was set for; null until the plan reports it. */
  event: number | null;
  value: number;
};

export function isValidFreeTransfers(value: unknown): value is number {
  return Number.isInteger(value) && (value as number) >= 0 && (value as number) <= MAX_FREE_TRANSFERS;
}

export function parseFreeTransferOverride(raw: string | null): FreeTransferOverride | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<FreeTransferOverride>;
    if (typeof parsed.teamId !== "string" || !isValidFreeTransfers(parsed.value)) return null;
    const event = Number.isInteger(parsed.event) ? parsed.event as number : null;
    return { teamId: parsed.teamId, event, value: parsed.value };
  } catch {
    return null;
  }
}

export function readFreeTransferOverride(teamId: string): FreeTransferOverride | null {
  try {
    const stored = parseFreeTransferOverride(window.localStorage.getItem(FREE_TRANSFERS_KEY));
    return stored?.teamId === teamId ? stored : null;
  } catch {
    return null;
  }
}

export function writeFreeTransferOverride(override: FreeTransferOverride | null) {
  try {
    if (override) window.localStorage.setItem(FREE_TRANSFERS_KEY, JSON.stringify(override));
    else window.localStorage.removeItem(FREE_TRANSFERS_KEY);
  } catch {
    // Private mode: the override lasts for this page only.
  }
}

/** An override set for an earlier Gameweek no longer applies. */
export function overrideApplies(override: FreeTransferOverride | null, targetEvent: number | null | undefined): boolean {
  if (!override) return false;
  return override.event == null || targetEvent == null || override.event === targetEvent;
}
