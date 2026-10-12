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
const IDLE_FPS = 15;
const BURST_FPS = 30;
const CROSSFADE_MS = 1200;
const SWELL_MS = 1400;
const PULSE_MS = 1100;
const SCROLL_REST_MS = 300;
const PARALLAX = 0.05;

// Colour fields: position as a share of the screen, radius as a share of its
// longer side, and an ellipse to drift along (periods 17-38 s, so the movement
// is visible without being busy).
const FIELDS = [
  { x: 0.08, y: -0.04, r: 0.95, ax: 0.15, ay: 0.09, p: 26, o: 0 },
  { x: 0.96, y: 0.22, r: 0.78, ax: 0.11, ay: 0.14, p: 34, o: 1.3 },
  { x: 0.1, y: 0.86, r: 0.8, ax: 0.13, ay: 0.09, p: 38, o: 2.1 },
  { x: 0.62, y: 1.06, r: 0.85, ax: 0.17, ay: 0.06, p: 30, o: 3.4 },
  { x: 0.96, y: -0.06, r: 0.5, ax: 0.08, ay: 0.06, p: 21, o: 0.7 },
  { x: 1.02, y: 0.78, r: 0.7, ax: 0.06, ay: 0.11, p: 17, o: 4.2 },
  { x: 0.98, y: 1.04, r: 0.55, ax: 0.05, ay: 0.05, p: 23, o: 5 },
];

// Floodlight beams from the two top corners, sweeping slowly. Colour and
// strength follow the mood (brighter and greener while a Gameweek is live).
const BEAMS = [
  { x: -0.02, y: -0.04, base: 0.62, sweep: 0.16, p: 24, o: 0 },
  { x: 1.02, y: -0.04, base: Math.PI - 0.62, sweep: 0.16, p: 29, o: 1.9 },
];
const BEAM_COLOR: Record<AmbientMood, Rgba> = {
  decision: hex("#c4b5fd", 0.07),
  live: hex("#d1fae5", 0.11),
  deadline: hex("#fde68a", 0.07),
  urgent: hex("#fecaca", 0.07),
  settled: hex("#cbd5e1", 0.04),
};

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

