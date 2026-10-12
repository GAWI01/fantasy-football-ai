import { useState, useSyncExternalStore } from "react";

/**
 * Which collapsible sections are open. Only choices the reader made are saved,
 * separately for phone and desktop (a phone starts with most sections closed,
 * a desktop with most open). Nothing is saved per team or per Gameweek.
 */
export const SECTIONS_KEY = "fpl-ai-overview-sections";
const SECTIONS_EVENT = "fpl-ai-overview-sections-change";
const PHONE_QUERY = "(max-width: 767px)";

type Side = "mobile" | "desktop";
type Store = { v: 1; mobile: Record<string, boolean>; desktop: Record<string, boolean> };
const EMPTY: Store = { v: 1, mobile: {}, desktop: {} };

let cached: { raw: string | null; store: Store } = { raw: null, store: EMPTY };

function readStore(): Store {
  if (typeof window === "undefined") return EMPTY;
  let raw: string | null = null;
  try { raw = window.localStorage.getItem(SECTIONS_KEY); } catch { raw = null; }
  if (raw === cached.raw) return cached.store;
  let store = EMPTY;
  try {
    const parsed = raw ? JSON.parse(raw) : null;
    if (parsed && parsed.v === 1) store = { v: 1, mobile: { ...parsed.mobile }, desktop: { ...parsed.desktop } };
  } catch { store = EMPTY; }
  cached = { raw, store };
  return store;
}

function writeStore(side: Side, id: string, open: boolean) {
  const current = readStore();
  const next: Store = { ...current, [side]: { ...current[side], [id]: open } };
  try { window.localStorage.setItem(SECTIONS_KEY, JSON.stringify(next)); } catch { /* private mode: lasts this visit */ }
  window.dispatchEvent(new Event(SECTIONS_EVENT));
}

function subscribeStore(onChange: () => void) {
  if (typeof window === "undefined") return () => undefined;
  const handleStorage = (event: StorageEvent) => { if (event.key === SECTIONS_KEY) onChange(); };
  window.addEventListener("storage", handleStorage);
  window.addEventListener(SECTIONS_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", handleStorage);
    window.removeEventListener(SECTIONS_EVENT, onChange);
  };
}

function subscribePhone(onChange: () => void) {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return () => undefined;
  const query = window.matchMedia(PHONE_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

const readPhone = () => typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(PHONE_QUERY).matches;

// Signals that opened a section by themselves (a new "What changed", a chip to
// play now). Once the reader closes one, it stays closed for this visit, so the
// next live refresh does not reopen it. Kept in memory only.
const dismissedSignals = new Set<string>();

export type SectionDefaults = { mobile: boolean; desktop: boolean };

/**
 * Open state for one section. `signal` is a stable key for something new that
 * should open the section until the reader closes it.
 */
export function useSectionOpen(id: string, defaults: SectionDefaults, signal?: string | null): [boolean, () => void] {
  const store = useSyncExternalStore(subscribeStore, readStore, () => EMPTY);
  const phone = useSyncExternalStore(subscribePhone, readPhone, () => false);
  const [, rerender] = useState(0);
  const side: Side = phone ? "mobile" : "desktop";
  const forced = Boolean(signal) && !dismissedSignals.has(signal as string);
  const open = forced ? true : store[side][id] ?? defaults[side];
  const toggle = () => {
    if (forced && signal) {
      // Closing a section that opened itself is a real choice: it stays closed.
      dismissedSignals.add(signal);
      writeStore(side, id, false);
      rerender((count) => count + 1);
      return;
    }
    writeStore(side, id, !open);
  };
  return [open, toggle];
}

/** Test helper: forget closed signals. */
export function resetSectionSignals() {
  dismissedSignals.clear();
}
