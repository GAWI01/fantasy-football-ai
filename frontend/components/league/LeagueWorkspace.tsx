"use client";

import { GitCompareArrows, Trophy, Users } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { useTeam } from "@/app/providers/TeamProvider";
import { DataState } from "@/components/states/DataState";
import { Card, Segmented, Skeleton, SourceBadge } from "@/components/ui/primitives";
import { fixed } from "@/lib/format";
import type { LeaguePlayer, LeagueRole, RivalPlayer } from "@/lib/contracts";
import { useLeague, useLeagues, useRival } from "@/lib/hooks/data";

const ROLE_LABEL: Record<NonNullable<LeagueRole>, string> = { CAPTAIN: "Captain", STARTER: "Starter", BENCH: "Bench" };
type PlayerFilter = "all" | "threats" | "differentials";

function signedGap(value: number): string {
  if (value === 0) return "—";
  return value > 0 ? `+${value}` : `${value}`;
}

function RoleTag({ role }: { role: LeagueRole }) {
  if (!role) return <span className="faint">—</span>;
  return <span className={`pill${role === "CAPTAIN" ? " pill-accent" : ""}`}>{ROLE_LABEL[role]}</span>;
}

function PlayerName({ player }: { player: Pick<LeaguePlayer, "name" | "team_short" | "position"> }) {
  return <span><b>{player.name}</b> <small className="faint">{player.position ?? ""} · {player.team_short}</small></span>;
}

function RivalColumn({ title, players, total }: { title: string; players: RivalPlayer[]; total?: number | null }) {
  return (
    <div className="rival-col">
      <div className="row"><strong>{title}</strong><span className="spacer" />{total != null ? <span className="num tone-accent">{fixed(total)} xP</span> : null}</div>
      {players.length ? (
        <ul className="list">
          {players.map((player) => (
            <li key={player.player_id} className="list-row">
              <div className="list-row-main"><PlayerName player={player} /></div>
              <div className="list-row-end">
                <RoleTag role={player.role} />
                {player.rival_role !== undefined && player.rival_role !== player.role ? <small>Rival: {player.rival_role ? ROLE_LABEL[player.rival_role] : "—"}</small> : null}
                {player.next_gw_points != null ? <small>{fixed(player.next_gw_points)} xP</small> : null}
              </div>
            </li>
          ))}
        </ul>
      ) : <p className="faint">None</p>}
    </div>
  );
}

function RivalCompare({ leagueId, rivalId, teamId, rivalName }: { leagueId: number; rivalId: number; teamId: string; rivalName: string }) {
  const rival = useRival(leagueId, rivalId, teamId);
  const data = rival.data?.data;
  return (
    <Card title={`You vs ${rivalName}`} eyebrow="Head to head" icon={<GitCompareArrows size={16} />} source="official">
      {rival.loading && !data ? <Skeleton lines={6} /> : rival.error ? (
        <DataState tone="error" compact title="Comparison unavailable">{rival.error}</DataState>
      ) : data ? (
        <>
          <p className="card-note">
            The duel is decided by the players you do not share
            {data.same_captain ? ", and you have the same captain." : ". Your captains differ, which counts double."}
            {data.unique_next_gw_points.you != null && data.unique_next_gw_points.rival != null
              ? ` Unique starters project ${fixed(data.unique_next_gw_points.you)} xP for you and ${fixed(data.unique_next_gw_points.rival)} xP for ${rivalName} next Gameweek, if both squads stay the same.`
              : ""}
          </p>
          <div className="rival-grid">
            <RivalColumn title="Only you" players={data.only_you} total={data.unique_next_gw_points.you} />
            <RivalColumn title={`Only ${rivalName}`} players={data.only_rival} total={data.unique_next_gw_points.rival} />
            <RivalColumn title="Shared" players={data.shared} />
          </div>
          <p className="card-note">{data.basis} <SourceBadge kind="official" /></p>
        </>
      ) : null}
    </Card>
  );
}