export function AmbientBackground({ mood, level, goalId, pulseKey = null }: { mood: AmbientMood; level: MotionLevel; goalId: number | null; pulseKey?: string | null }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  // Everything the drawing loop needs lives in one mutable object, so props can
  // change without restarting the loop.
  const engine = useRef({
    from: MOODS[mood], to: MOODS[mood], fadeStart: -1, swellStart: -1, pulseStart: -1,
    beamFrom: BEAM_COLOR[mood], beamTo: BEAM_COLOR[mood],
    level, t0: 0, width: 0, height: 0,
    // Pointer light (desktop, Lively and Max): where it is and where it heads.
    pointer: { x: 0.5, y: 0.3, tx: 0.5, ty: 0.3, on: false },
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
      const pulse = state.pulseStart >= 0 ? Math.max(0, 1 - (now - state.pulseStart) / PULSE_MS) : 0;
      if (state.pulseStart >= 0 && pulse <= 0) state.pulseStart = -1;
      // A data refresh brightens the light once, softly.
      const gain = (state.level === "max" ? 1.12 : 1) * (1 + 0.22 * Math.sin(Math.PI * pulse));
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
      // Floodlight beams.
      const fadeK = state.fadeStart < 0 ? 1 : ease((now - state.fadeStart) / CROSSFADE_MS);
      const beam = mix([state.beamFrom], [state.beamTo], fadeK)[0];
      if (beam[3] > 0.004) {
        BEAMS.forEach((item) => {
          const angle = item.base + Math.sin((2 * Math.PI * t) / item.p + item.o) * item.sweep;
          const length = L * 1.25;
          const spread = L * 0.16;
          context.save();
          context.translate(item.x * W, item.y * H);
          context.rotate(angle);
          const light = context.createLinearGradient(0, 0, length, 0);
          const rgb = `rgba(${beam[0] | 0},${beam[1] | 0},${beam[2] | 0},`;
          light.addColorStop(0, `${rgb}${(beam[3] * gain * 1.6).toFixed(3)})`);
          light.addColorStop(0.55, `${rgb}${(beam[3] * gain * 0.6).toFixed(3)})`);
          light.addColorStop(1, `${rgb}0)`);
          context.fillStyle = light;
          context.beginPath();
          context.moveTo(0, -spread * 0.08);
          context.lineTo(length, -spread);
          context.lineTo(length, spread);
          context.lineTo(0, spread * 0.08);
          context.closePath();
          context.fill();
          context.restore();
        });
      }
      // A soft light that follows the pointer on a desktop.
      if (drifting && state.pointer.on) {
        const p = state.pointer;
        p.x += (p.tx - p.x) * 0.12;
        p.y += (p.ty - p.y) * 0.12;
        const glow = context.createRadialGradient(p.x * W, p.y * H, 0, p.x * W, p.y * H, L * 0.35);
        glow.addColorStop(0, "rgba(167,139,250,0.10)");
        glow.addColorStop(1, "rgba(167,139,250,0)");
        context.fillStyle = glow;
        context.fillRect(0, 0, W, H);
      }
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

    const busy = () => state.fadeStart >= 0 || state.swellStart >= 0 || state.pulseStart >= 0;
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

    let parallaxFrame = 0;
    const parallax = () => {
      parallaxFrame = 0;
      // The light drifts a little slower than the page: depth for free, on the compositor.
      const shift = state.level === "off" ? 0 : Math.min(window.scrollY * PARALLAX, window.innerHeight * 0.06);
      canvas.style.transform = `translate3d(0, ${(-shift).toFixed(1)}px, 0) scale(1.08)`;
    };
    const onScroll = () => {
      scrolling = true;
      if (!parallaxFrame) parallaxFrame = requestAnimationFrame(parallax);
      window.clearTimeout(scrollTimer);
      scrollTimer = window.setTimeout(() => { scrolling = false; kick(); }, SCROLL_REST_MS);
    };
    const onPointer = (event: PointerEvent) => {
      if (event.pointerType !== "mouse") return;
      state.pointer.tx = event.clientX / window.innerWidth;
      state.pointer.ty = event.clientY / window.innerHeight;
      if (!state.pointer.on) { state.pointer.on = true; state.pointer.x = state.pointer.tx; state.pointer.y = state.pointer.ty; }
    };
    const onPointerOut = () => { state.pointer.on = false; };
    const onResize = () => { if (size()) draw(performance.now()); };

    size();
    parallax();
    draw(performance.now());
    kick();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onResize);
    window.addEventListener("pointermove", onPointer, { passive: true });
    document.documentElement.addEventListener("pointerleave", onPointerOut);
    document.addEventListener("visibilitychange", kick);
    return () => {
      cancelAnimationFrame(frame);
      cancelAnimationFrame(parallaxFrame);
      window.clearTimeout(scrollTimer);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("pointermove", onPointer);
      document.documentElement.removeEventListener("pointerleave", onPointerOut);
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
    if (state.level === "off") { state.from = next; state.to = next; state.beamFrom = BEAM_COLOR[mood]; state.beamTo = BEAM_COLOR[mood]; state.fadeStart = -1; }
    else {
      const k = state.fadeStart < 0 ? 1 : ease((now - state.fadeStart) / CROSSFADE_MS);
      state.from = state.fadeStart < 0 ? state.to : mix(state.from, state.to, k);
      state.beamFrom = state.fadeStart < 0 ? state.beamTo : mix([state.beamFrom], [state.beamTo], k)[0];
      state.to = next;
      state.beamTo = BEAM_COLOR[mood];
      state.fadeStart = now;
    }
    state.kick();
  }, [mood]);

  useEffect(() => {
    engine.current.level = level;
    engine.current.kick();
  }, [level]);

  // Fresh data: one soft brightening (skipped for the first value).
  const lastPulse = useRef(pulseKey);
  useEffect(() => {
    if (pulseKey == null || pulseKey === lastPulse.current) return;
    lastPulse.current = pulseKey;
    if (engine.current.level === "off") return;
    engine.current.pulseStart = performance.now();
    engine.current.kick();
  }, [pulseKey]);

  // A goal by one of your players: a green swell rises from the bottom once.
  useEffect(() => {
    if (goalId == null || engine.current.level === "off") return;
    engine.current.swellStart = performance.now();
    engine.current.kick();
  }, [goalId]);

  return (
    <div className="ambient" aria-hidden="true">
      <canvas ref={canvasRef} className="ambient-canvas" />
      {/* A dark stadium under the light: the pitch fades into the night, haze
          drifts through the floodlights and fine rain catches the beams. */}
      <div className="ambient-stadium">
        <div className="ambient-pitch">
          <svg viewBox="0 0 100 64" preserveAspectRatio="none">
            <rect x="2" y="2" width="96" height="60" />
            <line x1="50" y1="2" x2="50" y2="62" />
            <circle cx="50" cy="32" r="8" />
            <rect x="2" y="17" width="14" height="30" />
            <rect x="84" y="17" width="14" height="30" />
          </svg>
        </div>
      </div>
      <div className="ambient-haze" />
      <div className="ambient-rain" />
    </div>
  );
}
