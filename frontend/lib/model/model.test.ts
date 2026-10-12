import { expect, test } from "vitest";

import type { PlayerSummary } from "@/lib/contracts";
import { makeDashboard, marketPlayers } from "@/test-utils/fixtures";
import { modelLineup, moveBench, officialLineup, projectLineup, setArmband, swapPlayers, validTargets } from "./lineup";
import { buildLiveView } from "./live";
import { deriveGameState } from "./phase";
import { buildPlan, chipAvailability, planSnapshot } from "./plan";
import { buildSquad, isFlagged } from "./squad";

const market = new Map<number, PlayerSummary>(marketPlayers().map((player) => [player.player_id, player]));

test("merges official picks with model, health and horizon data, including goalkeepers", () => {
  const squad = buildSquad(makeDashboard().data);
  expect(squad).toHaveLength(15);
  const keeper = squad.find((player) => player.id === 101)!;
  expect(keeper.position).toBe("GKP");
  expect(keeper.xp).toBe(4.4);
  expect(keeper.horizon).toHaveLength(5);
  expect(squad.filter((player) => player.isStarter)).toHaveLength(11);
  expect(isFlagged(squad.find((player) => player.id === 105)!)).toBe(true);
  expect(isFlagged(squad.find((player) => player.id === 107)!)).toBe(false);
});

test("derives the decision, live and settled phases from the envelope and fails closed", () => {
  expect(deriveGameState(makeDashboard({ phase: "decision" })).phase).toBe("decision");
  const live = deriveGameState(makeDashboard({ phase: "live" }));
  expect(live).toMatchObject({ phase: "live", liveActive: true, actionsOpen: false });
  expect(deriveGameState(makeDashboard({ phase: "settled" })).phase).toBe("settled");
  // Every match at full time: no longer live, even before FPL's data check.
  const played = makeDashboard({ phase: "live" });
  played.data.live!.all_played = true;
  played.meta.actions_locked = false;
  played.meta.target_deadline_time = new Date(Date.now() + 86_400_000).toISOString();
  expect(deriveGameState(played)).toMatchObject({ phase: "decision", liveActive: false, gwPlayed: true, actionsOpen: true });
  const missing = makeDashboard();
  delete missing.meta.actions_locked;
  expect(deriveGameState(missing).actionsOpen).toBe(false);
});

test("presents the backend's canonical plan numbers without recomputing them", () => {
  const data = makeDashboard({ verdict: "TRANSFER" }).data;
  const squad = buildSquad(data);
  const plan = buildPlan(data, squad, market)!;
  expect(plan.verdict).toBe("TRANSFER");
  expect(plan.action).toBe("SINGLE_TRANSFER");
  expect(plan.recommended.moves[0]).toMatchObject({ outName: "Ekström", inName: "Castellano", inTeamShort: "TOT" });
  expect(plan.recommended.nextGwGain).toBeCloseTo(2.7);
  expect(plan.recommended.hit).toBe(0);
  expect(plan.recommended.horizonNet).toBeNull();
  expect(plan.recommended.weightedNet).toBeCloseTo(9.4);
  expect(plan.recommended.rollValue).toBeCloseTo(2);
  expect(plan.recommended.modelScore).toBeCloseTo(7.4);
  const double = plan.alternatives.find((scenario) => scenario.moves.length === 2)!;
  expect(double.hit).toBe(4);
  expect(double.horizonNet).toBeNull();
  expect(double.weightedNet).toBeCloseTo(11.0);
  // The shown plan is the backend's recommended_transfers, never a frontend pick.
  const engine = data.decision!.transfers!.recommended_transfers!.map((move) => move.player_in_id);
  expect(plan.recommended.moves.map((move) => move.inId)).toEqual(engine);
  expect(plan.projectedScore).toBeCloseTo((plan.xiPoints ?? 0) + 8.1);
  expect(plan.mainRisk.title).toContain("Varga");
});

test("id-only plan rows still show the incoming player's name and price from the official list", () => {
  const data = makeDashboard({ verdict: "TRANSFER" }).data;
  const strategy = data.decision!.intelligence!.transfer_strategy!;
  strategy.selected_transfers = strategy.selected_transfers!.map(({ player_out_id, player_in_id }) => ({ player_out_id, player_in_id }) as never);
  const plan = buildPlan(data, buildSquad(data), market)!;
  const incoming = market.get(plan.recommended.moves[0].inId)!;
  expect(plan.recommended.moves[0]).toMatchObject({ outName: "Ekström", inName: incoming.name, inPrice: incoming.price });
});

test("a HOLD verdict keeps the best evaluated move as context, not as the recommendation", () => {
  const data = makeDashboard({ verdict: "HOLD" }).data;
  const plan = buildPlan(data, buildSquad(data), market)!;
  expect(plan.verdict).toBe("HOLD");
  expect(plan.recommended.moves).toHaveLength(0);
  expect(plan.bestRejected?.moves[0].inName).toBe("Castellano");
  // The rejected move is shown with why it lost: its gain is below the roll value.
  expect(plan.bestRejected!.weightedGain).toBeLessThan(plan.bestRejected!.rollValue);
  expect(plan.hold.moves).toHaveLength(0);
  expect(planSnapshot(plan, 7, "v1", "2026-10-03T09:00:00Z").action).toBe("Hold");
});

