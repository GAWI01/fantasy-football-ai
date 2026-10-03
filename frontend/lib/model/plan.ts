import type {
  ChipState,
  Confidence,
  DashboardData,
  DecisionPlayer,
  PlayerSummary,
  RecommendedTransfer,
  TransferScenario,
} from "@/lib/contracts";
import { hitCost } from "@/lib/fpl/rules";
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

export type ScenarioView = {
  id: string;
  label: string;
  moves: TransferMove[];
  /** Derived: Σ(in next-GW xP − out next-GW xP). Null when an incoming projection is unknown. */
  nextGwGain: number | null;
  /** Model: minutes-adjusted five-GW gain before hits. */
  horizonGain: number;
  hit: number | null;
  /** Derived: horizonGain − hit. */
  horizonNet: number | null;
  /** Model: weighted multi-GW decision score after hits, used by the engine to rank plans. */
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
  recommended: ScenarioView;
  /** When the verdict is HOLD, the best move the engine evaluated but did not adopt. */
  bestRejected: ScenarioView | null;
  hold: ScenarioView;
  alternatives: ScenarioView[];
  freeTransfers: number | null;
  /** "user" when the manager set the count; otherwise an estimate from public data. */
  freeTransfersSource: "user" | "derived" | "unknown";
  bank: number | null;
  captain: SquadPlayer | null;
  vice: SquadPlayer | null;
  captainOptions: Array<{ player: SquadPlayer; captainScore: number | null }>;
  bench: SquadPlayer[];
  modelXI: SquadPlayer[];
  formation: string | null;
  xiPoints: number | null;
  /** Derived: model XI base points plus the captain's extra multiplier. */
  projectedScore: number | null;
  chip: { recommended: ChipName | null; score: number; state: ChipState | null };
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
      outXp: out?.xp ?? null,
      inXp: typeof incoming?.predicted_points === "number" ? incoming.predicted_points : null,
    };
  });
}

function scenarioView(
  id: string,
  label: string,
  scenario: TransferScenario,
  freeTransfers: number | null,
  squadById: Map<number, SquadPlayer>,
  market: Map<number, PlayerSummary>,
): ScenarioView {
  const moves = toMoves(scenario.transfers ?? [], squadById, market);
  const hit = moves.length === 0 ? 0 : hitCost(moves.length, freeTransfers);
  const known = moves.every((move) => move.inXp != null && move.outXp != null);
  const nextGwGain = moves.length === 0
    ? 0
    : known
      ? moves.reduce((total, move) => total + ((move.inXp ?? 0) - (move.outXp ?? 0)), 0)
      : null;
  return {
    id,
    label,
    moves,
    nextGwGain,
    horizonGain: scenario.horizon_gain ?? 0,
    hit,
    horizonNet: hit == null ? null : (scenario.horizon_gain ?? 0) - hit,
    modelScore: scenario.combined_score ?? scenario.current_net_gain ?? 0,
    coverage: scenario.coverage ?? 0,
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
    if (!squad.some((player) => player.risk)) {
      return { tone: "calm", title: "Risk model unavailable", detail: "Official availability shows no flagged starters.", playerId: null };
    }
    return { tone: "calm", title: "No major starter risk", detail: "Every starter is available with a stable minutes outlook.", playerId: null };
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

  const selected: TransferScenario = {
    transfers: strategy?.selected_transfers?.length
      ? strategy.selected_transfers
      : decision.transfers?.recommended_transfers ?? (decision.transfers?.recommended ? [decision.transfers.recommended] : []),
    current_net_gain: strategy?.current_net_gain ?? decision.transfers?.net_gain ?? 0,
    horizon_gain: strategy?.horizon_gain ?? 0,
    combined_score: strategy?.combined_score ?? decision.transfers?.net_gain ?? 0,
    coverage: strategy?.coverage ?? 0,
  };
  const action = intelligence?.action ?? (selected.transfers.length && (decision.transfers?.net_gain ?? 0) > 0 ? "TRANSFER" : "HOLD");
  const verdict: Verdict = action === "HOLD" || !selected.transfers.length ? "HOLD" : "TRANSFER";

  const selectedView = scenarioView("selected", verdict === "TRANSFER" ? "Recommended" : "Best move found", selected, freeTransfers, squadById, market);
  const hold = scenarioView("hold", "Hold / roll", { transfers: [], current_net_gain: 0, horizon_gain: 0, combined_score: 0, coverage: strategy?.coverage ?? 0 }, freeTransfers, squadById, market);
  const alternatives = (strategy?.alternatives ?? [])
    .filter((scenario) => scenario.transfers?.length)
    .map((scenario, index) => scenarioView(`alt-${index + 1}`, `Option ${index + 1}`, scenario, freeTransfers, squadById, market));

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
  const chipName = intelligence?.chip_advisor.recommended_chip as ChipName | null | undefined;

  return {
    verdict,
    recommended: verdict === "TRANSFER" ? selectedView : hold,
    bestRejected: verdict === "HOLD" && selectedView.moves.length ? selectedView : null,
    hold,
    alternatives,
    freeTransfers,
    freeTransfersSource: decision.transfers?.free_transfers_source ?? "derived",
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