/** Mini-leagues: standings and gaps, league effective ownership and head-to-head against one rival. */
export function LeagueWorkspace() {
  const { ready, teamId } = useTeam();
  const leagues = useLeagues(teamId);
  const list = useMemo(() => leagues.data?.data.leagues ?? [], [leagues.data]);
  const [leagueId, setLeagueId] = useState<number | null>(null);
  // The chosen rival belongs to one league; switching league clears it.
  const [rival, setRival] = useState<{ league: number; id: number } | null>(null);
  const [filter, setFilter] = useState<PlayerFilter>("all");

  // Default to the smallest league: the one with friends, not a public code league.
  const activeLeague = leagueId ?? [...list].sort((left, right) => (left.managers ?? 1e9) - (right.managers ?? 1e9))[0]?.league_id ?? null;
  const league = useLeague(activeLeague, teamId);
  const data = league.data?.data;
  const rivalId = rival && rival.league === activeLeague ? rival.id : null;

  const players = useMemo(() => {
    const all = data?.players ?? [];
    if (filter === "threats") return all.filter((player) => player.role === "THREAT");
    if (filter === "differentials") return all.filter((player) => player.role === "DIFFERENTIAL");
    return all.slice(0, 25);
  }, [data, filter]);

  if (!ready) return <DataState title="Loading" loading />;
  if (!teamId) {
    return (
      <DataState title="Connect your team to see your mini-leagues">
        Your leagues come from your public FPL Team ID. <Link className="link" href="/">Connect a team</Link>
      </DataState>
    );
  }

  const me = data?.standings.find((row) => row.is_you);
  const leader = data?.standings[0];
  const rivalRow = data?.standings.find((row) => row.team_id === rivalId);
  const nextAbove = data && me ? [...data.standings].reverse().find((row) => (row.rank ?? 0) < (me.rank ?? 0)) : undefined;

  return (
    <div className="stack">
      <header className="page-head">
        <div>
          <span className="eyebrow">Mini-leagues</span>
          <h1>{data?.name ?? "Your leagues"}</h1>
          <p className="page-lede">Where you stand, which players your rivals rely on, and where a duel is decided. Squads are the latest public ones: FPL shows nobody&apos;s team for the next deadline until it has passed.</p>
        </div>
        {list.length > 1 ? (
          <label className="select-label">
            League
            <select className="select" value={activeLeague ?? ""} onChange={(event) => setLeagueId(Number(event.target.value))}>
              {list.map((item) => <option key={item.league_id} value={item.league_id}>{item.name} ({item.managers ?? "?"})</option>)}
            </select>
          </label>
        ) : null}
      </header>

      {leagues.loading && !list.length ? <Skeleton lines={4} /> : leagues.error ? (
        <DataState tone="error" title="Leagues unavailable" action={<button className="btn btn-sm" onClick={leagues.reload}>Try again</button>}>{leagues.error}</DataState>
      ) : !list.length ? (
        <DataState tone="unavailable" title="No mini-leagues">This team is only in public leagues (overall, country, club). Join or create a private league in FPL to compare with friends.</DataState>
      ) : league.loading && !data ? <Skeleton lines={8} /> : league.error ? (
        <DataState tone="error" title="League unavailable" action={<button className="btn btn-sm" onClick={league.reload}>Try again</button>}>{league.error}</DataState>
      ) : data ? (
        <>
          <div className="grid-3 league-summary">
            <Card title="Your rank" source="official"><strong className="num big">{me?.rank ?? "—"}<small className="faint"> / {data.managers}</small></strong></Card>
            <Card title="Gap to leader" source="official"><strong className="num big">{leader && me ? (leader.is_you ? "Leading" : `${leader.total! - me.total!} pts`) : "—"}</strong></Card>
            <Card title="Gap to next place" source="official"><strong className="num big">{nextAbove && me ? `${nextAbove.total! - me.total!} pts` : "—"}</strong></Card>
          </div>

          <Card title="Standings" icon={<Trophy size={16} />} source="official">
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">Team</th>
                    <th scope="col" className="num">GW{data.event ?? ""}</th>
                    <th scope="col" className="num">Total</th>
                    <th scope="col" className="num">Vs you</th>
                    <th scope="col"><span className="sr-only">Compare</span></th>
                  </tr>
                </thead>
                <tbody>
                  {data.standings.map((row) => (
                    <tr key={row.team_id} className={row.is_you ? "is-owned" : undefined}>
                      <td className="num">{row.rank}</td>
                      <td><b>{row.team_name}</b> <small className="faint">{row.manager ?? ""}{row.active_chip ? ` · ${row.active_chip}` : ""}</small></td>
                      <td className="num">{row.event_points ?? "—"}</td>
                      <td className="num">{row.total ?? "—"}</td>
                      <td className={`num${row.gap_to_you > 0 ? " tone-neg" : row.gap_to_you < 0 ? " tone-pos" : ""}`}>{row.is_you ? "You" : signedGap(row.gap_to_you)}</td>
                      <td>{row.is_you ? null : <button type="button" className="btn btn-sm" aria-pressed={rivalId === row.team_id} onClick={() => activeLeague && setRival({ league: activeLeague, id: row.team_id })}>Compare</button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {rivalId && rivalRow ? <RivalCompare leagueId={data.league_id} rivalId={rivalId} teamId={teamId} rivalName={rivalRow.team_name} /> : null}

          <Card title="Who the league relies on" eyebrow={`Effective ownership · ${data.analysed_managers} managers`} icon={<Users size={16} />} source={["official", "derived"]}
            action={<Segmented label="Filter players" value={filter} onChange={(value) => setFilter(value as PlayerFilter)} options={[{ value: "all", label: "Top 25" }, { value: "threats", label: "Threats" }, { value: "differentials", label: "Your differentials" }]} />}>
            {players.length ? (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">Player</th>
                      <th scope="col" className="num">Owned</th>
                      <th scope="col" className="num">Captained</th>
                      <th scope="col" className="num" title="Effective ownership among your rivals (you excluded)">Rivals&apos; EO</th>
                      <th scope="col">You</th>
                      <th scope="col" className="num">xP next</th>
                    </tr>
                  </thead>
                  <tbody>
                    {players.map((player) => (
                      <tr key={player.player_id} className={player.you ? "is-owned" : undefined}>
                        <td>
                          <PlayerName player={player} />
                          {player.role === "THREAT" ? <span className="pill pill-warn"> Threat</span> : player.role === "DIFFERENTIAL" ? <span className="pill pill-pos"> Differential</span> : null}
                        </td>
                        <td className="num">{player.owners}/{data.analysed_managers}</td>
                        <td className="num">{player.captains}</td>
                        <td className="num">{fixed(player.rival_eo, 0)}%</td>
                        <td><RoleTag role={player.you} /></td>
                        <td className="num">{player.next_gw_points != null ? fixed(player.next_gw_points) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <p className="faint">{filter === "threats" ? "No player that most rivals start is missing from your team." : filter === "differentials" ? "None of your starters is rare among your rivals." : "No squads available yet."}</p>}
            <p className="card-note">
              EO counts a starter once, a captain twice (three times with Triple Captain) and a bench player not at all, so it shows how many points a player moves for the league. The column shows it among your rivals only.
              A <b>threat</b> is a player at least {data.thresholds.threat_eo}% of your rivals&apos; EO that you do not own: when he scores, you lose ground.
              A <b>differential</b> is a starter of yours under {data.thresholds.differential_eo}% rival EO: when he scores, you gain.
              {data.managers > data.analysed_managers ? ` Only the top ${data.analysed_managers} managers are analysed.` : ""}
            </p>
            <p className="card-note">{data.basis}</p>
          </Card>
        </>
      ) : null}
    </div>
  );
}
