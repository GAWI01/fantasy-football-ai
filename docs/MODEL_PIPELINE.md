# Forecast model and pipeline

The served forecasts come from one certified model, `models/fpl_model_v4.pkl`,
and one code path from raw fixture rows to published CSV. Training,
validation and live forecasting call the same functions, so features cannot
drift between them.

```
historical_data/<season>/merged_gw.csv      fixture rows (Vaastav archive, or the
historical_data/<season>/fixtures.csv       official API for the current season)
            │
            ▼
build_features.build_feature_frame()        the only feature implementation
            │
   ┌────────┴──────────────────────┐
   ▼                               ▼
validate_model (train + certify)   forecast.live_feature_rows (history + next GW fixtures)
   │                               │
   ▼                               ▼
models/fpl_model_v4.pkl            current_data/predict_gw → gw{N}_predictions_v13.csv
 + .validation.json                 + sidecar + manifest.json (served by the API)
 + .metadata.json (certificate)
```

## Features (contract v4)

One row per player and fixture. Every rolling value for Gameweek G uses only
the player's completed Gameweeks before G (Double Gameweeks are aggregated to
Gameweeks first, so one fixture never sees the other).

| Feature | Meaning |
|---|---|
| `price` | Price at the Gameweek (live: current price) |
| `was_home` | Home fixture |
| `fixture_difficulty` | Official FDR for the player's side of the fixture |
| `position` | GK / DEF / MID / FWD (assistant-manager rows are excluded) |
| `points_last_3`, `points_last_5`, `points_avg_5` | Points over the last 3/5 completed Gameweeks |
| `minutes_last_5`, `starts_last_5` | Minutes and 60-minute appearances |
| `goals_last_5`, `assists_last_5` | Goals and assists |
| `history_gw_count` | Completed Gameweeks in the window (0-5) |
| `bps_avg_5`, `influence_avg_5`, `creativity_avg_5`, `threat_avg_5`, `ict_index_avg_5` | Per-fixture averages |

Version 3 removed `opponent_team` (a club ID used as a number; IDs are
alphabetical per season and mean nothing across seasons) and the `xP`/`form_5`
columns (exact copies of `points_avg_5`). The archived same-Gameweek FPL `xP`
field is never used: it has no verified pre-deadline timing. The feature
frame still records `xP = points_avg_5`, `history_cutoff_gw` and the contract
version so provenance can be checked row by row.

Version 4 added `history_gw_count`. Without it, "no history yet" and "five
Gameweeks without minutes" were the same all-zero row, so at the start of a
season regular starters were forecast like benched players: v3 under-forecast
GW1 by about one point per fixture in every validation season (-1.14 in
2026-27) and GW1-5 by 0.22-0.35. With the count, GW1 bias is -0.16 to -0.25
and GW1-5 bias -0.04 to -0.17. With a full five-Gameweek window the two
versions forecast almost identically (GW6 2026-27: rank correlation 0.999).

## Model and validation

`HistGradientBoostingRegressor` on the feature row; target = points from that
fixture. Negative outputs are floored at zero; a Double Gameweek sums its
fixtures.

**Model selection** used rolling-origin validation on completed seasons only:
each of 2023-24, 2024-25 and 2025-26 was scored by a model trained on the
seasons before it. Gradient boosting with fixture difficulty beat Random Forest
and the club-ID feature set on every fold.

**Production model**: trained on 2020-21 to 2025-26 (2025-26 introduced
defensive-contribution points, so it must be in training). **Held-out test**:
the current season's completed Gameweeks (2026-27 GW1-5, 3 216 fixture rows),
used neither for training nor for model selection.

| | MAE | RMSE | Spearman per GW (all players) | Actual points of the model's top 10 per GW |
|---|---|---|---|---|
| Model v4, 2026-27 GW1-5 | **1.256** | **2.230** | 0.618 | **6.06** |
| Baseline `points_avg_5` | 1.350 | 2.650 | 0.667 | 3.46 |

Rolling-origin folds (model vs baseline MAE): 2023-24 0.955 vs 1.006,
2024-25 0.992 vs 1.055, 2025-26 0.990 vs 1.054. Against v3, v4 lowers MAE and
RMSE on all three folds and RMSE on 2026-27 (2.293 to 2.230); its 2026-27 MAE
is slightly higher (1.229 to 1.256) because MAE rewards forecasting low when
most results are zero, which is what v3's bias did. Held-out bias is -0.14
points per fixture (v3: -0.35). The feature was chosen on the three
historical folds; the 2026-27 figures were also inspected before
recertification, so they are a confirmation rather than an untouched test.

