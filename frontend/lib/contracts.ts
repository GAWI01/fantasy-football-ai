export type SourceClass = "live" | "official" | "model" | "derived";

export type SourceMeta = {
  source: SourceClass;
  fetched_at: string;
  stale: boolean;
  version: string | null;
};

export type AreaError = {
  area: string;
  message: string;
};

export type Prediction = {
  predicted_points?: number | null;
  opponent?: string | null;
  home?: boolean | null;
  difficulty?: number | null;
  form?: number | null;
  minutes?: number | null;
  xmins?: number | null;
  start_probability?: number | null;
  availability?: string | number | null;
  value?: number | null;
};

export type TeamPick = {
  player_id: number;
  position: number;
  multiplier?: number;
  is_captain?: boolean;
  is_vice_captain?: boolean;
  name: string;
  position_name: string;
  team: string;
  team_short?: string | null;
  price: number | null;
  purchase_price?: number | null;
  selling_price?: number | null;
  status: string;
  event_points?: number | null;
  live_minutes?: number | null;
  live_bps?: number | null;
  form?: number | null;
  ownership?: number | null;
  season_points?: number | null;
  starts?: number | null;
  season_goals?: number | null;
  season_assists?: number | null;
  season_bonus?: number | null;
  expected_goals?: number | null;
  expected_assists?: number | null;
  ict_index?: number | null;
  chance_of_playing_next_round?: number | null;
  news?: string | null;
  news_added?: string | null;
  team_id?: number | null;
  prediction?: Prediction | null;
};

export type DashboardTeam = {
  team_id: number;
  name: string;
  bank: number | null;
  event: number | null;
  transfers: number | null;
  prediction_event?: number | null;
  prediction_file?: string | null;
  picks: TeamPick[];
  overall_rank?: number | null;
  event_points?: number | null;
  event_rank?: number | null;
  total_points?: number | null;
  value?: number | null;
  started_event?: number | null;
};

/** Official points for one stat (FPL's live `explain`). */
export type LiveStat = {
  stat: string;
  value: number;
  /** Null when only the raw stat is known, not its points. */
  points: number | null;
};

export type LivePick = TeamPick & {
  multiplied_points?: number | null;
  /** Pre-deadline model forecast for this live Gameweek, only when the served forecast targets it. */
  expected_points?: number | null;
  goals?: number | null;
  assists?: number | null;
  bonus?: number | null;
  saves?: number | null;
  penalties_saved?: number | null;
  penalties_missed?: number | null;
  yellow_cards?: number | null;
  red_cards?: number | null;
  own_goals?: number | null;
  breakdown?: LiveStat[];
};

export type LiveFixture = {
  fixture_id: number;
  home_team_id: number;
  away_team_id: number;
  home_team: string;
  home_team_short?: string;
  away_team: string;
  away_team_short?: string;
  home_score: number | null;
  away_score: number | null;
  kickoff_time?: string | null;
  started: boolean;
  finished: boolean;
  minutes: number;
};

export type LiveEvent = {
  player_id: number;
  player_name: string;
  team_short: string;
  event_type: "GOAL" | "ASSIST" | "PENALTY_SAVE" | "SAVE" | "BONUS" | "YELLOW_CARD" | "RED_CARD" | "OWN_GOAL" | "PENALTY_MISS";
  count: number;
  active: boolean;
  provisional: boolean;
};

export type DashboardLive = {
  team_id?: number;
  current_event: number;
  gameweek_name?: string;
  status: "LIVE" | "FINISHED" | string;
  finished?: boolean;
  next_event?: number | null;
  next_deadline_time?: string | null;
  picks: LivePick[];
  summary?: {
    live_points: number;
    captain_contribution: number;
    players_finished: number;
    players_live: number;
    players_remaining: number;
    players_without_fixture?: number;
  };
  events?: LiveEvent[];
  fixtures?: LiveFixture[];
};

export type RankHistoryItem = {
  event: number;
  points: number;
  total_points?: number | null;
  overall_rank?: number | null;
  event_rank?: number | null;
  /** Tenths of a million, as FPL reports them. */
  bank?: number | null;
  value?: number | null;
  transfers?: number | null;
};

