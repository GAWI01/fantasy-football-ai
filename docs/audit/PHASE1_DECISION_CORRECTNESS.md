# Phase 1: Decision correctness (2026-10-11)

This phase follows up on `PRACTICAL_PRODUCT_AUDIT_2026-10-11.md`. Every
finding was checked against the code before it was changed. The table below
uses the recorded real-team benchmark (`benchmark/`).

## Root causes

| # | Finding | Root cause in code |
|---|---|---|
| P0-1 | "No plan available" while GW6 was live | `predict_gw.target_gameweek` would only forecast GW N+1 once every earlier GW was finished and data-checked. `_validate_prediction_target` then rejected the GW N forecast for target N+1. Planning was blocked from each deadline until the live GW was data-checked. |
| P0-2 | Transfers spent on the reserve goalkeeper | `transfer_analysis.optimize_transfer_plan` maximised the sum of projected points over all 15 players. There was no starting XI, captain or bench weighting. |
| P0-3/4 | Never HOLD, always every free transfer | The roll plan had `net = 0` and won only when nothing was positive. There was no value for a banked FT. `max_transfers = max(1, FT)` meant hits were never searched. |
| P0-5 | Two different transfers in one response | `decision_intelligence._select_horizon_transfer` re-ranked the optimizer's plans with its own score. The frontend showed the intelligence pick; the API also returned the optimizer's pick. |
| P0-6 | 5-GW gain counted twice | `optimize_transfers` already ranked on a weighted 5-GW score. Intelligence then added a second, minutes-discounted 5-GW sum (`combined_score = net_gain + horizon_gain`). |
| P0-7 | Injured/suspended/blank = 0 for 5 GWs | `planning_service.build_fixture_scaled_horizon` scaled the availability-adjusted target-GW points to every later GW. |
| P1-8 | `MULTI_TRANSFER` with one transfer | `transfer_pressure` compared a 5-GW sum with a 1-GW value. It was almost always ≥ 0.65, which forced `MULTI_TRANSFER`. |
| P1-9 | HIGH confidence everywhere | The components were saturated: margin divided by 6 on a 5-GW number; coverage was always 1; agreement was always 1. |
| P1-10 | Wildcard signal 1.0 whenever available | The signal measured overlap with a 100 m, single-GW theoretical optimum, so it saturated at 1.5 × turnover. |
| P1-11/12 | UI promised hits and a "threshold" | Neither existed in the engine. |
| Extra | Unknown Team ID showed "Failed to fetch" | An uncaught `TeamServiceError` produced a plain-text 500 without CORS headers. The gateway also retried the 404. |

## What changed

- **`optimizer/action_planner.py` (new)** is the canonical action planner.
  - It runs one MILP per transfer count: k = 0 (hold) … FT + 2.
  - Each plan's value is the best legal XI plus captain per horizon GW.
  - Bench players count only as autosub cover: 0.10 of their points for outfield players, 0.02 for goalkeepers.
  - The score is weighted gain − hits − hit margin (2.0 per hit) − value of the free transfers used (2.0 / 1.5 / 1.0 / 0.5 for the 1st–4th banked FT).
  - The output includes every option (`options_by_transfer_count`), alternatives (best plan without each chosen incoming player), confidence inputs and a Wildcard evaluation.
  - A Wildcard is recommended only if a free rebuild beats the best normal action by ≥ 20 weighted points.
  - All constants are documented assumptions, not fitted to the benchmark.
- **`transfer_analysis.optimize_transfer_plan`** delegates to the planner and keeps the existing contract fields. It adds `action`, `decision_score`, `next_gw_gain`, `roll_value_forgone`, `options_by_transfer_count` and `wildcard`.
- **`decision_intelligence.build_intelligence`** reports the canonical plan unchanged. `transfer_strategy.selected_transfers` equals `transfers.recommended_transfers`. Per-player horizon detail is display-only.
  - Action labels are `HOLD`, `SINGLE_TRANSFER`, `MULTI_TRANSFER` or `HIT`, or `WILDCARD` / `FREE_HIT` when that chip is recommended.
  - Confidence is the margin over the next-best action divided by the moved players' projection uncertainty. It is `UNKNOWN` when that cannot be measured.
  - Insights quote real numbers. The `net_gain` key bug is fixed.
