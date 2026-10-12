"use client";

import { useEffect, useRef } from "react";

import type { MotionLevel } from "@/lib/motion";

/**
 * The page background: soft violet, teal and green light that drifts like
 * floodlight spill on a night pitch, and reacts to the game.
 *
 * Cheap by design. It draws a few radial gradients on a canvas at 1/8 of the
 * screen's size and lets the browser stretch it, so the blur costs nothing.
 * It redraws 14 times a second at most, pauses while the page scrolls or is
 * hidden, and never moves at the Off level (or with reduced motion).
 */
export type AmbientMood = "decision" | "live" | "deadline" | "urgent" | "settled";

type Rgba = [number, number, number, number];

const SCALE = 1 / 8;
const IDLE_FPS = 14;
const BURST_FPS = 30;
const CROSSFADE_MS = 1200;
const SWELL_MS = 1400;
const SCROLL_REST_MS = 300;

// Colour fields: position as a share of the screen, radius as a share of its
// longer side, and a slow ellipse to drift along (periods 29-63 s).
const FIELDS = [
  { x: 0.08, y: -0.04, r: 0.95, ax: 0.1, ay: 0.06, p: 41, o: 0 },
  { x: 0.96, y: 0.22, r: 0.78, ax: 0.07, ay: 0.1, p: 57, o: 1.3 },
  { x: 0.1, y: 0.86, r: 0.8, ax: 0.09, ay: 0.06, p: 63, o: 2.1 },
  { x: 0.62, y: 1.06, r: 0.85, ax: 0.12, ay: 0.04, p: 49, o: 3.4 },
  { x: 0.96, y: -0.06, r: 0.5, ax: 0.05, ay: 0.04, p: 33, o: 0.7 },
  { x: 1.02, y: 0.78, r: 0.7, ax: 0.04, ay: 0.08, p: 29, o: 4.2 },
  { x: 0.98, y: 1.04, r: 0.55, ax: 0.03, ay: 0.03, p: 37, o: 5 },
];

function hex(color: string, alpha: number): Rgba {
  const value = parseInt(color.slice(1), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255, alpha];
}

// Peak strengths stay low enough that 12px grey text on the glass cards keeps
// at least 4.5:1 contrast.
const MOODS: Record<AmbientMood, Rgba[]> = {
  decision: [hex("#7c3aed", 0.4), hex("#4f46e5", 0.26), hex("#0ea5a4", 0.14), hex("#10b981", 0.08), hex("#c4b5fd", 0.08), hex("#fbbf24", 0), hex("#f87171", 0)],
  live: [hex("#a7f3d0", 0.16), hex("#4f46e5", 0.16), hex("#14b8a6", 0.16), hex("#10b981", 0.26), hex("#d1fae5", 0.14), hex("#fbbf24", 0), hex("#f87171", 0)],
  deadline: [hex("#7c3aed", 0.32), hex("#4338ca", 0.16), hex("#0ea5a4", 0.08), hex("#10b981", 0.05), hex("#fde68a", 0.07), hex("#fbbf24", 0.18), hex("#f87171", 0.06)],
  urgent: [hex("#7c3aed", 0.28), hex("#4338ca", 0.14), hex("#0ea5a4", 0.05), hex("#10b981", 0.03), hex("#fde68a", 0.08), hex("#fbbf24", 0.24), hex("#f87171", 0.14)],
  settled: [hex("#6d28d9", 0.26), hex("#334155", 0.2), hex("#0ea5a4", 0.08), hex("#10b981", 0.05), hex("#94a3b8", 0.05), hex("#fbbf24", 0), hex("#f87171", 0)],
};

function mix(from: Rgba[], to: Rgba[], k: number): Rgba[] {
  return to.map((color, index) => color.map((value, channel) => from[index][channel] + (value - from[index][channel]) * k) as Rgba);
}

const ease = (t: number) => (t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t));