export type Fixture = {
  fixture_id: number;
  event: number;
  team?: string;
  team_short?: string;
  opponent?: string;
  opponent_short?: string;
  home?: boolean;
  difficulty?: number | null;
  home_team?: string;
  away_team?: string;
  home_team_id?: number;
  away_team_id?: number;
  home_short?: string;
  away_short?: string;
  home_difficulty?: number | null;
  away_difficulty?: number | null;
  selected_team_ids?: number[];
  kickoff_time?: string | null;
  started?: boolean;
  finished?: boolean;
};

export type PlayerSummary = {
  player_id: number;
  name: string;
  team: string;
  team_short: string;
  position: string;
  price: number | null;
  ownership?: number | null;
  event_points?: number | null;
  minutes?: number | null;
  goals?: number | null;
  assists?: number | null;
  bonus?: number | null;
  bps?: number | null;
  clean_sheets?: number | null;
  form?: number | null;
  expected_goals?: number | null;
  expected_assists?: number | null;
  expected_goal_involvements?: number | null;
  season_minutes?: number | null;
  expected_goals_per_90?: number | null;
  expected_assists_per_90?: number | null;
  expected_goal_involvements_per_90?: number | null;
  expected_goals_conceded_per_90?: number | null;
  season_clean_sheets?: number | null;
  influence?: number | null;
  creativity?: number | null;
  threat?: number | null;
  ict_index?: number | null;
  predicted_points?: number | null;
  xmins?: number | null;
  start_probability?: number | null;
  status?: string | null;
  chance_of_playing_next_round?: number | null;
  news?: string | null;
  news_added?: string | null;
};

export type PlayerMarketEnvelope = {
  data: {
    current_event?: number | null;
    gameweek_name?: string;
    status?: string;
    finished?: boolean;
    next_event?: number | null;
    next_deadline_time?: string | null;
    model_version?: string | null;
    prediction_event?: number | null;
    model_validation_state?: string | null;
    model_error?: string;
    players: PlayerSummary[];
  };
  meta: SourceMeta & { model_version?: string | null };
  errors: AreaError[];
};

export type DecisionPlayer = {
  player_id: number;
  name: string;
  position?: string;
  team?: string;
  price?: number | null;
  predicted_points?: number | null;
  xmins?: number | null;
  start_probability?: number | null;
  availability?: string | null;
  difficulty?: number | null;
  captain_score?: number | null;
  opponent?: string | null;
  home?: boolean | null;
  form?: number | null;
  rotation_risk?: string | null;
};

export type RecommendedTransfer = {
  player_out_id: number;
  player_out: string;
  player_in_id: number;
  player_in: string;
  price?: number | null;
  predicted_points?: number | null;
  gain?: number | null;
  /** Each side's own projection for the target Gameweek. */
  next_gw_points_in?: number | null;
  next_gw_points_out?: number | null;
  selling_price?: number | null;
  position?: string | null;
};

export type TransferPlanAlternative = {
  transfers: RecommendedTransfer[];
  transfers_used?: number;
  gross_gain?: number;
  hit_cost?: number;
  net_gain?: number;
};

export type Confidence = {
  /** Null when the label is UNKNOWN. */
  score: number | null;
  label: "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN" | string;
  basis?: string;
  components: {
    decision_margin?: number | null;
    uncertainty?: number | null;
    ratio?: number | null;
  };
  minutes_doubts?: string[];
};

/** One evaluated action from the backend's canonical action planner. */
export type TransferScenario = {
  action?: string;
  transfers: RecommendedTransfer[];
  transfers_used?: number;
  /** Change in the best XI + captain's projected points this Gameweek. */
  next_gw_gain?: number | null;
  /** Weighted multi-GW change in the best XI + captain (bench counts only as cover). */
  horizon_gain: number;
  hit_cost?: number;
  net_gain?: number;
  roll_value_forgone?: number;
  decision_score?: number;
  coverage: number;
  /** Deprecated aliases. */
  current_net_gain?: number;
  combined_score?: number;
};

