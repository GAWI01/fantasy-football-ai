"use client";

import { CalendarRange } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { FixtureCell } from "@/components/fixtures/FixtureCell";
import { Kit } from "@/components/kit/Kit";
import { DataState } from "@/components/states/DataState";
import { Card, Skeleton } from "@/components/ui/primitives";
import { useFixtureMatrix } from "@/lib/hooks/data";
import { runScore } from "@/lib/fpl/fixtures";
import type { SquadPlayer } from "@/lib/model/squad";

/** Upcoming fixture runs for the clubs you own, easiest run first. */
export function SquadFixtures({ squad, horizon = 5 }: { squad: SquadPlayer[]; horizon?: number }) {
  const matrix = useFixtureMatrix(horizon);
  const rows = useMemo(() => {
    const data = matrix.data?.data;
    if (!data) return [];
    const owned = new Map<string, SquadPlayer[]>();
    for (const player of squad) owned.set(player.teamShort, [...(owned.get(player.teamShort) ?? []), player]);
    return data.teams
      .filter((team) => owned.has(team.team_short))
      .map((team) => ({ team, players: owned.get(team.team_short) ?? [], score: runScore(team) }))
      .sort((left, right) => left.score - right.score);
  }, [matrix.data, squad]);
  const gameweeks = matrix.data?.data.gameweeks ?? [];

  return (
    <Card title="Your fixture runs" eyebrow={gameweeks.length ? `GW${gameweeks[0]}–${gameweeks[gameweeks.length - 1]}` : "Next Gameweeks"} icon={<CalendarRange size={16} />} source={matrix.data?.meta.stale ? "cached" : "official"} action={<Link className="link" href="/fixtures">Planner</Link>} className="squad-fixtures">
      {matrix.loading && !matrix.data ? <Skeleton lines={5} /> : matrix.error && !matrix.data ? (
        <DataState compact tone="unavailable" title="Fixtures unavailable">{matrix.error}</DataState>
      ) : (
        <div className="fx-table" role="table" aria-label="Fixture runs for clubs in your squad">
          <div className="fx-tr fx-thead" role="row" style={{ gridTemplateColumns: `minmax(116px, 1.2fr) repeat(${gameweeks.length}, minmax(52px, 1fr))` }}>
            <span role="columnheader">Club</span>
            {gameweeks.map((gameweek) => <span role="columnheader" key={gameweek}>GW{gameweek}</span>)}
          </div>
          {rows.map(({ team, players }) => (
            <div className="fx-tr" role="row" key={team.team_id} style={{ gridTemplateColumns: `minmax(116px, 1.2fr) repeat(${gameweeks.length}, minmax(52px, 1fr))` }}>
              <span role="rowheader" className="fx-club">
                <Kit team={team.team} teamShort={team.team_short} size={24} bare />
                <span><b>{team.team_short}</b><small>{players.map((player) => player.name).join(", ")}</small></span>
              </span>
              {gameweeks.map((gameweek) => (
                <span role="cell" key={gameweek}><FixtureCell cell={team.fixtures.find((cell) => cell.event === gameweek)} compact /></span>
              ))}
            </div>
          ))}
          {!rows.length ? <p className="faint">No fixtures found for your clubs.</p> : null}
        </div>
      )}
    </Card>
  );
}
