/**
 * Deterministic, clearly fictional API fixtures for tests and local browser QA.
 * Player names are invented; nothing here is presented to users as real data.
 */
import type {
  DashboardEnvelope,
  DashboardLive,
  DecisionPlayer,
  FixtureMatrixEnvelope,
  FixtureMatrixTeam,
  HorizonPlayer,
  LiveFixture,
  PlayerMarketEnvelope,
  PlayerSummary,
  RankHistoryItem,
  ReviewEnvelope,
  SquadHealthPlayer,
  TeamPick,
} from "@/lib/contracts";

export type FixturePhase = "decision" | "live" | "settled";

export const CLUBS: Array<[short: string, name: string, strength: number]> = [
  ["ARS", "Arsenal", 5], ["AVL", "Aston Villa", 4], ["BOU", "Bournemouth", 3], ["BRE", "Brentford", 3],
  ["BHA", "Brighton", 3], ["CHE", "Chelsea", 4], ["COV", "Coventry", 2], ["CRY", "Crystal Palace", 3],
  ["EVE", "Everton", 2], ["FUL", "Fulham", 3], ["HUL", "Hull", 2], ["IPS", "Ipswich", 2],
  ["LEE", "Leeds", 2], ["LIV", "Liverpool", 5], ["MCI", "Man City", 5], ["MUN", "Man Utd", 4],
  ["NEW", "Newcastle", 4], ["NFO", "Nott'm Forest", 3], ["SUN", "Sunderland", 2], ["TOT", "Spurs", 4],
];

const clubIndex = new Map(CLUBS.map(([short], index) => [short, index]));
const clubId = (short: string) => (clubIndex.get(short) ?? 0) + 1;
const clubName = (short: string) => CLUBS[clubIndex.get(short) ?? 0][1];
const strength = (short: string) => CLUBS[clubIndex.get(short) ?? 0][2];

/** Circle-method round robin: a stable home/away pairing for every Gameweek. */
export function pairings(event: number): Array<[home: string, away: string]> {
  const teams = CLUBS.map(([short]) => short);
  const fixed = teams[0];
  const rotating = teams.slice(1);
  const shift = (event - 1) % rotating.length;
  const order = [fixed, ...rotating.slice(shift), ...rotating.slice(0, shift)];
  const pairs: Array<[string, string]> = [];
  for (let index = 0; index < order.length / 2; index += 1) {
    const left = order[index];
    const right = order[order.length - 1 - index];
    pairs.push((event + index) % 2 === 0 ? [left, right] : [right, left]);
  }
  return pairs;
}

function opponentFor(short: string, event: number): { opponent: string; home: boolean; difficulty: number } {
  const pair = pairings(event).find(([home, away]) => home === short || away === short)!;
  const home = pair[0] === short;
  const opponent = home ? pair[1] : pair[0];
  return { opponent, home, difficulty: Math.max(1, Math.min(5, strength(opponent) + (home ? 0 : 1) - 1)) };
}

type SquadSeed = [id: number, name: string, position: "GKP" | "DEF" | "MID" | "FWD", club: string, price: number, xp: number, xmins: number, status?: string, chance?: number | null, news?: string];

/** 15 invented players: 11 starters in a 4-4-2 then GK, DEF, MID, FWD on the bench. */
export const SQUAD: SquadSeed[] = [
  [101, "Okafor", "GKP", "ARS", 5.5, 4.4, 90],
  [102, "Lindqvist", "DEF", "LIV", 6.5, 5.3, 88],
  [103, "Mendes", "DEF", "ARS", 6.0, 5.1, 86],
  [104, "Hale", "DEF", "NEW", 5.0, 3.9, 84],
  [105, "Varga", "DEF", "CHE", 5.5, 3.7, 70, "d", 75, "Knock - 75% chance of playing"],
  [106, "Sato", "MID", "MCI", 9.5, 6.4, 82],
  [107, "Duarte", "MID", "LIV", 13.0, 8.1, 87],
  [108, "Bramwell", "MID", "AVL", 7.5, 4.6, 80],
  [109, "Ekström", "MID", "BHA", 6.5, 3.2, 62],
  [110, "Kovač", "FWD", "MCI", 14.5, 7.6, 84],
  [111, "Adeyemi", "FWD", "CHE", 8.0, 4.9, 78],
  [112, "Pryce", "GKP", "IPS", 4.0, 2.6, 0],
  [113, "Moreau", "DEF", "BOU", 4.5, 2.9, 66],
  [114, "Tanaka", "MID", "FUL", 5.0, 2.4, 40],
  [115, "Whitlock", "FWD", "SUN", 4.5, 1.9, 30],
];