export type HorizonGameweek = {
  gameweek: number;
  horizon_index?: number;
  predicted_points: number;
  minutes_adjusted_points?: number;
  uncertainty?: number | null;
  opponent?: string | null;
  home?: boolean | null;
  difficulty?: number | null;
  projection_method?: string;
  fixture_count?: number;
};

export type HorizonPlayer = {
  player_id: number;
  coverage: number;
  predicted_points: number;
  minutes_adjusted_points?: number;
  gameweeks: HorizonGameweek[];
};

export type SquadHealthPlayer = DecisionPlayer & {
  score: number;
  label: string;
  rotation_risk?: string | null;
};

export type ChipState = {
  known: boolean;
  period?: number;
  period_events?: [number, number] | number[];
  used_in_period?: Array<{ chip: string; event: number }>;
  wildcard_available: boolean;
  free_hit_available: boolean;
  bench_boost_available: boolean;
  triple_captain_available: boolean;
  double_gameweek?: boolean;
  blank_gameweek?: boolean;
};

/** Per chip: worth playing now, and the best week in the projection horizon. */
export type ChipOutlook = {
  chip: string;
  label: string;
  available: boolean;
  verdict: "USE" | "SAVE" | null;
  this_week: number | null;
  threshold: number | null;
  best_window: { gameweek: number; value: number; unit: string; player_id?: number | null } | null;
  summary: string | null;
};

export type DecisionIntelligence = {
  chip_scenarios?: { budget_is_estimate?: boolean };
  action: string;
  confidence: Confidence;
  captain_decision: {
    captain: DecisionPlayer;
    vice_captain: DecisionPlayer;
    alternatives: DecisionPlayer[];
  };
  squad_health: {
    status: string;
    unavailable_count: number;
    high_risk_count: number;
    average_xmins: number;
    players: SquadHealthPlayer[];
  };
  horizon: {
    horizon: number;
    gameweeks?: number[];
    coverage: number;
    team_projected_points: number;
    captain_projection?: HorizonPlayer;
    team_player_projections: HorizonPlayer[];
  };
  transfer_strategy: Omit<TransferScenario, "transfers"> & {
    action: string;
    selected_transfers: RecommendedTransfer[];
    alternatives: TransferScenario[];
    options_by_transfer_count?: TransferScenario[];
  };
  transfer_action?: string;
  chip_advisor: {
    recommended_chip: string | null;
    score: number;
    reason?: string;
    alternatives: Array<{ chip: string; score: number; reason?: string }>;
  };
  chip_state: ChipState;
  chip_outlook?: ChipOutlook[];
  wildcard_signal?: {
    available: boolean;
    evaluated: boolean;
    recommended: boolean;
    advantage?: number | null;
    threshold?: number | null;
  };
  risk_summary: {
    average_risk: number;
    high_risk_players: number;
    players: Array<DecisionPlayer & { risk_score: number; risk_adjusted_points: number }>;
  };
  insights: Array<{
    type: string;
    severity: string;
    reason: string;
    evidence: Record<string, unknown>;
  }>;
};

