import type {
  ChipState,
  Confidence,
  DashboardData,
  DecisionPlayer,
  PlayerSummary,
  RecommendedTransfer,
  TransferScenario,
} from "@/lib/contracts";
import { isFlagged, type SquadPlayer } from "@/lib/model/squad";

export type Verdict = "TRANSFER" | "HOLD";

export type TransferMove = {
  outId: number;
  outName: string;
  inId: number;
  inName: string;
  inPrice: number | null;
  position: string | null;
  out: SquadPlayer | null;
  /** Public market row for the incoming player, when loaded. */
  incoming: PlayerSummary | null;
  inTeam: string | null;
  inTeamShort: string | null;
  /** Next-GW model points for each side, when known. */
  outXp: number | null;
  inXp: number | null;
};

/**
 * One action the backend's canonical planner evaluated. Every number comes
 * from the backend; the frontend never re-ranks or recomputes a plan.
 */
export type ScenarioView = {
  id: string;
  label: string;
  moves: TransferMove[];
  /** Model: change in the best XI + captain's projected points this Gameweek. */
  nextGwGain: number | null;
  /** Model: weighted five-GW change in the best XI + captain, before hits. */
  horizonGain: number;
  hit: number | null;
  /** Model: horizonGain − hit. */
  horizonNet: number | null;
  /** Model: value of the free transfers this option uses instead of rolling. */
  rollValue: number;
  /** Model: the score the engine ranks actions by (net gain − roll value − hit margin). */
  modelScore: number;
  coverage: number;
};

export type ChipName = "WILDCARD" | "FREE_HIT" | "BENCH_BOOST" | "TRIPLE_CAPTAIN";

export const CHIP_LABEL: Record<ChipName, string> = {
  WILDCARD: "Wildcard",
  FREE_HIT: "Free Hit",
  BENCH_BOOST: "Bench Boost",
  TRIPLE_CAPTAIN: "Triple Captain",
};

export type MainRisk = {
  tone: "risk" | "warn" | "calm";
  title: string;
  detail: string;
  playerId: number | null;
};

export type GameweekPlan = {
  verdict: Verdict;
  /** Backend action label, e.g. HOLD, SINGLE_TRANSFER, MULTI_TRANSFER, HIT, WILDCARD. */
  action: string;
  recommended: ScenarioView;
  /** When the verdict is HOLD, the best move the engine evaluated but did not adopt. */
  bestRejected: ScenarioView | null;
  hold: ScenarioView;
  alternatives: ScenarioView[];
  freeTransfers: number | null;
  /** "user" when the manager set the count; otherwise an estimate from public data. */
  freeTransfersSource: "user" | "derived" | "unknown";
  bank: number | null;
  budgetIsEstimate: boolean;
  chipBudgetIsEstimate: boolean;
  captain: SquadPlayer | null;
  vice: SquadPlayer | null;
  captainOptions: Array<{ player: SquadPlayer; captainScore: number | null }>;
  bench: SquadPlayer[];
  modelXI: SquadPlayer[];
  formation: string | null;
  xiPoints: number | null;
  /** Derived: model XI base points plus the captain's extra multiplier. */
  projectedScore: number | null;
  chip: { recommended: ChipName | null; score: number; reason: string | null; state: ChipState | null };
  confidence: Confidence | null;
  mainRisk: MainRisk;
  insights: Array<{ type: string; severity: string; reason: string }>;
};

const num = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

const text = (value: unknown): string | null =>
  typeof value === "string" && value.trim() ? value : null;

function toMoves(
  transfers: RecommendedTransfer[],
  squadById: Map<number, SquadPlayer>,
  market: Map<number, PlayerSummary>,
): TransferMove[] {
  return transfers.map((transfer) => {
    const out = squadById.get(transfer.player_out_id) ?? null;
    const incoming = market.get(transfer.player_in_id) ?? null;
    return {
      outId: transfer.player_out_id,
      outName: text(transfer.player_out) ?? out?.name ?? `Player ${transfer.player_out_id}`,
      inId: transfer.player_in_id,
      // Older plan payloads carry only ids; fall back to the official player list.
      inName: text(transfer.player_in) ?? text(incoming?.name) ?? `Player ${transfer.player_in_id}`,
      inPrice: num(transfer.price) ?? num(incoming?.price),
      position: transfer.position ?? out?.position ?? incoming?.position ?? null,
      out,
      incoming,
      inTeam: incoming?.team ?? null,
      inTeamShort: incoming?.team_short ?? null,
      outXp: num(transfer.next_gw_points_out) ?? out?.xp ?? null,
      inXp: num(transfer.next_gw_points_in) ?? (typeof incoming?.predicted_points === "number" ? incoming.predicted_points : null),
    };
  });
}

