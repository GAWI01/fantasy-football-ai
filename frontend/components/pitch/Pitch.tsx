"use client";

import { AlertTriangle } from "lucide-react";
import type { DragEvent, ReactNode } from "react";

import { Kit } from "@/components/kit/Kit";
import { POSITIONS } from "@/lib/fpl/rules";
import { isFlagged, type SquadPlayer } from "@/lib/model/squad";

export type ValueMode = "projected" | "live";

export function playerValue(player: SquadPlayer, mode: ValueMode, captainId?: number | null): { text: string; kind: "model" | "live" | "none"; label: string } {
  if (mode === "live") {
    if (player.livePoints == null) return { text: "—", kind: "none", label: "no live points yet" };
    const multiplier = player.isStarter ? (player.multiplier ?? 1) : 1;
    const total = player.livePoints * Math.max(1, multiplier);
    return { text: String(total), kind: "live", label: `${total} live points${multiplier > 1 ? " including captaincy" : ""}` };
  }
  if (player.xp == null) return { text: "—", kind: "none", label: "no projection" };
  const doubled = captainId != null && captainId === player.id;
  const value = player.xp * (doubled ? 2 : 1);
  return { text: value.toFixed(1), kind: "model", label: `${value.toFixed(1)} projected points${doubled ? " as captain" : ""}` };
}

function fixtureLabel(player: SquadPlayer, mode: ValueMode): string | null {
  if (mode === "live") {
    if (player.fixtureState === "live") return player.liveMinutes != null ? `${player.liveMinutes}′` : "Live";
    if (player.fixtureState === "finished") return player.liveMinutes != null ? `FT · ${player.liveMinutes}′` : "FT";
    if (player.fixtureState === "upcoming") return "To play";
    if (player.fixtureState === "none") return "No match";
    return null;
  }
  if (!player.opponent) return null;
  const opponent = player.opponent.length > 14 ? player.opponent.slice(0, 3).toUpperCase() : player.opponent;
  return player.home == null ? opponent : `${opponent} (${player.home ? "H" : "A"})`;
}

export type PitchPlayerProps = {
  player: SquadPlayer;
  mode: ValueMode;
  captainId?: number | null;
  viceId?: number | null;
  selected?: boolean;
  target?: boolean;
  dimmed?: boolean;
  size?: "sm" | "md";
  benchIndex?: number;
  onPress?: (player: SquadPlayer) => void;
  draggable?: boolean;
  onDragStart?: (event: DragEvent<HTMLElement>, player: SquadPlayer) => void;
  onDragEnd?: () => void;
  onDrop?: (event: DragEvent<HTMLElement>, player: SquadPlayer) => void;
  onDragOver?: (event: DragEvent<HTMLElement>, player: SquadPlayer) => void;
};

export function PitchPlayer({
  player,
  mode,
  captainId,
  viceId,
  selected,
  target,
  dimmed,
  size = "md",
  benchIndex,
  onPress,
  draggable,
  onDragStart,
  onDragEnd,
  onDrop,
  onDragOver,
}: PitchPlayerProps) {
  const isCaptain = captainId != null ? captainId === player.id : player.isCaptain;
  const isVice = viceId != null ? viceId === player.id : player.isVice;
  const value = playerValue(player, mode, isCaptain ? player.id : null);
  const fixture = fixtureLabel(player, mode);
  const flagged = isFlagged(player);
  const status = String(player.status ?? "a").toLowerCase();
  const flagTone = status === "i" || status === "s" || status === "u" || status === "n" || player.risk?.label === "VERY_HIGH" ? "risk" : "warn";
  const roles = [isCaptain ? "captain" : null, isVice ? "vice-captain" : null, flagged ? "flagged" : null].filter(Boolean).join(", ");
  const label = `${player.name}, ${player.position}, ${player.teamShort}${roles ? `, ${roles}` : ""}, ${value.label}${benchIndex != null ? `, bench ${benchIndex + 1}` : ""}`;
  const Tag = onPress ? "button" : "div";
  return (
    <Tag
      {...(onPress ? { type: "button" as const, onClick: () => onPress(player), "aria-pressed": selected ?? false } : { role: "group" })}
      aria-label={label}
      className={["pp", `pp-${size}`, selected ? "is-selected" : "", target ? "is-target" : "", dimmed ? "is-dimmed" : "", mode === "live" && player.fixtureState === "live" ? "is-playing" : ""].filter(Boolean).join(" ")}
      draggable={draggable || undefined}
      onDragStart={draggable ? (event: DragEvent<HTMLElement>) => onDragStart?.(event, player) : undefined}
      onDragEnd={draggable ? onDragEnd : undefined}
      onDragOver={onDragOver ? (event: DragEvent<HTMLElement>) => onDragOver(event, player) : undefined}
      onDrop={onDrop ? (event: DragEvent<HTMLElement>) => onDrop(event, player) : undefined}
    >
      <span className="pp-kit">
        <Kit team={player.team} teamShort={player.teamShort} goalkeeper={player.position === "GKP"} size={size === "sm" ? 38 : 50} />
        {isCaptain ? <b className="pp-badge pp-badge-c" aria-hidden="true">C</b> : isVice ? <b className="pp-badge pp-badge-v" aria-hidden="true">V</b> : null}
        {flagged ? <i className={`pp-flag pp-flag-${flagTone}`} aria-hidden="true"><AlertTriangle size={10} strokeWidth={3} /></i> : null}
      </span>
      <span className="pp-plate">
        <span className="pp-name">{player.name}</span>
        <span className={`pp-value pp-value-${value.kind}`}>{value.text}</span>
      </span>
      {fixture ? <span className="pp-fixture">{fixture}</span> : null}
    </Tag>
  );
}

export function PitchSurface({ children, compact = false, label }: { children: ReactNode; compact?: boolean; label: string }) {
  return (
    <div className={`pitch${compact ? " pitch-compact" : ""}`} role="group" aria-label={label}>
      <svg className="pitch-lines" viewBox="0 0 100 140" preserveAspectRatio="none" aria-hidden="true">
        <rect x="3" y="3" width="94" height="134" rx="1.5" />
        <line x1="3" y1="70" x2="97" y2="70" />
        <circle cx="50" cy="70" r="11" />
        <rect x="26" y="3" width="48" height="19" />
        <rect x="39" y="3" width="22" height="7" />
        <rect x="26" y="118" width="48" height="19" />
        <rect x="39" y="130" width="22" height="7" />
      </svg>
      <div className="pitch-rows">{children}</div>
    </div>
  );
}

/** Static formation view: 11 starters by line, top to bottom GKP → FWD. */
export function FormationRows({ starters, render }: { starters: SquadPlayer[]; render: (player: SquadPlayer) => ReactNode }) {
  return (
    <>
      {POSITIONS.map((position) => (
        <div className="pitch-row" key={position} data-line={position}>
          {starters.filter((player) => player.position === position).map((player) => render(player))}
        </div>
      ))}
    </>
  );
}
