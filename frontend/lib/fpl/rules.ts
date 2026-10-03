/**
 * FPL squad rules used by local simulations. Official FPL data uses "GK" while
 * model artifacts use "GKP"; everything in the UI is normalised to `Position`.
 */

export type Position = "GKP" | "DEF" | "MID" | "FWD";

export const POSITIONS: readonly Position[] = ["GKP", "DEF", "MID", "FWD"];

export const POSITION_LABEL: Record<Position, string> = {
  GKP: "Goalkeeper",
  DEF: "Defender",
  MID: "Midfielder",
  FWD: "Forward",
};

export function normalizePosition(value: unknown): Position | null {
  const text = String(value ?? "").trim().toUpperCase();
  if (text === "GK" || text === "GKP" || text === "1") return "GKP";
  if (text === "DEF" || text === "D" || text === "2") return "DEF";
  if (text === "MID" || text === "M" || text === "3") return "MID";
  if (text === "FWD" || text === "FW" || text === "F" || text === "4") return "FWD";
  return null;
}

/** Valid FPL starting XI shape limits. */
export const XI_LIMITS: Record<Position, readonly [number, number]> = {
  GKP: [1, 1],
  DEF: [3, 5],
  MID: [2, 5],
  FWD: [1, 3],
};

export type XIMember = { position: Position | string | null };

export function formationCounts(players: readonly XIMember[]): Record<Position, number> {
  const counts: Record<Position, number> = { GKP: 0, DEF: 0, MID: 0, FWD: 0 };
  for (const player of players) {
    const position = normalizePosition(player.position);
    if (position) counts[position] += 1;
  }
  return counts;
}

export function formationLabel(players: readonly XIMember[]): string {
  const counts = formationCounts(players);
  return `${counts.DEF}-${counts.MID}-${counts.FWD}`;
}

/**
 * Validates an XI against FPL formation rules. Club limits apply to the
 * 15-player squad, not the XI, so they are deliberately not checked here.
 */
export function validateStartingXI(players: readonly XIMember[]): { valid: boolean; reason: string | null } {
  if (players.length !== 11) return { valid: false, reason: "A starting XI needs exactly 11 players." };
  if (players.some((player) => normalizePosition(player.position) == null)) {
    return { valid: false, reason: "A player has an unknown position." };
  }
  const counts = formationCounts(players);
  for (const position of POSITIONS) {
    const [min, max] = XI_LIMITS[position];
    if (counts[position] < min || counts[position] > max) {
      if (position === "GKP") return { valid: false, reason: "The XI must contain exactly one goalkeeper." };
      const label = POSITION_LABEL[position].toLowerCase();
      return {
        valid: false,
        reason: counts[position] < min
          ? `The XI needs at least ${min} ${label}s.`
          : `The XI can have at most ${max} ${label}s.`,
      };
    }
  }
  return { valid: true, reason: null };
}

export function isValidStartingXI(players: readonly XIMember[]): boolean {
  return validateStartingXI(players).valid;
}

/** Each transfer beyond the free allowance costs four points. */
export const HIT_COST = 4;

export function hitCost(transfers: number, freeTransfers: number | null | undefined): number | null {
  if (typeof freeTransfers !== "number") return null;
  return Math.max(0, transfers - freeTransfers) * HIT_COST;
}

export function availabilityFromStatus(status: string | null | undefined, chance?: number | null): {
  label: string;
  tone: "ok" | "warn" | "risk" | "unknown";
} {
  const code = String(status ?? "").toLowerCase();
  if (code === "a") return { label: "Available", tone: "ok" };
  if (code === "d") return { label: typeof chance === "number" ? `${chance}% chance` : "Doubtful", tone: typeof chance === "number" && chance >= 75 ? "warn" : "risk" };
  if (code === "i") return { label: "Injured", tone: "risk" };
  if (code === "s") return { label: "Suspended", tone: "risk" };
  if (code === "u") return { label: "Unavailable", tone: "risk" };
  if (code === "n") return { label: "Not in squad", tone: "risk" };
  return { label: "Unknown", tone: "unknown" };
}
