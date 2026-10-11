# Phase 2: decision quality and one new feature (2026-10-11)

Builds on Phase 1 (`PHASE1_DECISION_CORRECTNESS.md`). Every change was checked
on the recorded real-team benchmark (`benchmark/`) and in the browser against
the live state (GW6 live, provisional GW7 forecast).

## Done

| Change | Why (found in the benchmark or audit) | Where |
|---|---|---|
| **Selling prices derived from public data** | Every budget was a market-price estimate. Purchase prices are public: the latest non-Free-Hit `element_in_cost`, or the season start price (`now_cost − cost_change_start`) for a GW1 squad. The FPL rule (half the rise, rounded down) gives the selling price. | `backend/selling_prices.py`, `backend/main.py` |
| **Lineup, captain and bench after the recommended transfers** | 639449 was told to sell B.Fernandes and captain him. Every plan's XI still contained the players it sold. | `decision_engine.py` (`lineup_source`, `owned_lineup`), `frontend/lib/model/plan.ts` |
| **Captain = expected points, with a 0.3-point tie band** | Projections already include minutes and availability, so the old score discounted doubts two or three times. Within 0.3 points the surer starter wins (Haaland over Rashford, 5.52 vs 5.59 xP, 100% vs 79% start). | `decision_intelligence.py` |
| **Decision cache** | The dashboard polls every minute, and each poll re-ran up to ~8 MILP solves. Decisions are now cached on every input (squad, bank, transfers, chips, forecast, projections, official prices and availability). | `backend/main.py` |
| **New: "Test your own move"** | Managers want to know whether their own idea is good, not just what the engine prefers. The move is scored by the same planner, against holding and against the recommendation. Illegal moves are explained (budget, position, club limit). | `GET /api/v1/evaluate/{team_id}?sell=&buy=`, `optimizer/action_planner.evaluate_moves`, `frontend/components/plan/OwnMoveCard.tsx` |
| My Team uses the owned squad's best lineup | Lineup editing applies to the squad you own now, not the squad after the plan. | `frontend/components/team/TeamWorkspace.tsx` |

## Benchmark (15 recorded cases)

| Check | Phase 1 | Phase 2 |
|---|---|---|
| Selling prices known (no estimate) | 0/15 | **15/15** |
| Captain is a player the plan sells | 1/15 | **0/15** |
| Recommended XI or bench contains a sold player | 15/15 | **0/15** |
| One plan per response / no bench-GK transfers | 15/15 / 0 | 15/15 / 0 |
| Dashboard latency (replay, warm) | ~2.0 s | **~0.55 s** |

**Live (GW6 live, provisional GW7):** 639449 is recommended Palmer → Tavernier and João Pedro → Haaland, with captain Haaland (bought) and vice B.Fernandes. "Test your own move" (Palmer → Cherki) returned "Worse than holding by 1.1 points". Both checks were run on desktop and at 390 px, with no horizontal scroll and no page errors.

## Tests

| Area | New or changed tests |
|---|---|
| Selling prices (`tests/test_selling_prices.py`) | FPL rule, Free Hit ignored, start price, untraceable kept as estimate |
| Benchmark (`tests/test_decision_benchmark.py`) | No sold captain or lineup player, cache reuse, own move scores equal to the recommendation, illegal and malformed moves |
| Engine (`tests/test_decision_engine.py`) | Lineup from the post-transfer squad, captain value not discounted twice |
| Intelligence (`tests/test_decision_intelligence.py`) | Tie band, surer starter on ties |
| Frontend (`lib/model/model.test.ts`, `components/plan/OwnMoveCard.test.tsx`) | Plan lineup with an incoming captain; own-move verdicts and flow |

Results:
- `pytest`: 531 passed, 1 skipped.
- Frontend: 112 passed.
- lint and `tsc`: clean.
- build: succeeded.

## Not verified

- Derived selling prices could not be compared with real private FPL selling prices (they are not public).
- Docker, hosted deployment and the scheduled workflow were not run.

## Proposed next features (not built), with the decision each one improves

| Feature | Decision it improves | Complexity | Priority |
|---|---|---|---|
| **Plan across weeks** (roll now, two transfers next week; sequencing) | Today's move assumes nothing happens next week. A two-week plan values rolling properly. | HIGH | P1 |
| **Chip timing planner** (BB/TC/FH across the next 8 GWs, DGW/BGW aware) | When to play each chip, instead of a yes/no for this week only | HIGH | P1 |
| **Mini-league view** (rival squads, effective ownership, differentials) | Captain and transfer choices when the goal is beating specific rivals | MEDIUM | P2 |
| **Team news since last visit** (status changes for owned and targeted players, with dates) | Reacting to injuries before the deadline without opening FPL | LOW | P2 |
| **Model: minutes-aware calibration and per-GW forecasts** | Every recommendation (Rashford-type cases, flat 5-GW outlook) | HIGH | P1 (model) |
| **Calibrate policy constants by backtest** | Hold vs transfer, hits and Wildcard thresholds | MEDIUM | P1 |
