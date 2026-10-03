import type {
  DashboardData,
  DecisionPlayer,
  HorizonGameweek,
  LiveFixture,
  LivePick,
  SquadHealthPlayer,
  TeamPick,
} from "@/lib/contracts";
import { normalizePosition, type Position } from "@/lib/fpl/rules";

export type FixtureState = "finished" | "live" | "upcoming" | "none" | "unknown";

export type RiskLabel = "LOW" | "MEDIUM" | "HIGH" | "VERY_HIGH";

/**
 * One owned player with official, model and live facts merged by FPL id.
 * Every optional value is `null` when its source did not provide it.
 */
export type SquadPlayer = {
  id: number;
  name: string;
  position: Position;
  team: string;
  teamShort: string;
  teamId: number | null;
  slot: number;
  isStarter: boolean;
  isCaptain: boolean;
  isVice: boolean;
  multiplier: number | null;
  // Official
  price: number | null;
  sellingPrice: number | null;
  form: number | null;
  ownership: number | null;
  seasonPoints: number | null;
  starts: number | null;
  goals: number | null;
  assists: number | null;
  bonus: number | null;
  xg: number | null;
  xa: number | null;
  ict: number | null;
  status: string | null;
  chance: number | null;
  news: string | null;
  // Model
  xp: number | null;
  xmins: number | null;
  startProbability: number | null;
  modelAvailability: string | null;
  rotationRisk: string | null;
  opponent: string | null;
  home: boolean | null;
  difficulty: number | null;
  risk: { score: number; label: RiskLabel } | null;
  horizon: HorizonGameweek[];
  horizonTotal: number | null;
  // Live
  livePoints: number | null;
  liveContribution: number | null;
  liveMinutes: number | null;
  liveBps: number | null;
  fixtureState: FixtureState;
  liveFixture: LiveFixture | null;
};

const num = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

function fixtureStateFor(teamId: number | null, fixtures: LiveFixture[] | undefined): { state: FixtureState; fixture: LiveFixture | null } {
  if (!fixtures) return { state: "unknown", fixture: null };
  if (teamId == null) return { state: "unknown", fixture: null };
  const matches = fixtures.filter((fixture) => fixture.home_team_id === teamId || fixture.away_team_id === teamId);
  if (!matches.length) return { state: "none", fixture: null };
  const live = matches.find((fixture) => fixture.started && !fixture.finished);
  if (live) return { state: "live", fixture: live };
  const upcoming = matches.find((fixture) => !fixture.started);
  if (upcoming) return { state: "upcoming", fixture: upcoming };
  return { state: "finished", fixture: matches[matches.length - 1] };
}

export function buildSquad(data: DashboardData): SquadPlayer[] {
  const decision = data.decision;
  const intelligence = decision?.intelligence;
  const modelById = new Map<number, DecisionPlayer>((decision?.current_team?.players ?? []).map((player) => [player.player_id, player]));
  const healthById = new Map<number, SquadHealthPlayer>((intelligence?.squad_health.players ?? []).map((player) => [player.player_id, player]));
  const horizonById = new Map((intelligence?.horizon.team_player_projections ?? []).map((player) => [player.player_id, player]));
  const liveById = new Map<number, LivePick>((data.live?.picks ?? []).map((pick) => [pick.player_id, pick]));
  const liveFixtures = data.live ? data.live.fixtures ?? [] : undefined;

  return data.team.picks
    .map((pick: TeamPick): SquadPlayer | null => {
      const position = normalizePosition(pick.position_name);
      if (!position) return null;
      const model = modelById.get(pick.player_id);
      const health = healthById.get(pick.player_id);
      const horizon = horizonById.get(pick.player_id);
      const live = liveById.get(pick.player_id);
      const teamId = num(live?.team_id) ?? num(pick.team_id);
      const fixture = fixtureStateFor(teamId, liveFixtures);
      const multiplier = num(live?.multiplier) ?? num(pick.multiplier);
      const livePoints = live ? num(live.event_points) : null;
      return {
        id: pick.player_id,
        name: pick.name,
        position,
        team: pick.team,
        teamShort: pick.team_short ?? pick.team.slice(0, 3).toUpperCase(),
        teamId,
        slot: pick.position,
        isStarter: pick.position <= 11,
        isCaptain: Boolean(pick.is_captain),
        isVice: Boolean(pick.is_vice_captain),
        multiplier,
        price: num(pick.price),
        sellingPrice: num(pick.selling_price),
        form: num(pick.form),
        ownership: num(pick.ownership),
        seasonPoints: num(pick.season_points),
        starts: num(pick.starts),
        goals: num(pick.season_goals),
        assists: num(pick.season_assists),
        bonus: num(pick.season_bonus),
        xg: num(pick.expected_goals),
        xa: num(pick.expected_assists),
        ict: num(pick.ict_index),
        status: pick.status ?? null,
        chance: num(pick.chance_of_playing_next_round),
        news: pick.news || null,
        xp: num(model?.predicted_points) ?? num(pick.prediction?.predicted_points),
        xmins: num(health?.xmins) ?? num(model?.xmins) ?? num(pick.prediction?.xmins),
        startProbability: num(health?.start_probability) ?? num(model?.start_probability) ?? num(pick.prediction?.start_probability),
        modelAvailability: (health?.availability ?? model?.availability ?? (typeof pick.prediction?.availability === "string" ? pick.prediction.availability : null)) || null,
        rotationRisk: health?.rotation_risk || model?.rotation_risk || null,
        opponent: model?.opponent ?? pick.prediction?.opponent ?? null,
        home: typeof model?.home === "boolean" ? model.home : typeof pick.prediction?.home === "boolean" ? pick.prediction.home : null,
        difficulty: num(model?.difficulty) ?? num(pick.prediction?.difficulty),
        risk: health ? { score: health.score, label: (health.label as RiskLabel) } : null,
        horizon: horizon?.gameweeks ?? [],
        horizonTotal: num(horizon?.minutes_adjusted_points) ?? num(horizon?.predicted_points),
        livePoints,
        liveContribution: num(live?.multiplied_points) ?? (livePoints != null && multiplier != null ? livePoints * multiplier : null),
        liveMinutes: live ? num(live.live_minutes) : null,
        liveBps: live ? num(live.live_bps) : null,
        fixtureState: fixture.state,
        liveFixture: fixture.fixture,
      };
    })
    .filter((player): player is SquadPlayer => player != null)
    .sort((left, right) => left.slot - right.slot);
}

export function startersOf(squad: SquadPlayer[]): SquadPlayer[] {
  return squad.filter((player) => player.isStarter);
}

export function benchOf(squad: SquadPlayer[]): SquadPlayer[] {
  return squad.filter((player) => !player.isStarter).sort((left, right) => left.slot - right.slot);
}

export function isFlagged(player: Pick<SquadPlayer, "status" | "modelAvailability" | "risk">): boolean {
  const status = String(player.status ?? "a").toLowerCase();
  if (status !== "a" && status !== "") return true;
  if (player.modelAvailability && player.modelAvailability.toUpperCase() !== "AVAILABLE") return true;
  return player.risk?.label === "HIGH" || player.risk?.label === "VERY_HIGH";
}