function scenarioView(
  id: string,
  label: string,
  scenario: TransferScenario,
  squadById: Map<number, SquadPlayer>,
  market: Map<number, PlayerSummary>,
): ScenarioView {
  const moves = toMoves(scenario.transfers ?? [], squadById, market);
  const hit = num(scenario.hit_cost) ?? (moves.length ? null : 0);
  const horizonGain = num(scenario.horizon_gain) ?? 0;
  return {
    id,
    label,
    moves,
    nextGwGain: moves.length === 0 ? 0 : num(scenario.next_gw_gain),
    horizonGain,
    hit,
    horizonNet: num(scenario.net_gain) ?? (hit == null ? null : horizonGain - hit),
    rollValue: num(scenario.roll_value_forgone) ?? 0,
    modelScore: num(scenario.decision_score) ?? num(scenario.combined_score) ?? 0,
    coverage: num(scenario.coverage) ?? 0,
  };
}

function riskRank(player: SquadPlayer): number {
  const status = String(player.status ?? "a").toLowerCase();
  const statusWeight = status === "a" ? 0 : status === "d" ? 0.5 : 1;
  return Math.max(statusWeight, player.risk?.score ?? 0) * (1 + (player.xp ?? 0) / 10) * (player.isCaptain ? 1.5 : 1);
}

export function mainRiskFor(squad: SquadPlayer[], captain: SquadPlayer | null): MainRisk {
  const starters = squad.filter((player) => player.isStarter);
  const flagged = starters.filter(isFlagged).sort((left, right) => riskRank(right) - riskRank(left));
  const top = flagged[0];
  if (!top) {
    if (!starters.length || !starters.every((player) => player.risk && player.xmins != null && player.startProbability != null)) {
      return { tone: "calm", title: "Risk model unavailable", detail: "Official availability shows no flagged starters.", playerId: null };
    }
    return { tone: "calm", title: "No major starter risk", detail: "No flagged starters in the available risk and minutes data.", playerId: null };
  }
  const status = String(top.status ?? "a").toLowerCase();
  const reasons: string[] = [];
  if (status === "i") reasons.push("injured");
  else if (status === "s") reasons.push("suspended");
  else if (status === "u" || status === "n") reasons.push("unavailable");
  else if (status === "d") reasons.push(top.chance != null ? `${top.chance}% chance to play` : "doubtful");
  if (top.startProbability != null && top.startProbability < 0.75) reasons.push(`${Math.round(top.startProbability * 100)}% start probability`);
  else if (top.xmins != null && top.xmins < 60) reasons.push(`${Math.round(top.xmins)} xMins`);
  if (!reasons.length && top.rotationRisk) reasons.push(`${top.rotationRisk.replaceAll("_", " ").toLowerCase()} rotation risk`);
  const severe = status !== "a" && status !== "d" || top.risk?.label === "VERY_HIGH";
  const role = top.isCaptain || top.id === captain?.id ? "Captain" : "Starter";
  return {
    tone: severe ? "risk" : "warn",
    title: `${top.name} · ${role.toLowerCase()} at risk`,
    detail: reasons.length ? capitalize(reasons.join(", ")) : "Elevated minutes risk in the model.",
    playerId: top.id,
  };
}

const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