/** Market-only players, including transfer targets 201 and 202. */
const MARKET_EXTRA: SquadSeed[] = [
  [201, "Castellano", "MID", "TOT", 7.0, 5.9, 86],
  [202, "Brennan", "FWD", "NEW", 7.5, 5.6, 85],
  [203, "Ivanova", "DEF", "MCI", 6.0, 4.8, 88],
  [204, "Nakamura", "MID", "ARS", 10.0, 6.9, 85],
  [205, "Fontaine", "GKP", "LIV", 5.5, 4.1, 90],
  [206, "Oduya", "FWD", "AVL", 9.0, 5.8, 82],
  [207, "Rask", "DEF", "TOT", 5.0, 3.8, 80, "i", 0, "Hamstring injury - expected back in three weeks"],
  [208, "Mbeki", "MID", "LEE", 5.5, 3.5, 76],
];

export const TARGET_EVENT = 7;

function pick(seed: SquadSeed, slot: number): TeamPick {
  const [id, name, position, club, price, , , status = "a", chance = null, news = ""] = seed;
  return {
    player_id: id,
    position: slot,
    multiplier: slot <= 11 ? (id === 107 ? 2 : 1) : 0,
    is_captain: id === 107,
    is_vice_captain: id === 110,
    name,
    position_name: position === "GKP" ? "GK" : position,
    team: clubName(club),
    team_short: club,
    team_id: clubId(club),
    price,
    selling_price: price - 0.1,
    status,
    chance_of_playing_next_round: chance,
    news,
    form: Math.round((seed[5] - 0.6) * 10) / 10,
    ownership: Math.round(price * 2.7 * 10) / 10,
    season_points: Math.round(seed[5] * 6),
    starts: 6,
    season_goals: position === "FWD" ? 4 : position === "MID" ? 2 : 0,
    season_assists: position === "MID" ? 3 : 1,
    season_bonus: 5,
    expected_goals: position === "FWD" ? 3.9 : 1.2,
    expected_assists: 1.4,
    ict_index: Math.round(seed[5] * 60) / 10,
  };
}

function decisionPlayer(seed: SquadSeed, event = TARGET_EVENT): DecisionPlayer {
  const [id, name, position, club, price, xp, xmins] = seed;
  const fixture = opponentFor(club, event);
  return {
    player_id: id,
    name,
    position,
    team: clubName(club),
    price,
    predicted_points: xp,
    xmins,
    start_probability: Math.min(0.98, xmins / 90),
    availability: seed[7] === "d" ? "DOUBTFUL" : "AVAILABLE",
    difficulty: fixture.difficulty,
    captain_score: Math.round(xp * (xmins / 90) * 100) / 100,
    opponent: clubName(fixture.opponent),
    home: fixture.home,
    rotation_risk: xmins < 70 ? "MEDIUM" : "LOW",
  };
}

function horizon(seed: SquadSeed): HorizonPlayer {
  const [id, , , club, , xp, xmins] = seed;
  const gameweeks = [0, 1, 2, 3, 4].map((offset) => {
    const event = TARGET_EVENT + offset;
    const fixture = opponentFor(club, event);
    const scale = offset === 0 ? 1 : 1 + (3 - fixture.difficulty) * 0.08;
    const points = Math.round(xp * scale * 10) / 10;
    return {
      gameweek: event,
      horizon_index: offset,
      predicted_points: points,
      minutes_adjusted_points: Math.round(points * Math.min(1, xmins / 85) * 10) / 10,
      uncertainty: Math.round((0.6 + offset * 0.35) * 10) / 10,
      opponent: clubName(fixture.opponent),
      home: fixture.home,
      difficulty: fixture.difficulty,
      projection_method: offset === 0 ? "native_model" : "fixture_scaled",
      fixture_count: 1,
    };
  });
  const total = gameweeks.reduce((sum, gameweek) => sum + gameweek.predicted_points, 0);
  return {
    player_id: id,
    coverage: 1,
    predicted_points: Math.round(total * 10) / 10,
    minutes_adjusted_points: Math.round(gameweeks.reduce((sum, gameweek) => sum + (gameweek.minutes_adjusted_points ?? 0), 0) * 10) / 10,
    gameweeks,
  };
}