test("captain options never include players outside the squad", () => {
  const data = makeDashboard().data;
  const squad = buildSquad(data);
  const plan = buildPlan(data, squad, market)!;
  const owned = new Set(squad.map((player) => player.id));
  expect(plan.captain?.name).toBe("Duarte");
  expect(plan.captainOptions.every((option) => owned.has(option.player.id))).toBe(true);
  expect(plan.captainOptions.some((option) => option.player.id === 204)).toBe(false);
  expect(chipAvailability(plan.chip.state).find((chip) => chip.chip === "TRIPLE_CAPTAIN")?.status).toBe("used");
});

test("no decision means no plan rather than an invented one", () => {
  const data = makeDashboard({ noDecision: true }).data;
  expect(buildPlan(data, buildSquad(data), market)).toBeNull();
});

test("lineup swaps keep formations legal and armbands on starters", () => {
  const squad = buildSquad(makeDashboard().data);
  const lineup = officialLineup(squad);
  expect(lineup.bench[0]).toBe(112);

  const illegal = swapPlayers(lineup, 101, 113, squad);
  expect(illegal.ok).toBe(false);

  const legal = swapPlayers(lineup, 105, 113, squad);
  expect(legal.ok).toBe(true);
  expect(legal.lineup.starters).toContain(113);
  expect(legal.lineup.bench).toContain(105);

  const benchedCaptain = swapPlayers(lineup, 107, 114, squad);
  expect(benchedCaptain.ok).toBe(true);
  expect(benchedCaptain.lineup.captain).toBe(110);
  expect(benchedCaptain.message).toMatch(/armband/);

  const chained = swapPlayers(swapPlayers(lineup, 105, 115, squad).lineup, 104, 113, squad);
  expect(chained.ok).toBe(true);
  expect(swapPlayers(lineup, 102, 115, squad).ok).toBe(true);
  expect(swapPlayers(swapPlayers(lineup, 102, 115, squad).lineup, 103, 114, squad).ok).toBe(false);

  expect(setArmband(lineup, 113, "captain", squad).ok).toBe(false);
  const vice = setArmband(lineup, 107, "vice", squad).lineup;
  expect(vice.vice).toBe(107);
  expect(vice.captain).toBe(110);

  expect(moveBench(lineup, 1, -1)).toBe(lineup);
  expect(moveBench(lineup, 1, 1).bench).toEqual([112, 114, 113, 115]);
  expect(validTargets(lineup, 101, squad)).toEqual(new Set([112]));

  const projection = projectLineup(lineup, squad);
  expect(projection.missing).toBe(0);
  expect(projection.points).toBeCloseTo(SQUAD_XI_POINTS + 8.1);

  const plan = buildPlan(makeDashboard().data, squad, market)!;
  expect(modelLineup(squad, plan.owned.xi, plan.owned.bench, plan.owned.captain, plan.owned.vice)?.captain).toBe(107);
});

const SQUAD_XI_POINTS = [4.4, 5.3, 5.1, 3.9, 3.7, 6.4, 8.1, 4.6, 3.2, 7.6, 4.9].reduce((total, value) => total + value, 0);

test("live view counts only your clubs' matches and flags auto-sub candidates", () => {
  const data = makeDashboard({ phase: "live" }).data;
  const squad = buildSquad(data);
  const live = buildLiveView(data, squad)!;
  expect(live.points).toBe(data.live?.summary?.live_points);
  const owned = new Set(squad.map((player) => player.teamId));
  expect(live.fixtures.every((fixture) => owned.has(fixture.home_team_id) || owned.has(fixture.away_team_id))).toBe(true);
  expect(live.fixtures[0].started && !live.fixtures[0].finished).toBe(true);
  expect(live.projectedXI).toBeCloseTo(SQUAD_XI_POINTS + 8.1);
});

test("a next-Gameweek forecast is unavailable for the live Gameweek", () => {
  const data = makeDashboard({ phase: "live" }).data;
  data.team.prediction_event = 8;
  expect(buildLiveView(data, buildSquad(data))?.projectedXI).toBeNull();
});

test("live forecasts use the official triple-captain multiplier", () => {
  const data = makeDashboard({ phase: "live" }).data;
  data.live!.picks.find((pick) => pick.is_captain)!.multiplier = 3;
  expect(buildLiveView(data, buildSquad(data))?.projectedXI).toBeCloseTo(73.4);
});

test("live forecasts include bench-boost picks that contribute to the official total", () => {
  const data = makeDashboard({ phase: "live" }).data;
  for (const pick of data.live!.picks.filter((pick) => pick.position > 11)) pick.multiplier = 1;
  expect(buildLiveView(data, buildSquad(data))?.projectedXI).toBeCloseTo(75.1);
});