export function buildPlan(
  data: DashboardData,
  squad: SquadPlayer[],
  market: Map<number, PlayerSummary> = new Map(),
): GameweekPlan | null {
  const decision = data.decision;
  if (!decision) return null;
  const intelligence = decision.intelligence;
  const squadById = new Map(squad.map((player) => [player.id, player]));
  const freeTransfers = num(decision.transfers?.free_transfers);
  const strategy = intelligence?.transfer_strategy;

  // The backend's canonical action. transfer_strategy mirrors transfers; the
  // fallback only serves payloads without the intelligence block.
  const selected: TransferScenario = strategy
    ? { ...strategy, transfers: strategy.selected_transfers ?? [] }
    : {
      transfers: decision.transfers?.recommended_transfers ?? (decision.transfers?.recommended ? [decision.transfers.recommended] : []),
      next_gw_gain: decision.transfers?.next_gw_gain ?? null,
      horizon_gain: decision.transfers?.gross_gain ?? 0,
      hit_cost: decision.transfers?.hit_cost ?? 0,
      net_gain: decision.transfers?.net_gain ?? 0,
      decision_score: decision.transfers?.decision_score ?? decision.transfers?.net_gain ?? 0,
      coverage: 0,
    };
  const action = intelligence?.transfer_action ?? strategy?.action ?? decision.transfers?.action ?? (selected.transfers.length ? "TRANSFER" : "HOLD");
  const verdict: Verdict = action === "HOLD" || !selected.transfers.length ? "HOLD" : "TRANSFER";

  const selectedView = scenarioView("selected", verdict === "TRANSFER" ? "Recommended" : "Best move found", selected, squadById, market);
  const holdOption = strategy?.options_by_transfer_count?.find((option) => (option.transfers ?? []).length === 0);
  const hold = scenarioView("hold", "Hold / roll", holdOption ?? { transfers: [], horizon_gain: 0, hit_cost: 0, net_gain: 0, decision_score: 0, coverage: strategy?.coverage ?? 0 }, squadById, market);
  const alternatives = (strategy?.alternatives ?? [])
    .filter((scenario) => scenario.transfers?.length)
    .map((scenario, index) => scenarioView(`alt-${index + 1}`, `Option ${index + 1}`, scenario, squadById, market));

  const ownedIds = new Set(squad.map((player) => player.id));
  const captainPool: DecisionPlayer[] = [
    decision.captain,
    decision.vice_captain,
    ...(intelligence?.captain_decision.alternatives ?? []),
  ].filter((player): player is DecisionPlayer => Boolean(player && ownedIds.has(player.player_id)));
  const seen = new Set<number>();
  const captainOptions = captainPool.flatMap((candidate) => {
    if (seen.has(candidate.player_id)) return [];
    seen.add(candidate.player_id);
    const player = squadById.get(candidate.player_id);
    return player ? [{ player, captainScore: num(candidate.captain_score) }] : [];
  });
  // Captaincy must only ever recommend owned players.
  const captain = decision.captain && ownedIds.has(decision.captain.player_id) ? squadById.get(decision.captain.player_id) ?? null : null;
  const vice = decision.vice_captain && ownedIds.has(decision.vice_captain.player_id) ? squadById.get(decision.vice_captain.player_id) ?? null : null;

  const bench = [...(decision.bench?.players ?? [])]
    .sort((left, right) => left.bench_order - right.bench_order)
    .map((player) => squadById.get(player.player_id))
    .filter((player): player is SquadPlayer => Boolean(player));
  const modelXI = (decision.starting_xi?.players ?? [])
    .map((player) => squadById.get(player.player_id))
    .filter((player): player is SquadPlayer => Boolean(player));
  const xiPoints = num(decision.starting_xi?.projected_points);
  const captainXp = num(decision.captain?.predicted_points);
  const chipScore = num(intelligence?.chip_advisor.score) ?? 0;
  const chipReason = text(intelligence?.chip_advisor.reason);
  const chipName = intelligence?.chip_advisor.recommended_chip as ChipName | null | undefined;

  return {
    verdict,
    action: intelligence?.action ?? action,
    recommended: verdict === "TRANSFER" ? selectedView : hold,
    // When holding, the best move the engine evaluated but did not adopt.
    bestRejected: verdict === "HOLD" ? (selectedView.moves.length ? selectedView : alternatives[0] ?? null) : null,
    hold,
    alternatives,
    freeTransfers,
    freeTransfersSource: decision.transfers?.free_transfers_source ?? "derived",
    budgetIsEstimate: decision.transfers?.budget_is_estimate === true,
    chipBudgetIsEstimate: intelligence?.chip_scenarios?.budget_is_estimate === true,
    bank: num(data.team.bank) ?? num(decision.current_team?.bank),
    captain,
    vice,
    captainOptions,
    bench,
    modelXI,
    formation: decision.starting_xi?.formation ?? null,
    xiPoints,
    projectedScore: xiPoints != null && captainXp != null ? xiPoints + captainXp : xiPoints,
    chip: {
      recommended: chipName && chipName in CHIP_LABEL ? chipName : null,
      score: chipScore,
      reason: chipReason,
      state: intelligence?.chip_state ?? null,
    },
    confidence: intelligence?.confidence ?? null,
    mainRisk: mainRiskFor(squad, captain),
    insights: (intelligence?.insights ?? []).map(({ type, severity, reason }) => ({ type, severity, reason })),
  };
}

export function transferHeadline(plan: Pick<GameweekPlan, "verdict" | "recommended">): string {
  if (plan.verdict === "HOLD") return "Hold";
  return plan.recommended.moves.map((move) => `${move.outName} → ${move.inName}`).join(" · ");
}

export function chipAvailability(state: ChipState | null): Array<{ chip: ChipName; label: string; status: "available" | "used" | "unknown" }> {
  const map: Array<[ChipName, keyof ChipState]> = [
    ["WILDCARD", "wildcard_available"],
    ["FREE_HIT", "free_hit_available"],
    ["BENCH_BOOST", "bench_boost_available"],
    ["TRIPLE_CAPTAIN", "triple_captain_available"],
  ];
  return map.map(([chip, key]) => ({
    chip,
    label: CHIP_LABEL[chip],
    status: !state?.known ? "unknown" : state[key] ? "available" : "used",
  }));
}

export function planSnapshot(plan: GameweekPlan, event: number | null, modelVersion: string | null, recordedAt: string) {
  const edge = plan.verdict === "TRANSFER" ? plan.recommended : plan.bestRejected;
  return {
    event: event ?? 0,
    action: plan.verdict === "HOLD" ? "Hold" : transferHeadline(plan),
    captain: plan.captain?.name ?? "Unavailable",
    netGain: edge ? edge.horizonNet : 0,
    confidenceScore: plan.confidence?.score ?? null,
    confidenceLabel: plan.confidence?.label ?? null,
    modelVersion,
    recordedAt,
  };
}