function health(seed: SquadSeed): SquadHealthPlayer {
  const xmins = seed[6];
  const score = seed[7] === "d" ? 0.42 : xmins < 50 ? 0.6 : xmins < 70 ? 0.3 : 0.08;
  return { ...decisionPlayer(seed), score, label: score >= 0.55 ? "HIGH" : score >= 0.25 ? "MEDIUM" : "LOW" };
}

function history(event: number): RankHistoryItem[] {
  const ranks = [1_850_000, 1_240_000, 905_000, 1_010_000, 640_000, 512_000, 431_000, 388_000];
  const points = [58, 71, 66, 49, 82, 64, 69, 61];
  let total = 0;
  return Array.from({ length: event }, (_, index) => {
    total += points[index % points.length];
    return {
      event: index + 1,
      points: points[index % points.length],
      total_points: total,
      overall_rank: ranks[index % ranks.length],
      event_rank: 900_000 - index * 40_000,
      bank: 5,
      value: 1012 + index,
      transfers: index === 0 ? 0 : 1,
    };
  });
}

function liveFixtures(event: number, mode: "live" | "finished"): LiveFixture[] {
  return pairings(event).map(([home, away], index) => {
    const finished = mode === "finished" || index < 4;
    const started = finished || index < 7;
    return {
      fixture_id: event * 100 + index,
      home_team_id: clubId(home),
      away_team_id: clubId(away),
      home_team: clubName(home),
      home_team_short: home,
      away_team: clubName(away),
      away_team_short: away,
      home_score: started ? (index + event) % 3 : null,
      away_score: started ? (index * 2 + 1) % 3 : null,
      kickoff_time: `2026-10-0${3 + Math.floor(index / 4)}T${12 + (index % 4) * 2}:30:00Z`,
      started,
      finished,
      minutes: finished ? 90 : started ? 63 : 0,
    };
  });
}

function live(event: number, mode: "live" | "finished"): DashboardLive {
  const fixtures = liveFixtures(event, mode);
  const picks = SQUAD.map((seed, index) => {
    const base = pick(seed, index + 1);
    const teamId = clubId(seed[3]);
    const fixture = fixtures.find((item) => item.home_team_id === teamId || item.away_team_id === teamId);
    const played = Boolean(fixture?.started);
    const points = played ? (seed[0] === 112 ? 0 : Math.max(1, Math.round(seed[5] * (seed[0] % 3 === 0 ? 1.6 : 0.8)))) : 0;
    return {
      ...base,
      event_points: points,
      live_minutes: played ? (seed[0] === 109 ? 0 : fixture?.finished ? 90 : 63) : 0,
      live_bps: played ? points * 4 : 0,
      multiplied_points: points * (base.multiplier ?? 0),
    };
  });
  const starters = picks.slice(0, 11);
  const finishedCount = starters.filter((item) => fixtures.find((fixture) => fixture.home_team_id === item.team_id || fixture.away_team_id === item.team_id)?.finished).length;
  const liveCount = starters.filter((item) => {
    const fixture = fixtures.find((candidate) => candidate.home_team_id === item.team_id || candidate.away_team_id === item.team_id);
    return fixture?.started && !fixture.finished;
  }).length;
  return {
    team_id: 4242,
    current_event: event,
    gameweek_name: `Gameweek ${event}`,
    status: mode === "live" ? "LIVE" : "FINISHED",
    finished: mode === "finished",
    next_event: event + 1,
    next_deadline_time: "2026-10-10T17:30:00Z",
    picks,
    summary: {
      live_points: starters.reduce((sum, item) => sum + (item.multiplied_points ?? 0), 0),
      captain_contribution: picks.find((item) => item.is_captain)?.multiplied_points ?? 0,
      players_finished: finishedCount,
      players_live: liveCount,
      players_remaining: 11 - finishedCount - liveCount,
      players_without_fixture: 0,
    },
    events: [
      { player_id: 107, player_name: "Duarte", team_short: "LIV", event_type: "GOAL", count: 1, active: true, provisional: false },
      { player_id: 106, player_name: "Sato", team_short: "MCI", event_type: "ASSIST", count: 2, active: true, provisional: false },
      { player_id: 110, player_name: "Kovač", team_short: "MCI", event_type: "BONUS", count: 2, active: true, provisional: true },
      { player_id: 105, player_name: "Varga", team_short: "CHE", event_type: "YELLOW_CARD", count: 1, active: true, provisional: false },
    ],
    fixtures,
  };
}

