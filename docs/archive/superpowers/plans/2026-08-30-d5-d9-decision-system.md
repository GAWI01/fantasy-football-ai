# D5-D9 Decision System Implementation Plan

## Goal
Complete the existing FPL-AI decision layer by upgrading chip selection, risk/uncertainty handling, decision-engine integration, historical decision backtesting, and final validation without replacing existing working modules.

## D5 — Chip optimization
- Add a deterministic scenario evaluator for Wildcard, Free Hit, Bench Boost and Triple Captain.
- Compare chip-use-now vs no-chip using supplied prediction/horizon data.
- Keep the existing `chip_advisor()` API backward compatible.

## D6 — Risk / uncertainty
- Add explicit risk-adjusted scoring utilities.
- Use xMins/start probability/availability/rotation where available.
- Keep raw predicted points intact; risk adjustment is a separate score.
- Integrate risk-adjusted score into decision intelligence confidence and action context.

## D7 — Decision Engine integration
- Feed the canonical optimizer/transfer/chip results into `build_decision()`.
- Preserve the decision contract.
- Add structured chip and risk blocks to the intelligence output.

## D8 — Historical decision backtest
- Add a reusable decision-backtest evaluator under `backtesting/`.
- Evaluate predicted vs realized transfer gains and decision direction.
- Enforce no-lookahead and target-GW alignment.
- Do not use future actuals as decision inputs.

## D9 — Final validation
- Add a single D5-D9 validation runner.
- Run focused, full non-UI, and runtime-contract tests.
- Document known limitations and evidence.
- Do not delete legacy code; cleanup remains a separate post-D task.
