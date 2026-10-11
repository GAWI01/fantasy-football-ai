"use client";

import { Crown, Radar, Swords, Trophy } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { useTeam } from "@/app/providers/TeamProvider";
import { PlayerChip } from "@/components/player/PlayerChip";
import { DataState } from "@/components/states/DataState";
import { Card, Meter, Skeleton, SourceBadge } from "@/components/ui/primitives";
import { fixed } from "@/lib/format";
import type { LeaguePlayer, LeagueStanding, RivalPlayer } from "@/lib/contracts";
import { useLeague, useLeagues, useRival } from "@/lib/hooks/data";

function ordinal(value: number | null | undefined): string {
  if (value == null) return "—";
  const tens = value % 100;
  const suffix = tens >= 11 && tens <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[value % 10] ?? "th";
  return `${value}${suffix}`;
}

function gapLabel(row: LeagueStanding): string {
  if (row.is_you) return "You";
  if (row.gap_to_you === 0) return "Level";
  return row.gap_to_you > 0 ? `+${row.gap_to_you}` : `${row.gap_to_you}`;
}

/** The standings as a race: bar length is points relative to the leader. */
function Race({ standings, selected, onSelect }: { standings: LeagueStanding[]; selected: number | null; onSelect: (teamId: number) => void }) {
  const leader = Math.max(1, ...standings.map((row) => row.total ?? 0));
  const lowest = Math.min(...standings.map((row) => row.total ?? 0));
  // Start the bars a little below the last place so the gaps are visible.
  const floor = Math.max(0, lowest - (leader - lowest) * 0.6);
  return (
    <ol className="race" aria-label="League standings">
      {standings.map((row) => {
        const share = ((row.total ?? 0) - floor) / Math.max(1, leader - floor);
        const content = (
          <>
            <span className="race-rank num">{row.rank}</span>
            <span className="race-name">
              <strong>{row.team_name}</strong>
              <small>{row.active_chip ? `${row.active_chip} · ` : ""}GW {row.event_points ?? "—"}</small>
            </span>
            <span className="race-track" aria-hidden="true"><i style={{ width: `${Math.max(4, share * 100)}%` }} /></span>
            <span className="race-total num">{row.total ?? "—"}</span>
            <span className={`race-gap num${row.is_you ? " is-you" : row.gap_to_you > 0 ? " is-ahead" : row.gap_to_you < 0 ? " is-behind" : ""}`}>{gapLabel(row)}</span>
          </>
        );
        return (
          <li key={row.team_id}>
            {row.is_you ? (
              <div className="race-row is-you">{content}</div>
            ) : (
              <button type="button" className={`race-row${selected === row.team_id ? " is-selected" : ""}`} aria-pressed={selected === row.team_id} onClick={() => onSelect(row.team_id)} aria-label={`Compare with ${row.team_name}`}>
                {content}
              </button>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function DuelPlayers({ title, players, tone }: { title: string; players: RivalPlayer[]; tone: "you" | "rival" }) {
  const ordered = [...players].sort((left, right) => Number(left.role === "BENCH") - Number(right.role === "BENCH") || Number(right.role === "CAPTAIN") - Number(left.role === "CAPTAIN"));
  return (
    <div className={`duel-col duel-${tone}`}>
      <span className="eyebrow">{title}</span>
      {ordered.length ? (
        <ul className="duel-list">
          {ordered.map((player) => (
            <li key={player.player_id} className={player.role === "BENCH" ? "is-bench" : undefined}>
              <PlayerChip
                name={player.name}
                teamShort={player.team_short}
                position={player.position}
                size={30}
                badge={player.role === "CAPTAIN" ? "C" : undefined}
                meta={player.role === "BENCH" ? "Bench" : `${player.position ?? ""} · ${player.team_short}`}
                end={player.next_gw_points != null && player.role !== "BENCH" ? <span className="num">{fixed(player.next_gw_points)}</span> : null}
              />
            </li>
          ))}
        </ul>
      ) : <p className="faint">No unique players</p>}
    </div>
  );
}

function Duel({ leagueId, rival, me, teamId }: { leagueId: number; rival: LeagueStanding; me: LeagueStanding; teamId: string }) {
  const resource = useRival(leagueId, rival.team_id, teamId);
  const data = resource.data?.data;
  const captainOf = (players: RivalPlayer[] | undefined) => players?.find((player) => player.role === "CAPTAIN");
  const myCaptain = data ? captainOf(data.only_you) ?? data.shared.find((player) => player.role === "CAPTAIN") : undefined;
  const rivalCaptain = data ? captainOf(data.only_rival) ?? data.shared.find((player) => player.rival_role === "CAPTAIN") : undefined;
  const youXp = data?.unique_next_gw_points.you ?? null;
  const rivalXp = data?.unique_next_gw_points.rival ?? null;
  const split = youXp != null && rivalXp != null && youXp + rivalXp > 0 ? youXp / (youXp + rivalXp) : null;

  return (
    <Card title={`You vs ${rival.team_name}`} eyebrow="Head to head" icon={<Swords size={16} />} source="official" className="duel-card">
      <div className="duel-score">
        <div><small>You</small><strong className="num">{me.total ?? "—"}</strong></div>
        <span className={`duel-gap num${rival.gap_to_you > 0 ? " is-ahead" : rival.gap_to_you < 0 ? " is-behind" : ""}`}>
          {rival.gap_to_you === 0 ? "Level" : rival.gap_to_you > 0 ? `${rival.gap_to_you} behind` : `${-rival.gap_to_you} ahead`}
        </span>
        <div><small>{rival.team_name}</small><strong className="num">{rival.total ?? "—"}</strong></div>
      </div>

      {resource.loading && !data ? <Skeleton lines={5} /> : resource.error ? (
        <DataState tone="error" compact title="Comparison unavailable">{resource.error}</DataState>
      ) : data ? (
        <>
          <div className="duel-captains">
            <div>
              <span className="eyebrow"><Crown size={12} aria-hidden="true" /> Your captain</span>
              {myCaptain ? <PlayerChip name={myCaptain.name} teamShort={myCaptain.team_short} position={myCaptain.position} size={30} badge="C" /> : <span className="faint">—</span>}
            </div>
            <span className={`pill ${data.same_captain ? "pill-pos" : "pill-warn"}`}>{data.same_captain ? "Same captain" : "Different captains"}</span>
            <div className="duel-captain-rival">
              <span className="eyebrow"><Crown size={12} aria-hidden="true" /> Their captain</span>
              {rivalCaptain ? <PlayerChip name={rivalCaptain.name} teamShort={rivalCaptain.team_short} position={rivalCaptain.position} size={30} badge="C" /> : <span className="faint">—</span>}
            </div>
          </div>

          {split != null ? (
            <div className="duel-split" aria-label={`Unique starters next Gameweek: you ${fixed(youXp)} xP, ${rival.team_name} ${fixed(rivalXp)} xP`}>
              <div className="row"><b className="num">{fixed(youXp)} xP</b><span className="spacer" /><small className="faint">Players only one of you starts · next GW</small><span className="spacer" /><b className="num">{fixed(rivalXp)} xP</b></div>
              <div className="duel-split-bar" aria-hidden="true"><i className="is-you" style={{ width: `${split * 100}%` }} /><i className="is-rival" style={{ width: `${(1 - split) * 100}%` }} /></div>
            </div>
          ) : null}

          <div className="duel-grid">
            <DuelPlayers title="Only you" players={data.only_you} tone="you" />
            <DuelPlayers title={`Only ${rival.team_name}`} players={data.only_rival} tone="rival" />
          </div>
          {data.shared.length ? (
            <p className="duel-shared"><span className="eyebrow">You both have</span> {data.shared.map((player) => player.name).join(" · ")}</p>
          ) : null}
          <p className="card-note">{data.basis}</p>
        </>
      ) : null}
    </Card>
  );
}

function RadarList({ title, hint, players, empty, tone }: { title: string; hint: string; players: LeaguePlayer[]; empty: string; tone: "warn" | "pos" }) {
  return (
    <div className="radar-col">
      <div className="radar-head"><strong>{title}</strong><small className="faint">{hint}</small></div>
      {players.length ? (
        <ul className="radar-list">
          {players.map((player) => (
            <li key={player.player_id}>
              <PlayerChip name={player.name} teamShort={player.team_short} position={player.position} size={30}
                meta={player.captains ? `Captained by ${player.captains}` : `${player.position ?? ""} · ${player.team_short}`} />
              {player.rival_eo > 0 ? (
                <span className="radar-eo">
                  <Meter value={Math.min(1, player.rival_eo / 100)} tone={tone} label={`${player.name} rivals' effective ownership`} />
                  <b className="num">{fixed(player.rival_eo, 0)}%</b>
                </span>
              ) : <span className="radar-only">Only you</span>}
            </li>
          ))}
        </ul>
      ) : <p className="faint">{empty}</p>}
    </div>
  );
}

/** Mini-leagues: the race, a head-to-head with one rival, and who the league relies on. */
export function LeagueWorkspace() {
  const { ready, teamId } = useTeam();
  const leagues = useLeagues(teamId);
  const list = useMemo(() => leagues.data?.data.leagues ?? [], [leagues.data]);
  const [leagueId, setLeagueId] = useState<number | null>(null);
  // The chosen rival belongs to one league; switching league clears it.
  const [rival, setRival] = useState<{ league: number; id: number } | null>(null);
  const [showAll, setShowAll] = useState(false);

  // Default to the smallest league: the one with friends, not a public code league.
  const activeLeague = leagueId ?? [...list].sort((left, right) => (left.managers ?? 1e9) - (right.managers ?? 1e9))[0]?.league_id ?? null;
  const league = useLeague(activeLeague, teamId);
  const data = league.data?.data;

  const me = data?.standings.find((row) => row.is_you);
  const leader = data?.standings[0];
  const above = data && me ? [...data.standings].reverse().find((row) => (row.rank ?? 0) < (me.rank ?? 0)) : undefined;
  const below = data && me ? data.standings.find((row) => (row.rank ?? 0) > (me.rank ?? 0)) : undefined;
  // Default duel: the manager directly above you (or below, when you lead).
  const rivalId = rival && rival.league === activeLeague ? rival.id : (above ?? below)?.team_id ?? null;
  const rivalRow = data?.standings.find((row) => row.team_id === rivalId);
  const threats = useMemo(() => (data?.players ?? []).filter((player) => player.role === "THREAT").slice(0, 8), [data]);
  const differentials = useMemo(() => (data?.players ?? []).filter((player) => player.role === "DIFFERENTIAL").slice(0, 8), [data]);

  if (!ready) return <DataState title="Loading" loading />;
  if (!teamId) {
    return (
      <DataState title="Connect your team to see your mini-leagues">
        Your leagues come from your public FPL Team ID. <Link className="link" href="/">Connect a team</Link>
      </DataState>
    );
  }

  return (
    <div className="stack league-page">
      <header className="page-head">
        <div>
          <span className="eyebrow">Mini-leagues</span>
          <h1>{data?.name ?? "Your leagues"}</h1>
          {data && me ? (
            <p className="league-status">
              You are <b>{ordinal(me.rank)}</b> of {data.managers}
              {leader && !leader.is_you ? <> · <b className="tone-neg">{(leader.total ?? 0) - (me.total ?? 0)}</b> behind the leader</> : <> · <b className="tone-pos">leading</b></>}
              {above && above.team_id !== leader?.team_id ? <> · <b>{(above.total ?? 0) - (me.total ?? 0)}</b> to {ordinal(above.rank)}</> : null}
            </p>
          ) : null}
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
      ) : data && me ? (
        <div className="league-grid">
          <Card title="The race" eyebrow="Tap a manager to compare" icon={<Trophy size={16} />} source="official" className="league-race">
            <Race standings={data.standings} selected={rivalId} onSelect={(id) => activeLeague && setRival({ league: activeLeague, id })} />
          </Card>

          {rivalRow ? <Duel leagueId={data.league_id} rival={rivalRow} me={me} teamId={teamId} /> : null}

          <Card title="League radar" eyebrow={`Squads of ${data.analysed_managers} managers · GW${data.event ?? "—"}`} icon={<Radar size={16} />} source={["official", "derived"]} className="league-radar">
            <div className="radar-grid">
              <RadarList title="They have, you don't" hint="When they score, you lose ground" players={threats} tone="warn"
                empty="You own every player most of your rivals rely on." />
              <RadarList title="Your edge" hint="Your starters few rivals have" players={differentials} tone="pos"
                empty="None of your starters is rare in this league." />
            </div>
            <button type="button" className="link radar-toggle" aria-expanded={showAll} onClick={() => setShowAll((value) => !value)}>
              {showAll ? "Hide full ownership" : "Show full ownership"}
            </button>
            {showAll ? (
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th scope="col">Player</th><th scope="col" className="num">Owned</th><th scope="col" className="num">Captained</th><th scope="col" className="num">Rivals&apos; EO</th><th scope="col" className="num">You</th></tr></thead>
                  <tbody>
                    {data.players.slice(0, 30).map((player) => (
                      <tr key={player.player_id} className={player.you ? "is-owned" : undefined}>
                        <td>{player.name} <small className="faint">{player.team_short}</small></td>
                        <td className="num">{player.owners}/{data.analysed_managers}</td>
                        <td className="num">{player.captains || "—"}</td>
                        <td className="num">{fixed(player.rival_eo, 0)}%</td>
                        <td className="num">{player.you === "CAPTAIN" ? "C" : player.you === "STARTER" ? "✓" : player.you === "BENCH" ? "Bench" : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            <p className="card-note">
              Rivals&apos; EO: how many of your rivals start a player, a captain counting twice. {data.basis} <SourceBadge kind="official" />
            </p>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