export type DashboardOptions = {
  phase?: FixturePhase;
  verdict?: "TRANSFER" | "HOLD";
  stale?: boolean;
  /** Leave out the decision (model) area, as when projections are missing. */
  noDecision?: boolean;
};

export function makeDashboard({ phase = "decision", verdict = "TRANSFER", stale = false, noDecision = false }: DashboardOptions = {}): DashboardEnvelope {
  const currentEvent = phase === "decision" ? TARGET_EVENT - 1 : TARGET_EVENT;
  const now = "2026-10-03T09:00:00Z";
  const starters = SQUAD.slice(0, 11);
  const xiPoints = Math.round(starters.reduce((sum, seed) => sum + seed[5], 0) * 10) / 10;
  const transfer = { player_out_id: 109, player_out: "Ekström", player_in_id: 201, player_in: "Castellano", price: 7.0, predicted_points: 5.9, gain: 2.7, selling_price: 6.4, position: "MID" };
  const second = { player_out_id: 115, player_out: "Whitlock", player_in_id: 202, player_in: "Brennan", price: 7.5, predicted_points: 5.6, gain: 3.7, selling_price: 4.4, position: "FWD" };
  const decision = noDecision ? null : {
    current_team: { team_id: 4242, name: "Midnight Pressers", bank: 1.4, value: 101.2, transfers: 1, players: SQUAD.map((seed) => decisionPlayer(seed)) },
    starting_xi: { formation: "4-4-2", players: starters.map((seed) => decisionPlayer(seed)), projected_points: xiPoints },
    bench: { players: SQUAD.slice(11).map((seed, index) => ({ ...decisionPlayer(seed), bench_order: index + 1 })) },
    captain: decisionPlayer(SQUAD[6]),
    vice_captain: decisionPlayer(SQUAD[9]),
    transfers: {
      recommended: verdict === "TRANSFER" ? transfer : null,
      recommended_transfers: verdict === "TRANSFER" ? [transfer] : [],
      transfers_used: verdict === "TRANSFER" ? 1 : 0,
      free_transfers: 1,
      hit_cost: 0,
      gross_gain: 2.7,
      net_gain: verdict === "TRANSFER" ? 9.4 : 0,
    },
    intelligence: {
      action: verdict,
      confidence: { score: verdict === "TRANSFER" ? 0.74 : 0.61, label: verdict === "TRANSFER" ? "HIGH" : "MEDIUM", components: { decision_margin: 0.68, minutes_certainty: 0.81, fixture_certainty: 1, signal_agreement: 0.55 } },
      captain_decision: { captain: decisionPlayer(SQUAD[6]), vice_captain: decisionPlayer(SQUAD[9]), alternatives: [decisionPlayer(SQUAD[5]), decisionPlayer(SQUAD[1]), decisionPlayer(MARKET_EXTRA[3])] },
      squad_health: { status: "WATCH", unavailable_count: 0, high_risk_count: 1, average_xmins: 72, players: SQUAD.map(health) },
      horizon: { horizon: 5, gameweeks: [7, 8, 9, 10, 11], coverage: 1, team_projected_points: 271.4, team_player_projections: SQUAD.map(horizon) },
      transfer_strategy: {
        action: verdict,
        current_net_gain: verdict === "TRANSFER" ? 9.4 : 1.1,
        horizon_gain: verdict === "TRANSFER" ? 11.2 : 1.6,
        combined_score: verdict === "TRANSFER" ? 9.4 : 1.1,
        coverage: 1,
        selected_transfers: [transfer],
        alternatives: [
          { transfers: [second], current_net_gain: 6.1, horizon_gain: 8.3, combined_score: 6.1, coverage: 1 },
          { transfers: [transfer, second], current_net_gain: 12.2, horizon_gain: 19.5, combined_score: 12.2, coverage: 1 },
        ],
      },
      chip_advisor: { recommended_chip: null, score: 0.18, alternatives: [{ chip: "BENCH_BOOST", score: 0.18 }] },
      chip_state: { known: true, wildcard_available: true, free_hit_available: true, bench_boost_available: true, triple_captain_available: false, double_gameweek: false, blank_gameweek: false },
      risk_summary: { average_risk: 0.2, high_risk_players: 1, players: [] },
      insights: [
        { type: "TRANSFER", severity: "INFO", reason: "Castellano projects 2.7 more points than Ekström next Gameweek with better minutes security.", evidence: {} },
        { type: "MINUTES_RISK", severity: "WARNING", reason: "Varga is flagged with a knock; the model keeps him in the XI at reduced minutes.", evidence: {} },
      ],
    },
  };
  const liveData = phase === "live" ? live(currentEvent, "live") : phase === "settled" ? live(currentEvent, "finished") : null;
  return {
    data: {
      team: {
        team_id: 4242,
        name: "Midnight Pressers",
        manager_name: "Test Manager",
        bank: 1.4,
        event: currentEvent,
        transfers: 1,
        prediction_event: TARGET_EVENT,
        prediction_file: "fixture_predictions_v1",
        picks: SQUAD.map((seed, index) => pick(seed, index + 1)),
        overall_rank: 431_000,
        event_points: 69,
        event_rank: 660_000,
        total_points: 459,
        value: 101.2,
      },
      live: liveData,
      history: { history: history(phase === "decision" ? currentEvent : currentEvent - 1) },
      fixtures: null,
      players: { players: marketPlayers() },
      decision,
    },
    meta: {
      event: currentEvent,
      current_event: currentEvent,
      prediction_event: TARGET_EVENT,
      target_deadline_time: phase === "decision" ? "2099-10-04T10:00:00Z" : "2026-09-27T10:00:00Z",
      actions_locked: phase !== "decision",
      official: { source: "official", fetched_at: now, stale, version: null },
      stale,
      generated_at: now,
      degraded: stale || noDecision,
      prediction_version: "fixture_predictions_v1",
    },
    errors: noDecision ? [{ area: "decision", message: "Model projections are unavailable for this Gameweek" }] : [],
  };
}