export function AmbientBackground({ mood, level, goalId }: { mood: AmbientMood; level: MotionLevel; goalId: number | null }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  // Everything the drawing loop needs lives in one mutable object, so props can
  // change without restarting the loop.
  const engine = useRef({
    from: MOODS[mood], to: MOODS[mood], fadeStart: -1, swellStart: -1,
    level, t0: 0, width: 0, height: 0,
    kick: () => {},
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d", { alpha: false });
    if (!canvas || !context) return;
    const state = engine.current;
    state.t0 = performance.now();
    let frame = 0;
    let last = 0;
    let scrolling = false;
    let scrollTimer = 0;

    const size = () => {
      const width = Math.max(24, Math.round(window.innerWidth * SCALE));
      const height = Math.max(24, Math.round(window.innerHeight * SCALE));
      // Mobile toolbars change the height while scrolling; only a new width redraws the buffer.
      if (width === state.width && Math.abs(height - state.height) < 4) return false;
      state.width = width;
      state.height = height;
      canvas.width = width;
      canvas.height = height;
      return true;
    };

    const current = (now: number) => {
      if (state.fadeStart < 0) return state.to;
      const k = ease((now - state.fadeStart) / CROSSFADE_MS);
      if (k >= 1) { state.fadeStart = -1; state.from = state.to; return state.to; }
      return mix(state.from, state.to, k);
    };

    const draw = (now: number) => {
      const W = state.width;
      const H = state.height;
      const L = Math.max(W, H);
      // Calm and Off show a still frame; only crossfades and the goal swell move.
      const drifting = state.level === "lively" || state.level === "max";
      const t = drifting ? (now - state.t0) / 1000 : 18;
      const gain = state.level === "max" ? 1.1 : 1;
      const colors = current(now);
      context.globalCompositeOperation = "source-over";
      context.fillStyle = "#04060d";
      context.fillRect(0, 0, W, H);
      context.globalCompositeOperation = "lighter";
      FIELDS.forEach((field, index) => {
        const [r, g, b, a] = colors[index];
        if (a <= 0.002) return;
        const w = (2 * Math.PI * t) / field.p + field.o;
        const x = (field.x + Math.cos(w) * field.ax) * W;
        const y = (field.y + Math.sin(w * 0.8) * field.ay) * H;
        const radius = field.r * L * (1 + 0.06 * Math.sin(w * 1.3));
        const alpha = a * gain * (1 + 0.12 * Math.sin(w * 1.7 + index));
        const gradient = context.createRadialGradient(x, y, 0, x, y, radius);
        const rgb = `rgba(${r | 0},${g | 0},${b | 0},`;
        gradient.addColorStop(0, `${rgb}${alpha.toFixed(3)})`);
        gradient.addColorStop(0.45, `${rgb}${(alpha * 0.45).toFixed(3)})`);
        gradient.addColorStop(1, `${rgb}0)`);
        context.fillStyle = gradient;
        context.fillRect(0, 0, W, H);
      });
      if (state.swellStart >= 0) {
        const k = (now - state.swellStart) / SWELL_MS;
        if (k >= 1) state.swellStart = -1;
        else {
          const rise = ease(Math.min(1, k / 0.45));
          const fall = 1 - ease(Math.max(0, (k - 0.35) / 0.65));
          const alpha = 0.34 * rise * fall;
          const y = H * (1.25 - 0.55 * rise);
          const radius = L * (0.45 + 0.6 * rise);
          const swell = context.createRadialGradient(W * 0.5, y, 0, W * 0.5, y, radius);
          swell.addColorStop(0, `rgba(52,211,153,${alpha.toFixed(3)})`);
          swell.addColorStop(0.5, `rgba(16,185,129,${(alpha * 0.45).toFixed(3)})`);
          swell.addColorStop(1, "rgba(16,185,129,0)");
          context.fillStyle = swell;
          context.fillRect(0, 0, W, H);
        }
      }
      // Keep the middle, where the cards sit, a little calmer.
      context.globalCompositeOperation = "source-over";
      const calm = context.createRadialGradient(W * 0.5, H * 0.5, 0, W * 0.5, H * 0.5, L * 0.55);
      calm.addColorStop(0, "rgba(4,6,13,0.28)");
      calm.addColorStop(1, "rgba(4,6,13,0)");
      context.fillStyle = calm;
      context.fillRect(0, 0, W, H);
    };

    const busy = () => state.fadeStart >= 0 || state.swellStart >= 0;
    const wantsLoop = () => !document.hidden && !scrolling && (busy() || state.level === "lively" || state.level === "max");

    const loop = (now: number) => {
      frame = 0;
      if (!wantsLoop()) { draw(now); return; }
      frame = requestAnimationFrame(loop);
      const fps = state.swellStart >= 0 ? BURST_FPS : IDLE_FPS;
      if (now - last < 1000 / fps - 2) return;
      last = now;
      draw(now);
    };
    const kick = () => {
      if (frame) return;
      if (wantsLoop()) frame = requestAnimationFrame(loop);
      else draw(performance.now());
    };
    state.kick = kick;

    const onScroll = () => {
      scrolling = true;
      window.clearTimeout(scrollTimer);
      scrollTimer = window.setTimeout(() => { scrolling = false; kick(); }, SCROLL_REST_MS);
    };
    const onResize = () => { if (size()) draw(performance.now()); };

    size();
    draw(performance.now());
    kick();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onResize);
    document.addEventListener("visibilitychange", kick);
    return () => {
      cancelAnimationFrame(frame);
      window.clearTimeout(scrollTimer);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", kick);
      state.kick = () => {};
    };
  }, []);

  // Mood changes crossfade (instantly at the Off level).
  useEffect(() => {
    const state = engine.current;
    const now = performance.now();
    const next = MOODS[mood];
    if (state.to === next) return;
    if (state.level === "off") { state.from = next; state.to = next; state.fadeStart = -1; }
    else {
      const k = state.fadeStart < 0 ? 1 : ease((now - state.fadeStart) / CROSSFADE_MS);
      state.from = state.fadeStart < 0 ? state.to : mix(state.from, state.to, k);
      state.to = next;
      state.fadeStart = now;
    }
    state.kick();
  }, [mood]);

  useEffect(() => {
    engine.current.level = level;
    engine.current.kick();
  }, [level]);

  // A goal by one of your players: a green swell rises from the bottom once.
  useEffect(() => {
    if (goalId == null || engine.current.level === "off") return;
    engine.current.swellStart = performance.now();
    engine.current.kick();
  }, [goalId]);

  return (
    <div className="ambient" aria-hidden="true">
      <canvas ref={canvasRef} className="ambient-canvas" />
    </div>
  );
}