export type DashboardDecision = {
  current_team?: {
    team_id: number | null;
    name: string | null;
    bank: number | null;
    value?: number | null;
    transfers?: number | null;
    players: DecisionPlayer[];
  };
  optimal_squad?: {
    players: DecisionPlayer[];
    total_cost: number;
    projected_points: number;
  };
  starting_xi?: {
    formation: string;
    players: DecisionPlayer[];
    projected_points: number;
  };
  bench?: { players: Array<DecisionPlayer & { bench_order: number }> };
  /** "after_recommended_transfers" when starting_xi/bench/captain include the plan's transfers. */
  lineup_source?: "after_recommended_transfers" | "owned_squad";
  /** Best lineup of the squad owned now, before any transfer. */
  owned_lineup?: {
    formation?: string;
    starting_xi: DecisionPlayer[];
    bench: Array<DecisionPlayer & { bench_order: number }>;
    captain: DecisionPlayer;
    vice_captain: DecisionPlayer;
  };
  captain?: DecisionPlayer;
  vice_captain?: DecisionPlayer;
  transfers?: {
    recommended?: RecommendedTransfer | null;
    recommended_transfers?: RecommendedTransfer[];
    transfers_used?: number;
    free_transfers?: number;
    /** "user" when the manager set it, "derived" from public transfer history, "unknown" when history failed. */
    free_transfers_source?: "user" | "derived" | "unknown";
    action?: string;
    hit_cost?: number;
    gross_gain?: number;
    net_gain?: number;
    next_gw_gain?: number;
    decision_score?: number;
    budget_is_estimate?: boolean;
    selling_prices_known?: boolean;
    alternatives?: TransferPlanAlternative[];
    base_projected_points?: number;
    projected_points_after_transfers?: number;
  };
  intelligence?: DecisionIntelligence;
};

export type DashboardData = {
  team: DashboardTeam;
  live: DashboardLive | null;
  history: { history: RankHistoryItem[] } | null;
  fixtures: { fixtures: Fixture[] } | null;
  players: { players: PlayerSummary[] } | null;
  decision: DashboardDecision | null;
};

export type DashboardEnvelope = {
  data: DashboardData;
  meta: {
    event: number | null;
    current_event?: number | null;
    next_event?: number | null;
    prediction_event?: number | null;
    target_deadline_time?: string | null;
    actions_locked?: boolean;
    official?: SourceMeta;
    stale?: boolean;
    generated_at: string;
    degraded: boolean;
    prediction_version?: string | null;
    model_validation_state?: string | null;
    /** "provisional" while the previous Gameweek is still being played. */
    forecast_stage?: "final" | "provisional" | null;
    history_cutoff_gw?: number | null;
  };
  errors: AreaError[];
};

export type StatusEnvelope = {
  data: {
    official: {
      current_event: number | null;
      next_event: number | null;
      player_count: number;
      team_count: number;
    } | null;
    model: {
      season: string;
      prediction_event: number;
      prediction_file: string;
      player_count: number;
      schema_version: number;
    } | null;
    service_state: "ready" | "degraded" | "unavailable";
  };
  meta: {
    official?: SourceMeta;
    model?: SourceMeta;
  };
  errors: AreaError[];
};

export type ReviewSummary = {
  projected_points: number;
  official_points: number;
  hit_cost: number;
  net_points_after_hits: number;
  actual_vs_projected: number;
  outcome: "ABOVE_EXPECTATION" | "IN_LINE" | "BELOW_EXPECTATION" | string;
};

export type ReviewCaptain = {
  player_id: number;
  name: string;
  multiplier: number;
  projected_points: number;
  actual_points: number;
  projected_contribution: number;
  actual_contribution: number;
  contribution_delta: number;
};

export type ReviewTransfer = {
  player_in: { player_id: number; name: string };
  player_out: { player_id: number; name: string };
  projected_delta: number;
  actual_delta: number;
};

export type ReviewPick = {
  player_id: number;
  name: string;
  team_short: string;
  position: string;
  slot: number;
  multiplier: number;
  is_captain: boolean;
  is_vice_captain: boolean;
  predicted_points: number;
  actual_points: number;
  projected_contribution: number;
  actual_contribution: number;
  residual: number;
};

export type ReviewDecisionQuality = {
  label: "SOUND" | "MARGINAL" | "QUESTIONABLE";
  projected_decision_value: number;
  projected_transfer_value: number;
  captain_opportunity_cost: number;
  basis: "pre_deadline_projection";
};

export type ReviewNextSignal = {
  type: "MINUTES_REVIEW" | "CAPTAIN_REVIEW" | "TRANSFER_DISCIPLINE";
  severity: "WATCH" | "ACTION";
  title: string;
  message: string;
  evidence: Record<string, number>;
};

