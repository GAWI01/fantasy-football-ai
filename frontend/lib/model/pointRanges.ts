import { POINT_RANGE_ROWS } from "@/lib/model/pointRanges.data";

export type PointRange = { low: number; high: number; median: number; hauls: number; blanks: number };

type Row = (typeof POINT_RANGE_ROWS)[number];
const QUANTILES = ["p10", "p50", "p90", "haul", "blank"] as const;

/**
 * What players with this expected score actually scored in an out-of-sample
 * backtest: usually between `low` and `high` (10th–90th percentile), with the
 * chance of a haul (10+) and a blank (2 or fewer). Mirrors backend/point_ranges.py.
 */
export function pointRange(expected: number | null | undefined): PointRange | null {
  if (expected == null || !Number.isFinite(expected)) return null;
  const rows = POINT_RANGE_ROWS as readonly Row[];
  const value = Math.max(0, expected);
  let row: Record<(typeof QUANTILES)[number], number>;
  if (value <= rows[0].mean) {
    row = rows[0];
  } else if (value >= rows[rows.length - 1].mean) {
    const top = rows[rows.length - 1];
    const scale = value / top.mean;
    row = { p10: top.p10 * scale, p50: top.p50 * scale, p90: top.p90 * scale, haul: top.haul, blank: top.blank };
  } else {
    const upper = rows.findIndex((item) => item.mean >= value);
    const low = rows[upper - 1];
    const high = rows[upper];
    const weight = (value - low.mean) / (high.mean - low.mean);
    row = Object.fromEntries(QUANTILES.map((key) => [key, low[key] + weight * (high[key] - low[key])])) as typeof row;
  }
  return { low: Math.round(row.p10), high: Math.round(row.p90), median: Math.round(row.p50), hauls: row.haul, blanks: row.blank };
}

/** "2–10" for display. */
export function rangeLabel(expected: number | null | undefined, multiplier = 1): string | null {
  const range = pointRange(expected);
  if (!range) return null;
  return `${range.low * multiplier}–${range.high * multiplier}`;
}
