import type { DashboardData, LiveEvent, LiveFixture } from "@/lib/contracts";
import { validateStartingXI } from "@/lib/fpl/rules";
import type { SquadPlayer } from "@/lib/model/squad";

export type LiveView = {
  event: number;
  status: string;
  /** Official live total for active picks. Null when the feed is incomplete. */
  points: number | null;
  captain: SquadPlayer | null;
  captainContribution: number | null;
  finished: number;
  playing: number;
  remaining: number;
  noFixture: number;
  benchPoints: number | null;
  /** Same-event model expectation for official active picks, including chip multipliers. */
  projectedXI: number | null;
  fixtures: LiveFixture[];
  events: LiveEvent[];
  autoSubWatch: Array<{ out: SquadPlayer; in: SquadPlayer | null }>;
  yetToPlay: SquadPlayer[];
  topContributors: SquadPlayer[];
};

export function buildLiveView(data: DashboardData, squad: SquadPlayer[], predictionEvent = data.team.prediction_event): LiveView | null {
  const live = data.live;
  if (!live) return null;
  const starters = squad.filter((player) => player.isStarter);
  const bench = squad.filter((player) => !player.isStarter).sort((left, right) => left.slot - right.slot);
  const activePicks = squad.filter((player) => player.multiplier != null && player.multiplier > 0);
  const contributions = activePicks.map((player) => player.liveContribution);
  const multipliersKnown = squad.length > 0 && squad.every((player) => player.multiplier != null);
  const summed = multipliersKnown && activePicks.length > 0 && contributions.every((value) => value != null)
    ? contributions.reduce<number>((total, value) => total + (value ?? 0), 0)
    : null;
  const captain = activePicks.find((player) => (player.multiplier ?? 0) > 1) ?? squad.find((player) => player.isCaptain) ?? null;
  const benchValues = bench.map((player) => player.livePoints);
  const projected = predictionEvent === live.current_event && activePicks.length > 0
    && multipliersKnown
    && activePicks.every((player) => player.xp != null)
    ? activePicks.reduce((total, player) => total + (player.xp ?? 0) * (player.multiplier ?? 0), 0)
    : null;

  const ownedTeams = new Set(squad.map((player) => player.teamId).filter((id): id is number => id != null));

  // Derived auto-sub watch: a starter whose fixtures are all finished with zero minutes.
  const autoSubWatch: LiveView["autoSubWatch"] = [];
  const used = new Set<number>();
  let lineup = [...starters];
  for (const starter of starters) {
    if (starter.fixtureState !== "finished" || starter.liveMinutes !== 0) continue;
    const replacement = bench.find((candidate) => {
      if (used.has(candidate.id)) return false;
      if (candidate.fixtureState === "finished" && candidate.liveMinutes === 0) return false;
      if ((candidate.position === "GKP") !== (starter.position === "GKP")) return false;
      const next = lineup.map((player) => player.id === starter.id ? candidate : player);
      return validateStartingXI(next).valid;
    }) ?? null;
    if (replacement) {
      used.add(replacement.id);
      lineup = lineup.map((player) => player.id === starter.id ? replacement : player);
    }
    autoSubWatch.push({ out: starter, in: replacement });
  }

  return {
    event: live.current_event,
    status: live.status,
    points: live.summary?.live_points ?? summed,
    captain,
    captainContribution: live.summary?.captain_contribution ?? captain?.liveContribution ?? null,
    finished: live.summary?.players_finished ?? activePicks.filter((player) => player.fixtureState === "finished").length,
    playing: live.summary?.players_live ?? activePicks.filter((player) => player.fixtureState === "live").length,
    remaining: live.summary?.players_remaining ?? activePicks.filter((player) => player.fixtureState === "upcoming").length,
    noFixture: live.summary?.players_without_fixture ?? activePicks.filter((player) => player.fixtureState === "none").length,
    benchPoints: benchValues.every((value) => value != null) ? benchValues.reduce<number>((total, value) => total + (value ?? 0), 0) : null,
    projectedXI: projected,
    fixtures: (ownedTeams.size ? (live.fixtures ?? []).filter((fixture) => ownedTeams.has(fixture.home_team_id) || ownedTeams.has(fixture.away_team_id)) : [...(live.fixtures ?? [])]).sort((left, right) => {
      const rank = (fixture: LiveFixture) => fixture.started && !fixture.finished ? 0 : !fixture.started ? 1 : 2;
      return rank(left) - rank(right) || String(left.kickoff_time ?? "").localeCompare(String(right.kickoff_time ?? ""));
    }),
    events: live.events ?? [],
    autoSubWatch,
    yetToPlay: activePicks.filter((player) => player.fixtureState === "upcoming" || player.fixtureState === "live"),
    topContributors: [...activePicks]
      .filter((player) => player.liveContribution != null)
      .sort((left, right) => (right.liveContribution ?? 0) - (left.liveContribution ?? 0))
      .slice(0, 3),
  };
}
