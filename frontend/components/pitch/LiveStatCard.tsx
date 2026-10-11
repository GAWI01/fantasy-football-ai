"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { Kit } from "@/components/kit/Kit";
import type { LiveStat } from "@/lib/contracts";
import type { SquadPlayer } from "@/lib/model/squad";

const STAT_LABEL: Record<string, [string, string]> = {
  minutes: ["Minute played", "Minutes played"],
  goals_scored: ["Goal", "Goals"],
  assists: ["Assist", "Assists"],
  clean_sheets: ["Clean sheet", "Clean sheets"],
  goals_conceded: ["Goal conceded", "Goals conceded"],
  saves: ["Save", "Saves"],
  bonus: ["Bonus", "Bonus"],
  bps: ["BPS", "BPS"],
  yellow_cards: ["Yellow card", "Yellow cards"],
  red_cards: ["Red card", "Red cards"],
  own_goals: ["Own goal", "Own goals"],
  penalties_saved: ["Penalty saved", "Penalties saved"],
  penalties_missed: ["Penalty missed", "Penalties missed"],
  defensive_contribution: ["Defensive contribution", "Defensive contributions"],
};

export function statLabel(stat: LiveStat): string {
  const [singular, plural] = STAT_LABEL[stat.stat] ?? [stat.stat.replace(/_/g, " "), stat.stat.replace(/_/g, " ")];
  return stat.value === 1 ? singular : plural;
}

function scoreLine(player: SquadPlayer): string | null {
  const fixture = player.liveFixture;
  if (!fixture) return player.fixtureState === "none" ? "No match this Gameweek" : null;
  const teams = `${fixture.home_team_short ?? fixture.home_team} ${fixture.started ? `${fixture.home_score ?? 0}–${fixture.away_score ?? 0}` : "v"} ${fixture.away_team_short ?? fixture.away_team}`;
  const state = fixture.finished ? (fixture.bonus_pending ? "FT · bonus pending" : "FT") : fixture.started ? `${fixture.minutes}′` : "To play";
  return `${teams} · ${state}`;
}

const WIDTH = 236;
const GAP = 8;

/**
 * Glass card with the official points breakdown, anchored to a pitch tile.
 * Rendered in a portal with fixed positioning: the pitch clips its children.
 */
export function LiveStatCard({ player, anchor, id }: { player: SquadPlayer; anchor: HTMLElement; id: string }) {
  const card = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);

  useLayoutEffect(() => {
    const rect = anchor.getBoundingClientRect();
    const height = card.current?.offsetHeight ?? 200;
    const left = Math.min(Math.max(GAP, rect.left + rect.width / 2 - WIDTH / 2), window.innerWidth - WIDTH - GAP);
    const above = rect.top - height - GAP;
    const top = above >= GAP ? above : Math.min(rect.bottom + GAP, window.innerHeight - height - GAP);
    setPosition({ top, left });
  }, [anchor]);

  const multiplier = player.isStarter ? Math.max(1, player.multiplier ?? 1) : 1;
  // FPL lists provisional bonus too; it is confirmed only once the fixture is.
  const bonusPending = Boolean(player.liveFixture?.bonus_pending);
  const stats = player.liveBreakdown.map((stat) => (stat.stat === "bonus" && bonusPending ? { ...stat, provisional: true } : stat));
  const score = scoreLine(player);
  const provisional = stats.some((stat) => stat.provisional);
  const total = stats.reduce((sum, stat) => sum + (stat.points ?? 0), 0);

  return createPortal(
    <div
      ref={card}
      id={id}
      role="tooltip"
      className="live-stat-card"
      style={{ width: WIDTH, top: position?.top ?? -9999, left: position?.left ?? -9999 }}
    >
      <header className="lsc-head">
        <Kit team={player.team} teamShort={player.teamShort} goalkeeper={player.position === "GKP"} size={30} bare />
        <span className="lsc-who"><b>{player.name}</b><small>{player.position} · {player.teamShort}{player.isStarter ? "" : " · bench"}</small></span>
        <span className="lsc-total"><b className="num">{(player.livePoints ?? total) * multiplier}</b><small>{multiplier > 2 ? "pts ×3" : multiplier > 1 ? "pts ×2" : "pts"}</small></span>
      </header>
      {score ? <p className="lsc-score">{score}</p> : null}
      {stats.length ? (
        <ul className="lsc-rows">
          {stats.map((stat) => (
            <li key={stat.stat} className={(stat.points ?? 0) < 0 ? "is-neg" : undefined}>
              <span>{statLabel(stat)}{stat.provisional ? <em>provisional</em> : null}</span>
              <span className="num lsc-value">{stat.value}</span>
              <span className="num lsc-points">{stat.points == null ? "" : stat.points > 0 ? `+${stat.points}` : stat.points}</span>
            </li>
          ))}
        </ul>
      ) : <p className="lsc-empty">{player.fixtureState === "upcoming" ? "Has not played yet." : "No points recorded yet."}</p>}
      <footer className="lsc-foot">
        {player.liveBps != null ? <span>BPS <b className="num">{player.liveBps}</b></span> : null}
        {player.liveExpected != null ? <span>Model <b className="num">{player.liveExpected.toFixed(1)}</b> xP</span> : null}
        {provisional ? <span className="lsc-note">Bonus not confirmed yet</span> : null}
      </footer>
    </div>,
    document.body,
  );
}
