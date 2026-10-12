"use client";

import { useCountUp, useMotionLevel } from "@/lib/motion";

/**
 * A number that counts up when it first appears (Lively and Max) and counts to
 * its new value whenever it changes. While it moves, screen readers get the
 * final value from hidden text and never hear the digits tick.
 */
export function CountUp({
  value,
  format,
  decimals = 0,
  signed = false,
  fromZero = true,
  duration = 800,
}: {
  value: number | null | undefined;
  format?: (value: number) => string;
  decimals?: number;
  signed?: boolean;
  fromZero?: boolean;
  duration?: number;
}) {
  const level = useMotionLevel();
  const shown = useCountUp(value, level, { fromZero, duration });
  const render = (n: number) => {
    const rounded = decimals ? Number(n.toFixed(decimals)) : Math.round(n);
    const text = format ? format(rounded) : decimals ? rounded.toFixed(decimals) : String(rounded);
    return `${signed && rounded > 0 ? "+" : ""}${text}`;
  };
  if (shown == null || value == null || !Number.isFinite(value)) return <>—</>;
  const final = render(value);
  const now = render(shown);
  if (now === final) return <>{final}</>;
  return <span className="count"><span className="sr-only">{final}</span><span aria-hidden="true">{now}</span></span>;
}
