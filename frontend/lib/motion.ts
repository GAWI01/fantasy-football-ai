import { useEffect, useRef, useState, useSyncExternalStore } from "react";

/**
 * How much the app moves. "auto" is Lively, unless the phone or computer asks for
 * reduced motion; that system setting always wins, whatever is chosen here.
 *
 * - calm: motion only at real moments (a goal, new points, a new page).
 * - lively: also ambient life (the background drifts, live dots pulse, glass glints).
 * - max: also pointer glow on cards and breathing players on the live pitch.
 * - off: nothing moves; the background is a still frame.
 */
export const MOTION_KEY = "fpl-ai-motion";
const MOTION_EVENT = "fpl-ai-motion-change";

export type MotionPreference = "auto" | "calm" | "lively" | "max" | "off";
export type MotionLevel = "off" | "calm" | "lively" | "max";

export const DEFAULT_MOTION: MotionPreference = "auto";

export const motionOptions: Array<{ id: MotionPreference; label: string; description: string }> = [
  { id: "auto", label: "Auto", description: "Lively, or still when your device asks for less motion." },
  { id: "calm", label: "Calm", description: "Moves only when something happens: a goal, new points, a new page." },
  { id: "lively", label: "Lively", description: "Also a drifting background, pulsing live dots and glinting glass." },
  { id: "max", label: "Max", description: "Also a glow that follows your pointer and players that breathe on the live pitch." },
  { id: "off", label: "Off", description: "Nothing moves. The background is a still image." },
];

export function readMotionPreference(): MotionPreference {
  if (typeof window === "undefined") return DEFAULT_MOTION;
  let stored: string | null = null;
  try { stored = window.localStorage.getItem(MOTION_KEY); } catch { stored = null; }
  return motionOptions.some((option) => option.id === stored) ? stored as MotionPreference : DEFAULT_MOTION;
}

export function writeMotionPreference(preference: MotionPreference) {
  if (typeof window === "undefined") return;
  try { window.localStorage.setItem(MOTION_KEY, preference); } catch { /* private mode: the choice lasts this visit */ }
  window.dispatchEvent(new Event(MOTION_EVENT));
}

function subscribeMotion(onChange: () => void) {
  if (typeof window === "undefined") return () => undefined;
  const handleStorage = (event: StorageEvent) => { if (event.key === MOTION_KEY) onChange(); };
  window.addEventListener("storage", handleStorage);
  window.addEventListener(MOTION_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", handleStorage);
    window.removeEventListener(MOTION_EVENT, onChange);
  };
}

export function useMotionPreference(): MotionPreference {
  return useSyncExternalStore(subscribeMotion, readMotionPreference, () => DEFAULT_MOTION);
}

const REDUCE_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeReduced(onChange: () => void) {
  if (typeof window === "undefined" || !window.matchMedia) return () => undefined;
  const query = window.matchMedia(REDUCE_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

function readReduced() {
  return typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(REDUCE_QUERY).matches;
}

export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribeReduced, readReduced, () => false);
}

export function resolveMotion(preference: MotionPreference, systemReduced: boolean): MotionLevel {
  if (systemReduced) return "off";
  return preference === "auto" ? "lively" : preference;
}

export function useMotionLevel(): MotionLevel {
  return resolveMotion(useMotionPreference(), usePrefersReducedMotion());
}

/**
 * A number that counts to its new value instead of jumping (700 ms, ease-out).
 * The first value counts up from zero when `fromZero` is set and motion is
 * Lively or Max; later changes count from the previous value at any level except Off.
 */
export function useCountUp(value: number | null | undefined, level: MotionLevel, { fromZero = false, duration = 700 }: { fromZero?: boolean; duration?: number } = {}): number | null {
  const target = typeof value === "number" && Number.isFinite(value) ? value : null;
  const animateFirst = fromZero && (level === "lively" || level === "max");
  const [shown, setShown] = useState<number | null>(animateFirst && target != null ? 0 : target);
  const shownRef = useRef<number | null>(shown);
  const first = useRef(true);

  useEffect(() => {
    const isFirst = first.current;
    first.current = false;
    let frame = 0;
    // Every update runs in an animation frame, never synchronously in the effect.
    const settle = (next: number | null) => {
      frame = requestAnimationFrame(() => { shownRef.current = next; setShown(next); });
      return () => cancelAnimationFrame(frame);
    };
    if (target == null) return settle(null);
    const from = isFirst ? (animateFirst ? 0 : target) : shownRef.current ?? target;
    if (level === "off" || from === target) return settle(target);
    const start = performance.now();
    const step = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      const next = progress >= 1 ? target : from + (target - from) * eased;
      shownRef.current = next;
      setShown(next);
      if (progress < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
    // `animateFirst` only matters for the first value.
  }, [target, level, duration]); // eslint-disable-line react-hooks/exhaustive-deps

  return shown;
}

/**
 * True for a moment after `value` changes (never on the first render), so a
 * number can glow once when it moves. Returns a fresh key per change so a CSS
 * animation restarts even when two changes come close together.
 */
export function useChangeFlash(value: unknown, ms = 1300): number {
  const [flash, setFlash] = useState(0);
  const previous = useRef(value);
  useEffect(() => {
    if (Object.is(previous.current, value)) return;
    previous.current = value;
    setFlash((count) => count + 1);
    const timer = window.setTimeout(() => setFlash(0), ms);
    return () => window.clearTimeout(timer);
  }, [value, ms]);
  return flash;
}