export type ReviewData =
  | {
      available: true;
      team_id: number;
      event: number;
      prediction_version: string;
      summary: ReviewSummary;
      captain: ReviewCaptain | null;
      bench: {
        official_points: number;
        projected_points: number;
        player_count: number;
      };
      transfers: ReviewTransfer[];
      picks: ReviewPick[];
      largest_model_miss: {
        player_id: number;
        name: string;
        predicted_points: number;
        actual_points: number;
        residual: number;
      };
      largest_xmins_miss: {
        player_id: number;
        name: string;
        predicted_xmins: number;
        actual_minutes: number;
        residual: number;
      } | null;
      decision_quality: ReviewDecisionQuality;
      next_signals: ReviewNextSignal[];
    }
  | {
      available: false;
      team_id: number;
      event: number;
      reason: string;
    };

export type ReviewEnvelope = {
  data: ReviewData;
  meta: SourceMeta & { event: number; official?: SourceMeta };
  errors: AreaError[];
};

export type FixtureMatrixCell = {
  event: number;
  opponents: string[];
  difficulty: number | null;
  fixture_count: number;
  /** Derived: chance of a clean sheet in each fixture (two in a double). */
  clean_sheet_chances?: number[];
};

export type FixtureMatrixTeam = {
  team_id: number;
  team: string;
  team_short: string;
  fixtures: FixtureMatrixCell[];
  /** Derived from official xG, pulled towards the league average early on. */
  xg_per_match?: number | null;
  xgc_per_match?: number | null;
  matches_played?: number;
};

export type FixtureMatrixEnvelope = {
  data: {
    current_event: number | null;
    next_event: number | null;
    start_event: number;
    horizon: number;
    gameweeks: number[];
    teams: FixtureMatrixTeam[];
  };
  meta: SourceMeta;
  errors: AreaError[];
};


/** The manager's own transfers scored by the backend planner (GET /api/v1/evaluate). */
export type EvaluationEnvelope = {
  data: {
    legal: boolean;
    reason?: string;
    option?: TransferScenario & { gross_gain?: number };
    hold?: TransferScenario;
    recommended: { action?: string; transfers: RecommendedTransfer[]; decision_score?: number | null; net_gain?: number | null };
    free_transfers: number;
    selling_prices_known?: boolean;
  };
  meta: SourceMeta & { event?: number | null };
  errors: AreaError[];
};


export type LeagueRole = "CAPTAIN" | "STARTER" | "BENCH" | null;

export type ManagerLeague = { league_id: number; name: string; managers: number | null; rank: number | null; last_rank: number | null; analysed_managers: number };

export type LeaguesEnvelope = { data: { team_id: number; leagues: ManagerLeague[] }; meta: SourceMeta; errors: AreaError[] };

export type LeagueStanding = {
  team_id: number; team_name: string; rank: number | null; last_rank: number | null;
  event_points: number | null; total: number | null; gap_to_you: number; active_chip: string | null; is_you: boolean;
};

export type LeaguePlayer = {
  player_id: number; name: string; team_short: string; position: string | null;
  owners: number; captains: number; ownership: number; eo: number; rival_eo: number;
  you: LeagueRole; role: "THREAT" | "DIFFERENTIAL" | null; next_gw_points: number | null;
};

export type LeagueEnvelope = {
  data: {
    league_id: number; name: string; event: number | null; managers: number; analysed_managers: number; max_analysed_managers: number;
    standings: LeagueStanding[]; players: LeaguePlayer[]; thresholds: { threat_eo: number; differential_eo: number }; basis: string;
  };
  meta: SourceMeta; errors: AreaError[];
};

export type RivalPlayer = { player_id: number; name: string; team_short: string; position: string | null; role: LeagueRole; rival_role?: LeagueRole; next_gw_points: number | null };

export type RivalEnvelope = {
  data: {
    event: number; team_id: number; rival_id: number; only_you: RivalPlayer[]; only_rival: RivalPlayer[]; shared: RivalPlayer[];
    same_captain: boolean; unique_next_gw_points: { you: number | null; rival: number | null }; basis: string;
  };
  meta: SourceMeta; errors: AreaError[];
};
