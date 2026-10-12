import { useId } from "react";

import { kitDesign, type KitDesign } from "@/lib/fpl/kits";

const SHIRT =
  "M20 6 L26 3.5 Q32 9.5 38 3.5 L44 6 L58.5 14.5 L53.5 27 L46.5 24 L46.5 57.5 Q32 61 17.5 57.5 L17.5 24 L10.5 27 L5.5 14.5 Z";

/** Front panel edges; stripes are laid out across this width. */
const TORSO_LEFT = 17.5;
const TORSO_RIGHT = 46.5;

/** Sleeves from shoulder seam to cuff, a little oversized and trimmed by the shirt clip. */
const LEFT_SLEEVE = "4,14 20,5.6 17.5,24 10,28.5";
const RIGHT_SLEEVE = "60,14 44,5.6 46.5,24 54,28.5";

/** Vertical stripes: equal bands across the front, alternating body/detail and carried over the sleeves. */
function Stripes({ count, color }: { count: number; color: string }) {
  const width = (TORSO_RIGHT - TORSO_LEFT) / count;
  const bands: number[] = [];
  for (let index = -7; index < count + 7; index += 1) {
    const x = TORSO_LEFT + index * width;
    if (Math.abs(index % 2) === 1 && x < 64 && x + width > 0) bands.push(x);
  }
  return (
    <g fill={color}>
      {bands.map((x) => <rect key={x} x={x} y="0" width={width} height="64" />)}
    </g>
  );
}

function Pattern({ kit }: { kit: KitDesign }) {
  switch (kit.pattern) {
    case "stripes":
      return <Stripes count={kit.stripes ?? 5} color={kit.detail} />;
    case "hoops":
      return (
        <g fill={kit.detail}>
          {[10, 24, 38, 52].map((y) => <rect key={y} x="0" y={y} width="64" height="7" />)}
        </g>
      );
    case "halves":
      return <rect x="32" y="0" width="32" height="64" fill={kit.detail} />;
    case "sash":
      return <polygon points="4,15 19,5 60,51 47,61" fill={kit.detail} />;
    case "pinstripe":
      return (
        <g stroke={kit.detail} strokeWidth="1.2" opacity="0.55">
          {[22, 27, 32, 37, 42].map((x) => <line key={x} x1={x} y1="8" x2={x} y2="62" />)}
        </g>
      );
    default:
      return null;
  }
}

/** Relative luminance (0-1) of a #rrggbb colour; anything unparseable counts as light. */
function luminance(hex: string): number {
  const match = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!match) return 1;
  const value = Number.parseInt(match[1], 16);
  const channel = (shift: number) => {
    const c = ((value >> shift) & 255) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(16) + 0.7152 * channel(8) + 0.0722 * channel(0);
}

export type KitProps = {
  team?: string | null;
  teamShort?: string | null;
  goalkeeper?: boolean;
  size?: number;
  className?: string;
  /** Hide the club initials, e.g. in very small renders. */
  bare?: boolean;
};

/**
 * A simplified shirt in a club's traditional home colours, drawn for this site.
 * Decorative: callers provide accessible names.
 */
export function Kit({ team, teamShort, goalkeeper = false, size = 44, className, bare = false }: KitProps) {
  const id = useId().replace(/:/g, "");
  const kit = kitDesign(team, teamShort, goalkeeper);
  const sleeves = kit.pattern === "sleeves" ? kit.sleeves ?? kit.detail : kit.sleeves;
  const lightInk = luminance(kit.ink) > 0.4;
  // A firmer halo where the initials cross two colours (stripes, hoops, halves, sash).
  const busy = kit.pattern !== "plain" && kit.pattern !== "sleeves" && kit.pattern !== "pinstripe";
  return (
    <svg
      className={["kit", className].filter(Boolean).join(" ")}
      width={size}
      height={size}
      viewBox="0 0 64 64"
      aria-hidden="true"
      focusable="false"
      data-club={kit.code}
    >
      <defs>
        <clipPath id={`kit-clip-${id}`}><path d={SHIRT} /></clipPath>
        <linearGradient id={`kit-shade-${id}`} x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.22" />
          <stop offset="0.5" stopColor="#ffffff" stopOpacity="0" />
          <stop offset="1" stopColor="#000000" stopOpacity="0.28" />
        </linearGradient>
      </defs>
      <g clipPath={`url(#kit-clip-${id})`}>
        <rect width="64" height="64" fill={kit.body} />
        <Pattern kit={kit} />
        {sleeves ? (
          <g fill={sleeves}>
            <polygon points={LEFT_SLEEVE} />
            <polygon points={RIGHT_SLEEVE} />
          </g>
        ) : null}
        <rect width="64" height="64" fill={`url(#kit-shade-${id})`} />
      </g>
      <path d={SHIRT} fill="none" stroke="rgba(0,0,0,0.45)" strokeWidth="1.1" strokeLinejoin="round" />
      <path d="M26 3.5 Q32 11 38 3.5" fill="none" stroke={kit.trim} strokeWidth="2.2" strokeLinecap="round" />
      <path d="M5.5 14.5 L10.5 27 M58.5 14.5 L53.5 27" stroke={kit.trim} strokeWidth="2.4" strokeLinecap="round" />
      {bare ? null : (
        <text
          x="32"
          y="51"
          textAnchor="middle"
          fontSize="8.5"
          fontWeight="800"
          letterSpacing="0.6"
          fill={kit.ink}
          stroke={lightInk ? "#070a12" : "#ffffff"}
          strokeOpacity={busy ? 0.85 : lightInk ? 0.55 : 0.45}
          strokeWidth={busy ? 2.4 : 2}
          strokeLinejoin="round"
          paintOrder="stroke"
          fontFamily="var(--font-sans), system-ui, sans-serif"
        >
          {kit.code}
        </text>
      )}
    </svg>
  );
}