test("the live captain follows the official vice-captain substitution multiplier", () => {
  const data = makeDashboard({ phase: "live" }).data;
  Object.assign(data.live!.picks.find((pick) => pick.is_captain)!, { multiplier: 0, multiplied_points: 0 });
  Object.assign(data.live!.picks.find((pick) => pick.is_vice_captain)!, { multiplier: 3, multiplied_points: 18 });
  data.live!.summary = undefined;
  const view = buildLiveView(data, buildSquad(data))!;
  expect(view.captain?.name).toBe("Kovač");
  expect(view.captainContribution).toBe(18);
  expect(view.projectedXI).toBeCloseTo(64.3);
});

test("one missing starter forecast makes the whole lineup projection unavailable", () => {
  const squad = buildSquad(makeDashboard().data);
  squad[0].xp = null;
  expect(projectLineup(officialLineup(squad), squad)).toEqual({ points: null, missing: 1 });
});

test("an unknown active-pick multiplier cannot become a partial live total", () => {
  const data = makeDashboard({ phase: "live" }).data;
  data.live!.summary = undefined;
  delete data.live!.picks[0].multiplier;
  delete data.team.picks[0].multiplier;
  expect(buildLiveView(data, buildSquad(data))?.points).toBeNull();
});

test("actions close when the known target deadline passes without another API response", () => {
  const envelope = makeDashboard();
  envelope.meta.target_deadline_time = "2026-10-04T10:00:00Z";
  expect(deriveGameState(envelope, Date.parse("2026-10-04T09:59:59Z")).actionsOpen).toBe(true);
  expect(deriveGameState(envelope, Date.parse("2026-10-04T10:00:00Z")).actionsOpen).toBe(false);
});

test("the live Gameweek's own forecast from the live endpoint drives the expectation", () => {
  const data = makeDashboard({ phase: "live" }).data;
  data.team.prediction_event = 8;
  for (const pick of data.live!.picks) pick.expected_points = 2;
  const active = data.live!.picks.filter((pick) => (pick.multiplier ?? 0) > 0);
  const expected = active.reduce((total, pick) => total + 2 * (pick.multiplier ?? 0), 0);
  expect(buildLiveView(data, buildSquad(data))?.projectedXI).toBeCloseTo(expected);
});

test("the recommended lineup and captain come from the squad after the transfer", () => {
  const data = makeDashboard({ verdict: "TRANSFER" }).data;
  const decision = data.decision!;
  // Backend lineup after Ekström (109) -> Castellano (201); Castellano captains.
  const castellano = { player_id: 201, name: "Castellano", position: "MID", team: "Spurs", predicted_points: 5.9, price: 7.0 };
  const ownedXI = decision.starting_xi!.players;
  decision.owned_lineup = { starting_xi: ownedXI, bench: decision.bench!.players, captain: decision.captain!, vice_captain: decision.vice_captain! };
  decision.starting_xi = { ...decision.starting_xi!, players: ownedXI.map((player) => (player.player_id === 109 ? castellano : player)) };
  decision.captain = castellano;
  decision.lineup_source = "after_recommended_transfers";
  const squad = buildSquad(data);
  const plan = buildPlan(data, squad, market)!;
  expect(plan.lineupAfterTransfers).toBe(true);
  expect(plan.captain?.name).toBe("Castellano");
  expect(plan.modelXI.map((player) => player.id)).toContain(201);
  expect(plan.modelXI.map((player) => player.id)).not.toContain(109);
  // My Team edits the squad owned now: its model lineup has no incoming player.
  expect(plan.owned.xi.map((player) => player.id)).toContain(109);
  expect(plan.owned.captain?.id).toBe(decision.owned_lineup.captain.player_id);
});

test("projected gains retain unweighted payload values and shortened scoring horizons", () => {
  const data = makeDashboard().data;
  const strategy = data.decision!.intelligence!.transfer_strategy;
  Object.assign(strategy, { projected_gain: 13.5, projected_net_gain: 9.5, horizon_gain: 7, net_gain: 3, hit_cost: 4, decision_score: 0.5, horizon_weights: [1, 0.9] });
  const plan = buildPlan(data, buildSquad(data), market)!;
  expect(plan.recommended.horizonGain).toBe(13.5);
  expect(plan.recommended.horizonNet).toBe(9.5);
  expect(plan.recommended.weightedGain).toBe(7);
  expect(plan.recommended.weightedNet).toBe(3);
  expect(plan.horizon).toBe(2);
  expect(planSnapshot(plan, 37, "v1", "2026-10-03T09:00:00Z").netGain).toBe(9.5);
});

test("the older dashboard shape preserves explicit projected values without intelligence", () => {
  const data = makeDashboard().data;
  delete data.decision!.intelligence;
  Object.assign(data.decision!.transfers!, { projected_gain: 13.5, projected_net_gain: 9.5 });
  const plan = buildPlan(data, buildSquad(data), market)!;
  expect(plan.recommended.horizonGain).toBe(13.5);
  expect(plan.recommended.horizonNet).toBe(9.5);
});