export function marketPlayers(): PlayerSummary[] {
  return [...SQUAD, ...MARKET_EXTRA].map((seed) => {
    const [id, name, position, club, price, xp, xmins, status = "a", chance = null, news = ""] = seed;
    return {
      player_id: id,
      name,
      team: clubName(club),
      team_short: club,
      position: position === "GKP" ? "GK" : position,
      price,
      ownership: Math.round(price * 2.7 * 10) / 10,
      event_points: Math.round(xp),
      minutes: xmins,
      goals: 0,
      assists: 1,
      bonus: 0,
      bps: 12,
      form: Math.round((xp - 0.6) * 10) / 10,
      expected_goals: 1.4,
      expected_assists: 1.1,
      expected_goal_involvements: 2.5,
      ict_index: Math.round(xp * 60) / 10,
      predicted_points: xp,
      xmins,
      start_probability: Math.min(0.98, xmins / 90),
      status,
      chance_of_playing_next_round: chance,
      news,
    };
  });
}

export function makePlayerMarket(): PlayerMarketEnvelope {
  return {
    data: { current_event: TARGET_EVENT - 1, status: "FINISHED", finished: true, next_event: TARGET_EVENT, model_version: "fixture_predictions_v1", players: marketPlayers() },
    meta: { source: "official", fetched_at: "2026-10-03T09:00:00Z", stale: false, version: null, model_version: "fixture_predictions_v1" },
    errors: [],
  };
}

