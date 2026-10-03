/** Display formatting helpers. Every helper renders missing data as an em dash, never as zero. */

export const MISSING = "—";

const isNum = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value);

export function fixed(value: number | null | undefined, digits = 1): string {
  return isNum(value) ? value.toFixed(digits) : MISSING;
}

/** Signed value with a true minus sign, e.g. "+2.4" / "−1.0". */
export function signed(value: number | null | undefined, digits = 1): string {
  if (!isNum(value)) return MISSING;
  const rounded = Number(value.toFixed(digits));
  if (rounded === 0) return (0).toFixed(digits);
  return `${rounded > 0 ? "+" : "−"}${Math.abs(rounded).toFixed(digits)}`;
}

export function price(value: number | null | undefined): string {
  return isNum(value) ? `£${value.toFixed(1)}m` : MISSING;
}

export function percent(value: number | null | undefined, { fraction = false, digits = 0 } = {}): string {
  if (!isNum(value)) return MISSING;
  return `${(fraction ? value * 100 : value).toFixed(digits)}%`;
}

export function compact(value: number | null | undefined): string {
  if (!isNum(value)) return MISSING;
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: value >= 1_000_000 ? 2 : 1 }).format(value);
}

export function integer(value: number | null | undefined): string {
  return isNum(value) ? Math.round(value).toLocaleString("en-GB") : MISSING;
}

export function points(value: number | null | undefined, digits = 1): string {
  return isNum(value) ? value.toFixed(digits) : MISSING;
}

export function sentenceCase(value: string | null | undefined): string {
  if (!value) return MISSING;
  const text = value.replaceAll("_", " ").toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function shortTime(iso: string | null | undefined): string {
  if (!iso) return MISSING;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return MISSING;
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return MISSING;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return MISSING;
  return date.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return MISSING;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return MISSING;
  return date.toLocaleString([], { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function relativeAge(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return MISSING;
  const time = Date.parse(iso);
  if (!Number.isFinite(time)) return MISSING;
  const seconds = Math.max(0, Math.round((now - time) / 1000));
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 36) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

export function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}