- **`decision_strategy.chip_advisor`** recommends a chip only on evidence:
  - Wildcard: the planner's rebuild advantage.
  - Free Hit: a blank GW with ≥ 8 points of gain.
  - Bench Boost: a double GW with ≥ 12 projected bench points.
  - Triple Captain: a double GW with ≥ 9 projected captain points.
- **`backend/availability.py` (new)** applies the official next-round rule to the target GW. Later GWs use the news return date ("Suspended until …", "Expected back …"); without a date they use documented recovery assumptions.
  - **`planning_service`** scales `ml_prediction` (points if available) per fixture, then applies each GW's own multiplier.
  - A blank in the target GW uses the new `ml_per_fixture` column.
- **`predict_gw`** publishes the next GW's forecast as `provisional` once the previous GW's deadline has passed, with history up to the GW before. It republishes as `final` once scores are checked.
  - Live expectations come from the live GW's pre-deadline artifact.
  - `meta.forecast_stage` / `history_cutoff_gw` are exposed, and the UI shows a "Provisional forecast" pill.
- **Frontend** presents the backend's numbers without recomputing hits or gains (`lib/model/plan.ts`).
  - The copy now describes the real policy: holding is a real option, hits need cost plus margin, chips need evidence.
  - Confidence shows the margin and the uncertainty.
- **Unknown Team ID** returns a 404 JSON response with CORS headers and is not retried.

## Decision benchmark (recorded real teams, same inputs before and after)

The snapshot `benchmark/snapshots/gw6_pre_deadline.json.gz` holds official FPL responses for the 12 audit teams. They are seen just before the GW6 deadline and run against the pinned GW6 forecast. Reproduce with `python -m benchmark.run`; the raw results are in `benchmark/results/`.

| Team | FT | Before | After |
|---|---|---|---|
| 895045 | 1 | MULTI_TRANSFER Schade>Groß (API said Szoboszlai>Rashford) · HIGH | SINGLE_TRANSFER Szoboszlai>Rashford · MEDIUM |
| 895045 (FT=0) | 0 | HOLD Schade>Groß (API said Szoboszlai>Rashford) · HIGH | HIT Szoboszlai>Rashford −4 · LOW |
| 895045 (FT=2) | 2 | Forster>Kelleher, Szoboszlai>Groß (API said Forster>Pickford, Palmer>Rashford) · HIGH | MULTI_TRANSFER Palmer>Groß, Slater>Rashford · LOW |
| 895045 (FT=3) | 3 | Forster>Kelleher, Palmer>Groß, Slater>Rashford (API differed) · HIGH | MULTI_TRANSFER Konsa>Tarkowski, Palmer>Groß, Szoboszlai>Rashford · LOW |
| 4182037 | 1 | MULTI_TRANSFER Semenyo>Rashford · HIGH · **Wildcard** | SINGLE_TRANSFER Semenyo>Rashford · MEDIUM · no chip (WC advantage 14.9 < 20) |
| 5151567 | 1 | MULTI_TRANSFER Bogle>Tarkowski · HIGH | SINGLE_TRANSFER Bogle>Tarkowski · MEDIUM |
| 1 | 2 | Button(GK)>Tzolakis, O'Reilly>Branthwaite · HIGH | O'Reilly>Tarkowski, Szoboszlai>Rashford · LOW |
| 2 | 3 | Dubravka(GK)>Pickford, Konsa>Tarkowski, Palmer>Rashford · HIGH | Konsa>Tarkowski, Palmer>Rogers, Szoboszlai>Rashford · LOW |
| 6658075 | 0 | Konsa>Gabriel −4 (API said Ajayi>Tarkowski) · HIGH | HIT Szoboszlai>Rashford −4 · LOW |
| 145931 | 2 | Dubravka(GK)>Pickford, Palmer>Rashford · HIGH | **SINGLE_TRANSFER** Szoboszlai>Rashford (rolls one FT) · LOW |
| 2312895 | 2 | Button(GK)>Pickford, Palmer>Rashford · HIGH | Muharemović>Tarkowski, Palmer>Rashford · LOW |
| 5841371 | 3 | Three moves, API differed on all three · HIGH · **Wildcard** | Calafiori>Tarkowski, Hughes>Iwobi, Semenyo>Rashford · LOW · no chip |
| 1482 | 2 | Dovin(GK)>Pickford, Palmer>Rashford · HIGH | Calafiori>Gabriel, Palmer>Rashford · LOW |
| 5416316 | 2 | Lecomte(GK)>Kelleher, Cherki>Rashford (API differed) · HIGH | Calafiori>Tarkowski, Cherki>Rashford · LOW |
| 639449 | 1 | Forster (bench GK, 0 xMins)>Pickford · HIGH | HIT B.Fernandes>Rashford, João Pedro>Haaland −4 · LOW |