export function makeFixtureMatrix(horizonLength = 5): FixtureMatrixEnvelope {
  const gameweeks = Array.from({ length: horizonLength }, (_, index) => TARGET_EVENT + index);
  const teams: FixtureMatrixTeam[] = CLUBS.map(([short, name]) => ({
    team_id: clubId(short),
    team: name,
    team_short: short,
    fixtures: gameweeks.map((event) => {
      // GW9: Hull and Leeds blank; GW10: Spurs and Arsenal play twice.
      if (event === 9 && (short === "HUL" || short === "LEE")) return { event, opponents: [], difficulty: null, fixture_count: 0 };
      const fixture = opponentFor(short, event);
      const opponents = [`${fixture.opponent} (${fixture.home ? "H" : "A"})`];
      if (event === 10 && (short === "TOT" || short === "ARS")) opponents.push(short === "TOT" ? "ARS (H)" : "TOT (A)");
      return { event, opponents, difficulty: fixture.difficulty, fixture_count: opponents.length };
    }),
  }));
  return {
    data: { current_event: TARGET_EVENT - 1, next_event: TARGET_EVENT, start_event: TARGET_EVENT, horizon: horizonLength, gameweeks, teams },
    meta: { source: "official", fetched_at: "2026-10-03T09:00:00Z", stale: false, version: null },
    errors: [],
  };
}

export function makeReview(event = TARGET_EVENT - 1): ReviewEnvelope {
  return {
    data: {
      available: true,
      team_id: 4242,
      event,
      prediction_version: "fixture_predictions_v1",
      summary: { projected_points: 58.4, official_points: 69, hit_cost: 0, net_points_after_hits: 69, actual_vs_projected: 10.6, outcome: "ABOVE_EXPECTATION" },
      captain: { player_id: 107, name: "Duarte", multiplier: 2, projected_points: 8.1, actual_points: 12, projected_contribution: 16.2, actual_contribution: 24, contribution_delta: 7.8 },
      bench: { official_points: 7, projected_points: 9.8, player_count: 4 },
      transfers: [{ player_out: { player_id: 120, name: "Halloran" }, player_in: { player_id: 108, name: "Bramwell" }, projected_delta: 1.4, actual_delta: 4 }],
      picks: SQUAD.map((seed, index) => ({
        player_id: seed[0], name: seed[1], team_short: seed[3], position: seed[2], slot: index + 1,
        multiplier: index < 11 ? (seed[0] === 107 ? 2 : 1) : 0, is_captain: seed[0] === 107, is_vice_captain: seed[0] === 110,
        predicted_points: seed[5], actual_points: Math.round(seed[5] * (index % 3 === 0 ? 1.5 : 0.7)),
        projected_contribution: index < 11 ? seed[5] * (seed[0] === 107 ? 2 : 1) : 0,
        actual_contribution: index < 11 ? Math.round(seed[5] * (index % 3 === 0 ? 1.5 : 0.7)) * (seed[0] === 107 ? 2 : 1) : 0,
        residual: Math.round(seed[5] * (index % 3 === 0 ? 0.5 : -0.3) * 10) / 10,
      })),
      largest_model_miss: { player_id: 109, name: "Ekström", predicted_points: 3.2, actual_points: 1, residual: -2.2 },
      largest_xmins_miss: { player_id: 109, name: "Ekström", predicted_xmins: 62, actual_minutes: 12, residual: -50 },
      decision_quality: { label: "SOUND", projected_decision_value: 1.4, projected_transfer_value: 1.4, captain_opportunity_cost: 0, basis: "pre_deadline_projection" },
      next_signals: [{ type: "MINUTES_REVIEW", severity: "WATCH", title: "Ekström minutes are slipping", message: "Two short appearances in a row. Treat the projection as fragile.", evidence: {} }],
    },
    meta: { source: "derived", fetched_at: "2026-10-03T09:00:00Z", stale: false, version: "fixture_predictions_v1", event },
    errors: [],
  };
}
