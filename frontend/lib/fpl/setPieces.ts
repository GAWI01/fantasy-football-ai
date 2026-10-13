import type { PlayerSummary } from "@/lib/contracts";

const ORDINAL = ["", "1st", "2nd", "3rd", "4th", "5th"];

/** The set pieces a player takes, as FPL lists them for his club, first choices first. */
export function setPieceRoles(player: Pick<PlayerSummary, "penalties_order" | "direct_freekicks_order" | "corners_order">): string[] {
  const roles: Array<[string, number | null | undefined]> = [
    ["Penalties", player.penalties_order],
    ["Free kicks", player.direct_freekicks_order],
    ["Corners", player.corners_order],
  ];
  return roles
    .filter(([, order]) => order != null && order >= 1 && order <= 3)
    .sort((left, right) => (left[1] ?? 9) - (right[1] ?? 9))
    .map(([label, order]) => (order === 1 ? label : `${label} (${ORDINAL[order ?? 0] ?? order})`));
}

/** A short tag for lists: only first-choice penalties or free kicks. */
export function setPieceTag(player: Pick<PlayerSummary, "penalties_order" | "direct_freekicks_order" | "corners_order">): string | null {
  if (player.penalties_order === 1) return "Pens";
  if (player.direct_freekicks_order === 1) return "FKs";
  return null;
}
