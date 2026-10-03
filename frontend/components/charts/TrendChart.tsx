"use client";

import { useId, useMemo, useState, type PointerEvent } from "react";

const pad = { top: 14, right: 12, bottom: 22, left: 52 };

export type TrendPoint = { x: number; y: number };

/**
 * Single-series line or bar chart with one y-axis, recessive grid,
 * crosshair tooltip on hover/touch and an sr-only table.
 */
export function TrendChart({
  points,
  kind = "line",
  invert = false,
  height = 160,
  label,
  xLabel = (x) => `GW${x}`,
  yLabel = (y) => y.toLocaleString("en-GB"),
  tone = "accent",
  reference,
}: {
  points: TrendPoint[];
  kind?: "line" | "bar";
  /** Draw smaller values higher (e.g. rank). */
  invert?: boolean;
  height?: number;
  label: string;
  xLabel?: (x: number) => string;
  yLabel?: (y: number) => string;
  tone?: "accent" | "live" | "cyan";
  reference?: { y: number; label: string };
}) {
  const gradientId = useId().replace(/:/g, "");
  const [hover, setHover] = useState<number | null>(null);
  const width = 640;
  const geometry = useMemo(() => {
    if (!points.length) return null;
    const ys = points.map((point) => point.y).concat(reference ? [reference.y] : []);
    let min = Math.min(...ys);
    let max = Math.max(...ys);
    if (kind === "bar") min = Math.min(0, min);
    if (min === max) { min -= 1; max += 1; }
    const span = max - min;
    min = kind === "bar" ? min : min - span * 0.08;
    max = max + span * 0.08;
    const innerW = width - pad.left - pad.right;
    const innerH = height - pad.top - pad.bottom;
    const step = points.length > 1 ? innerW / (points.length - 1) : 0;
    const barW = Math.max(4, Math.min(22, innerW / points.length - 6));
    const xAt = (index: number) => kind === "bar"
      ? pad.left + (innerW / points.length) * (index + 0.5)
      : pad.left + (points.length > 1 ? step * index : innerW / 2);
    const yAt = (value: number) => {
      const ratio = (value - min) / (max - min);
      return pad.top + (invert ? ratio : 1 - ratio) * innerH;
    };
    const ticks = [0, 0.5, 1].map((t) => min + (max - min) * t);
    return { xAt, yAt, ticks, barW, innerH, innerW, min };
  }, [points, kind, invert, height, reference]);

  if (!geometry) return <p className="faint">No data yet.</p>;
  const { xAt, yAt, ticks, barW } = geometry;
  const path = points.map((point, index) => `${index ? "L" : "M"}${xAt(index).toFixed(1)},${yAt(point.y).toFixed(1)}`).join(" ");
  const baseY = yAt(kind === "bar" ? Math.max(geometry.min, 0) : invert ? ticks[2] : ticks[0]);
  const area = `${path} L${xAt(points.length - 1).toFixed(1)},${baseY.toFixed(1)} L${xAt(0).toFixed(1)},${baseY.toFixed(1)} Z`;

  function onMove(event: PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * width;
    let nearest = 0;
    let distance = Infinity;
    points.forEach((_, index) => {
      const d = Math.abs(xAt(index) - x);
      if (d < distance) { distance = d; nearest = index; }
    });
    setHover(nearest);
  }

  const active = hover != null ? points[hover] : null;
  return (
    <figure className={`trend trend-${tone}`}>
      <div className="trend-plot">
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label} onPointerMove={onMove} onPointerLeave={() => setHover(null)}>
          <defs>
            <linearGradient id={`trend-${gradientId}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" stopColor="currentColor" stopOpacity="0.22" />
              <stop offset="1" stopColor="currentColor" stopOpacity="0" />
            </linearGradient>
          </defs>
          {ticks.map((tick) => (
            <g key={tick} className="trend-grid">
              <line x1={56} x2={width - 12} y1={yAt(tick)} y2={yAt(tick)} />
              <text x={46} y={yAt(tick) + 4} textAnchor="end">{yLabel(Math.round(tick))}</text>
            </g>
          ))}
          {reference ? (
            <g className="trend-ref">
              <line x1={56} x2={width - 12} y1={yAt(reference.y)} y2={yAt(reference.y)} />
            </g>
          ) : null}
          {kind === "line" ? (
            <>
              <path d={area} fill={`url(#trend-${gradientId})`} stroke="none" />
              <path d={path} className="trend-line" fill="none" />
              {points.length <= 24 ? points.map((point, index) => <circle key={point.x} cx={xAt(index)} cy={yAt(point.y)} r={hover === index ? 5 : 3} className="trend-dot" />) : null}
            </>
          ) : points.map((point, index) => {
            const y = yAt(point.y);
            const zero = yAt(Math.max(geometry.min, 0));
            return <rect key={point.x} x={xAt(index) - barW / 2} y={Math.min(y, zero)} width={barW} height={Math.max(1, Math.abs(zero - y))} rx={3} className={`trend-bar${hover === index ? " is-hover" : ""}`} />;
          })}
          {active && hover != null ? <line className="trend-cross" x1={xAt(hover)} x2={xAt(hover)} y1={8} y2={height - 20} /> : null}
          <text className="trend-axis" x={xAt(0)} y={height - 4} textAnchor="start">{xLabel(points[0].x)}</text>
          {points.length > 1 ? <text className="trend-axis" x={xAt(points.length - 1)} y={height - 4} textAnchor="end">{xLabel(points[points.length - 1].x)}</text> : null}
        </svg>
        {active && hover != null ? (
          <div className="trend-tip" style={{ left: `${(xAt(hover) / width) * 100}%` }} role="status">
            <small>{xLabel(active.x)}</small>
            <strong>{yLabel(active.y)}</strong>
          </div>
        ) : null}
      </div>
      {reference ? <figcaption className="trend-caption"><i aria-hidden="true" />{reference.label}</figcaption> : null}
      <table className="sr-only">
        <caption>{label}</caption>
        <tbody>{points.map((point) => <tr key={point.x}><th scope="row">{xLabel(point.x)}</th><td>{yLabel(point.y)}</td></tr>)}</tbody>
      </table>
    </figure>
  );
}
