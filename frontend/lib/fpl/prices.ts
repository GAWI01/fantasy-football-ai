import type { PriceChangePlayer } from "@/lib/contracts";

export type PriceStatus = "very-likely-rise" | "likely-rise" | "unlikely" | "likely-drop" | "very-likely-drop" | "locked";

/** FPL's own wording for its likelihood scale (-5 … +5), as its price page shows it. */
export function statusFromLikelihood(likelihood: number | null | undefined): PriceStatus {
  if (likelihood == null) return "unlikely";
  if (likelihood >= 5) return "very-likely-rise";
  if (likelihood >= 4) return "likely-rise";
  if (likelihood <= -5) return "very-likely-drop";
  if (likelihood <= -4) return "likely-drop";
  return "unlikely";
}

export const PRICE_STATUS_LABEL: Record<PriceStatus, string> = {
  "very-likely-rise": "Very likely to rise",
  "likely-rise": "Likely to rise",
  unlikely: "Unlikely to change",
  "likely-drop": "Likely to drop",
  "very-likely-drop": "Very likely to drop",
  locked: "Locked",
};

/** Status for the next change window (offset 0); a locked player cannot change. */
export function nextStatus(player: Pick<PriceChangePlayer, "projections" | "locked_until">): PriceStatus {
  if (player.locked_until) return "locked";
  const next = player.projections.find((item) => item.offset === 0) ?? player.projections[0];
  return statusFromLikelihood(next?.likelihood);
}

export const isRise = (status: PriceStatus) => status === "very-likely-rise" || status === "likely-rise";
export const isDrop = (status: PriceStatus) => status === "very-likely-drop" || status === "likely-drop";

/** "01:55:47" until the moment, or null once it has passed. */
export function countdown(target: string | null | undefined, now: number): string | null {
  if (!target) return null;
  const ms = Date.parse(target) - now;
  if (!Number.isFinite(ms) || ms <= 0) return null;
  const total = Math.floor(ms / 1000);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(Math.floor(total / 3600))}:${pad(Math.floor((total % 3600) / 60))}:${pad(total % 60)}`;
}
