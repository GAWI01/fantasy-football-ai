import { useId } from "react";

import { kitDesign, type KitPattern } from "@/lib/fpl/kits";

const SHIRT =
  "M20 6 L26 3.5 Q32 9.5 38 3.5 L44 6 L58.5 14.5 L53.5 27 L46.5 24 L46.5 57.5 Q32 61 17.5 57.5 L17.5 24 L10.5 27 L5.5 14.5 Z";

function Pattern({ pattern, color }: { pattern: KitPattern; color: string }) {
  switch (pattern) {
    case "chevron":
      return <polygon points="17,21 32,31 47,21 47,28.5 32,38.5 17,28.5" fill={color} />;
    case "sash":
      return <polygon points="4,15 19,5 60,51 47,61" fill={color} />;
    case "split":
      return <polygon points="41,0 64,0 64,64 23,64" fill={color} />;
    case "yoke":
      return <path d="M0 0 H64 V16.5 Q32 21 0 16.5 Z" fill={color} />;
    case "band":
      return <rect x="0" y="27" width="64" height="7" fill={color} />;
    case "pinstripe":
      return (
        <g stroke={color} strokeWidth="1.2" opacity="0.55">
          {[22, 27, 32, 37, 42].map((x) => <line key={x} x1={x} y1="8" x2={x} y2="62" />)}
        </g>
      );
    default:
      return null;
  }
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

/** An original, club-inspired FPL-AI shirt. Decorative: callers provide accessible names. */
export function Kit({ team, teamShort, goalkeeper = false, size = 44, className, bare = false }: KitProps) {
  const id = useId().replace(/:/g, "");
  const kit = kitDesign(team, teamShort, goalkeeper);
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
        <Pattern pattern={kit.pattern} color={kit.detail} />
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
          fontFamily="var(--font-sans), system-ui, sans-serif"
        >
          {kit.code}
        </text>
      )}
    </svg>
  );
}