The baseline ranks the *whole* player pool slightly better (Spearman), while
the model is clearly better on error and at the top of the ranking, which is
what transfers and captaincy use. The whole-pool difference comes mostly from
the many non-playing squad players, whom a recent-points rule ranks at
exactly zero; this is an interpretation, not a measured decomposition.

### Certification gates

`python -m historical_data.validate_model` writes the model, its validation
report and, only if every gate passes, the certificate:

1. **Beats the baseline** on held-out MAE and RMSE.
2. **Causality**: for every held-out Gameweek G, replacing all outcomes from G
   onwards with random values leaves G's features unchanged (max difference 0).
3. **Production parity**: replaying the live path (history before G + G's
   fixtures) reproduces the historical feature rows and predictions exactly
   (max difference 0).

The live publisher (`load_prediction_model`) refuses a model whose bytes,
report, temporal split, metrics or scikit-learn version do not match the
certificate. `backend.data_manifest.model_validation_state()` reports
`validated` only for forecasts published with that provenance.

### Known limitations

- Historical fixture difficulty comes from end-of-season FDR snapshots; the
  current season uses the official values at prediction time.
- The official availability multiplier is a rule applied after the model
  (status s/u/n → 0; injured without a chance → 0; otherwise chance/100). Past
  availability flags are not archived, so it cannot be validated historically.
- New signings with no completed history this season are scored from price,
  position and fixture only.

## Live forecasts and availability

`historical_data/current_data/predict_gw.py` forecasts the next Gameweek only
when every earlier Gameweek is finished **and** data-checked: that is the input
the model was validated on. Each row stores the model's points if available
(`ml_prediction`) and minutes if available (`xmins_available`,
`start_probability_available`); `predicted_points` applies availability at
generation time. The API reapplies the latest official availability, price and
names on every request, so injury news never needs a new artifact.

A Gameweek is published once. It is republished (as `_r2`, `_r3`, ...) only if
its fixtures change, e.g. a postponement that creates a blank. Publication is
immutable: artifacts and sidecars are never overwritten, and `manifest.json`
switches last.

### Between a deadline and final scores

After Gameweek N's deadline the next Gameweek is N+1, but its forecast needs
N's final scores. Until then the API serves official team data and marks the
plan and player forecasts as unavailable (target mismatch), while the live view
still compares live points with Gameweek N's own pre-deadline forecast
(`expected_points` on each live pick).

## Refreshing forecasts

`python -m historical_data.refresh_predictions` (pinned by
`requirements-pipeline.txt`) is the single refresh command: it refreshes
official data and the season history, publishes a due forecast and validates
the serving bundle. It reports `changed=true` only for a new forecast, a new
forecast check or a fixture-schedule change; prices and ownership alone are
not worth a commit.

`.github/workflows/refresh-predictions.yml` runs it in GitHub Actions every
three hours and commits any change to `master`, which deploys the API and the
app automatically. If a run fails, the failure is an error annotation on the
run and the API keeps serving the previous forecast; the plan then shows as
unavailable once that forecast's Gameweek has started.

## Forecast checks

After each Gameweek has final scores, the refresh scores its pre-deadline
forecast (the artifact Review uses) against official points for every
current player and appends the result to
`historical_data/current_data/forecast_checks.csv`: mean forecast vs mean
actual, bias, MAE, RMSE, rank correlation and the points scored by the
forecast's top 10. Under GitHub Actions each check is also a notice
annotation on the run. The first entry scores the archived, unverified v11
GW3 forecast: 0.82 forecast vs 1.43 actual points per player.

## Commands

```bash
python historical_data/download_data.py 2025-26      # archived season (Vaastav)
python historical_data/fetch_season_history.py       # current season, final Gameweeks only
python -m historical_data.validate_model             # train, validate, certify
python -m historical_data.refresh_predictions        # what the scheduled job runs
python -m historical_data.current_data.predict_gw    # publish the next forecast (--force to republish)
python -m backend.runtime_artifacts                  # validate the serving bundle
```

### Season rollover

When a season ends, download it (`download_data.py <season>`), add it to
`TRAIN_SEASONS` in `historical_data/train_model.py`, and once the new season
has a few final Gameweeks run `validate_model` again so the held-out test is
the new season. Until then the existing certified model keeps serving.

## Immutable publication

`publish_prediction_artifact(path, bytes, ...)` validates CSV columns, finite
positive unique player IDs, finite nonnegative forecasts, row count, season and
event bounds before publication. It uses an exclusive directory lock, stages
bytes under unique temporary names, publishes immutable artifact/sidecar files
and replaces the pointer last. Identical reruns keep the original timestamp and
metadata bytes. A failed write restores prior bytes and removes partial files.
A process killed while holding the lock can leave
`.prediction-publication.lock`; confirm no publisher is running before removing it.