| Policy check | Before | After |
|---|---|---|
| Response names one plan | 8/15 | **15/15** |
| Plan spends a transfer on a bench goalkeeper | 9/15 | **0/15** |
| `MULTI_TRANSFER` label with one transfer | 5/15 | **0/15** |
| Confidence HIGH | 15/15 | **0/15** (MEDIUM 3, LOW 12) |
| Wildcard recommended because it was available | 2/2 available | **0/2** |
| Uses fewer FTs than available when the next one does not pay | 0/6 multi-FT cases | **1/6** (145931) |
| HOLD on a real team | 1/15 (FT=0, hit rule) | **0/15** (see below) |

**HOLD on real teams: still 0/15.** The synthetic tests show the engine holds when no move beats rolling (scenarios A, C, D, E, F). On these real squads, though, the GW6 model finds a weighted gain above the 2.0 roll value every time. Rashford is in 14 of 15 plans. His forecast is ml 5.59 if available, ×0.75 doubtful in GW6, with 54 expected minutes. Under GW-specific availability he now counts as recovered after GW6, so his horizon value rose. The policy follows the model faithfully. Whether the model is right about Rashford is the open ML question (see Remaining).

**Live state check (GW6 live, 2026-10-11):**
- I ran the real refresh pipeline in a scratch copy. It published `gw7_predictions_v13.csv` as provisional, with history to GW5.
- The real API then returned `service_state: ready`, `prediction_event 7`, `actions_locked: false` and `forecast_stage: provisional`. It recommended O'Shea>Gvardiol, Palmer>Groß for 895045 (MEDIUM).
- Live GW6 points still compared against the GW6 pre-deadline forecast.
- In the browser, the plan page showed the GW7 plan with the "Provisional forecast" pill on desktop and at 390 px, with no horizontal scroll and no "threshold" text.

## Tests

