# C3 Combined Training + Backtest Pipeline

## Purpose

Run the remaining C3 work in one controlled pipeline:

1. Train corrected V1 model on 2020-21 through 2023-24.
2. Never overwrite `models/fpl_model_v1.pkl`.
3. Save the corrected artifact as `models/fpl_model_v1_corrected.pkl`.
4. Run a small 2024-25 out-of-sample backtest (GW1 decision through GW6).
5. Run the full 2024-25 out-of-sample backtest (GW1 decision through GW37, targeting GW2-GW38).
6. Validate target-GW alignment.
7. Compare the model against the historical `xP` baseline.
8. Write machine-readable reports under `backtesting/reports/`.

## Expected outputs

- `models/fpl_model_v1_corrected.pkl`
- `backtesting/reports/c3_report.json`
- `backtesting/reports/c3_small_backtest_2024-25.csv`
- `backtesting/reports/c3_full_backtest_2024-25.csv`
- `backtesting/reports/c3_full_metrics_by_gw_2024-25.csv`

## Evaluation boundary

Training seasons:

- 2020-21
- 2021-22
- 2022-23
- 2023-24

Out-of-sample test season:

- 2024-25

The feature rows use pre-GW rolling history and the fixture context for the
fixture being predicted. Double Gameweek fixture predictions are aggregated
to player/Gameweek before comparison with realised total points.

## Safety

The original V1 artifact is read but never overwritten by this pipeline.

A corrected artifact is created separately. It should only become the official
V1 artifact after local verification and review of the C3 report.
