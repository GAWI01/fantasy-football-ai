import { useSyncExternalStore } from "react";

/**
 * Whether every number carries its source label (FPL data, Model, Derived).
 * Off by default to keep screens calm: Live and Cached still show, because they
 * say something about the data right now, and every forecast keeps its xP unit.
 */
export const DATA_LABELS_KEY = "fpl-ai-data-labels";
const DATA_LABELS_EVENT = "fpl-ai-data-labels-change";

// When storage is blocked (private mode) the choice lasts this visit.
let session: boolean | null = null;

export function readDataLabels(): boolean {
  if (typeof window === "undefined") return false;
  try { return window.localStorage.getItem(DATA_LABELS_KEY) === "on"; } catch { return session ?? false; }
}

export function writeDataLabels(show: boolean) {
  if (typeof window === "undefined") return;
  try {
    if (show) window.localStorage.setItem(DATA_LABELS_KEY, "on");
    else window.localStorage.removeItem(DATA_LABELS_KEY);
  } catch { session = show; }
  window.dispatchEvent(new Event(DATA_LABELS_EVENT));
}

function subscribeDataLabels(onChange: () => void) {
  if (typeof window === "undefined") return () => undefined;
  const handleStorage = (event: StorageEvent) => { if (event.key === DATA_LABELS_KEY) onChange(); };
  window.addEventListener("storage", handleStorage);
  window.addEventListener(DATA_LABELS_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", handleStorage);
    window.removeEventListener(DATA_LABELS_EVENT, onChange);
  };
}

export function useDataLabels(): boolean {
  return useSyncExternalStore(subscribeDataLabels, readDataLabels, () => false);
}