| Area | New or changed tests |
|---|---|
| Scenarios A–G (`tests/test_decision_scenarios.py`) | Hold/roll, injured starter, one-match ban, reserve keeper vs weak starter, 2 FT (0/1/2), 3 FT, hit margin, canonical plan, hand-computed horizon gain, unlimited FT |
| Real-team benchmark (`tests/test_decision_benchmark.py`) | One plan per response, no bench-GK transfers, unused FT rolled, action labels, wildcard evidence, non-uniform confidence |
| Availability (`tests/test_availability.py`, `tests/test_planning_service.py`) | Return-date parsing, suspension/injury/doubt/departed per GW, blank target GW, future minutes |
| Planner contract (`tests/test_full_transfer_optimizer.py`, `tests/test_transfer_optimizer.py`) | XI-aware gains with hand-checked values, hit taken/declined, timeout |
| Strategy (`tests/test_decision_strategy.py`), intelligence (`tests/test_decision_intelligence.py`) | Action classification, confidence bands/UNKNOWN/minutes cap, evidence-based chips, no re-ranking, HOLD insight |
| Provisional forecast (`tests/test_forecast_pipeline.py`, `tests/test_provisional_serving.py`, `tests/test_audit_api_regressions.py`) | Provisional, then final; wait when two GWs are pending; neutral fixture estimate; live expectations from the pre-deadline artifact; stage reporting |
| Unknown team (`tests/test_unknown_team.py`) | No retry on 404; dashboard 404 JSON with CORS |
| Frontend (`lib/model/model.test.ts`, `components/plan/PlanWorkspace.test.tsx`) | Canonical numbers not recomputed, hold explanation, truthful hit/hold copy, provisional pill |

Results at commit time:
- `python -m pytest tests backend/tests`: 522 passed, 1 skipped.
- `pnpm test`: 24 files, 109 tests passed.
- `pnpm lint`: clean.
- `tsc --noEmit`: clean.
- `pnpm build`: succeeded.

## Remaining (not addressed in this phase)

- **The model drives the remaining questionable advice.**
  - Rashford-type cases: high points if available, low expected minutes.
  - Predictions are compressed (maximum 5.5).
  - Ranking (Spearman) is worse than the baseline.
  - There is no xG/xA, no team strength, and future GWs are FDR-scaled rather than forecast per GW.
  - Next step: per-GW forecasts and minutes-aware calibration.
- **Constants are uncalibrated.** Roll values, bench weights, hit margin, the Wildcard threshold, chip bars and recovery assumptions are documented, not fitted. They should be calibrated with `backtesting/decision_backtest.py` on past seasons.
- **Captain logic is unchanged.** It still double-penalises minutes and availability and has no ceiling model. The planner already optimises a captain per GW internally, but the displayed captain still comes from `captain_intelligence`.
- **The model XI shown is the pre-transfer squad's XI.** The planner's post-transfer lineup (`transfers.lineup`) is not displayed yet.
- **No transfer sequencing.** Future-GW transfers are not modelled; roll value is a constant per banked FT.
- **Chips are judged on this GW only** against fixed bars. There is no comparison with playing them later.
- **Selling prices** are still estimated from market prices. They can be derived from public transfer history.
- **The FT rule after Wildcard/Free Hit** (`live_service.derive_free_transfers`) is still unverified against the official rule text.
- **Live expectations** now use the pre-deadline artifact as published. Availability changes after publication are not reapplied, which is deliberate.
- **Dashboard latency:** about 2 s warm and up to about 8 s cold with all FPL fetches, up from about 1 s. That is up to roughly 8 MILP solves per request plus 60 s polling. Caching the decision per team, forecast and FT override is the obvious next step.
- Earlier audit findings not in scope: scaling of the upstream quota, rank-chart axis, legacy modules/routes.

## Recommended Phase 2: decision quality (not started)

1. **Calibrate the policy constants** with a decision backtest on 2023-24 and 2024-25: roll values, bench weights, hit margin, Wildcard threshold. Report how often HOLD wins and the realised points against always transferring.
2. **Minutes-aware projections.** Combine `ml_prediction` with the start probability for players with low recent minutes, or add expected minutes as a model feature. Re-certify against the baseline, including rank metrics.
3. **Captain:** use the planner's per-GW captain, add a ceiling component, and stop double-counting minutes and availability.
4. **Show the post-transfer XI and bench order** from the planner's lineup.
5. **Derive selling prices** from the public transfer history.
6. **Cache decisions per (team, forecast, FT)** and poll only live data during a live GW.
