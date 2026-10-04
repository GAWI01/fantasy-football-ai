# Prediction pipeline audit fixes

The code fixes do not certify the committed models, historical metrics or GW6 forecast. No existing CSV, model or manifest was regenerated in this change. A new honest training and validation run is required before a fresh forecast can be published as validated.

## Corrected feature inputs

The model retains its 18 input column names, but semantics are now explicitly versioned with `feature_contract_version=2`, `xp_source=previous_completed_gw_points_mean_v1`, and `target=same_fixture_total_points`.

Historical scraped same-GW `xP` has no verified pre-deadline collection time. Historical regeneration now derives `xP` from the shifted mean of prior completed-GW points. Live regeneration uses that same `points_avg_5` value and does not use cumulative season xG/xA as a fixture forecast. This is an input recipe change: previous fitted weights and metrics cannot be relabelled compatible.

Every training/backtest/live row must record `history_cutoff_gw` earlier than its target GW and an `xP` matching its declared recipe. Nonfinite model inputs fail validation. Current rows also record `prediction_event`, `history_gw_count` and `history_complete`; live regeneration rejects incomplete coverage or a different target event.

Publication derives `prediction_season` from the source GW1 deadline and checks that the next deadline belongs to that season. The wall-clock generation date cannot relabel an earlier-season dataset as current.

The current builder reads all `gwN_history.csv` inputs preceding the next GW. Normalized fixture history requires `player_id`, `GW` (or `round`), `minutes`, `total_points`, `goals_scored`, `assists`, `bps`, `influence`, `creativity`, `threat` and `ict_index`; explicit `starts` may be supplied. Legacy event files may supply corresponding `_gwN` statistics (`goals_gwN` and `started_gwN`). Unsuffixed cumulative bootstrap ICT cannot establish event timing and is refused. The existing GW1-only files must therefore be rebuilt from verified event history before current regeneration. The complete last-five event window is required; the runner does not fetch it automatically.

Fixture histories are aggregated to completed Gameweeks before rolling values are calculated. Existing historical DGW rolling semantics are preserved. Missing history remains distinguishable from a recorded zero while minutes fallbacks run. The xMins writer updates the existing canonical feature table and preserves rolling columns instead of replacing them with the bare player table.

Availability is the official status/chance multiplier; it is separate from the minutes/start estimate. Suspended, unavailable and not-in-game statuses, zero official chance, or injury with no official chance give zero availability. Injury with a positive chance remains a risk. Minutes and start probability cannot exceed availability. Recorded zero recent participation never falls back to misleading season minutes. Forecasts with no fixture or zero availability/minutes are zero. A blank player remains in the full current pool, and DGW points and xMins sum across every fixture; start probability remains a per-fixture estimate bounded by one.

## Model provenance and validation

New training writes the corrected artifact name and attaches `feature_contract_metadata_` with the recipe and `validation_state=unverified`. The historical adapter accepts compatible models for evaluation, but the live predictor defaults to `fpl_model_v1_corrected.pkl` and requires a separate certificate at `<model>.metadata.json`. A legacy artifact, the word corrected, or a flag alone cannot satisfy the gate.

The certificate must contain the recipe fields, `validation_state=validated`, the model SHA256, and a validation report filename/SHA256. The loader verifies both files' bytes. The report must refer to that same model/recipe and record `production_parity_verified=true`, `xp_timing_verified=true`, temporally earlier `train_seasons`, a separate later `held_out_season`, and finite nonnegative MAE/RMSE with a positive row count. Report paths stay inside the model directory. C3 does not create a production certificate merely by training and calculating historical metrics.

A future validation run must establish pre-deadline timing for every other model input, check live/history feature and fixture parity, and validate availability and fixture postprocessing as well as predictive quality. The repository's existing reports do not establish these conditions. No certificate was fabricated during this fix.

Published `model_provenance` records the verified model/report hashes, per-input hashes, aggregate `input_sha256`, and `code_revision` as a SHA256 of actual generator source contents. Its `evaluation` object records `leakage_safe`, `production_parity`, `report_id` and `report_sha256`. `backend.data_manifest.model_validation_state()` requires these fields before reporting validated. Old manifests remain readable and are explicitly unverified.

## Immutable publication

`publish_prediction_artifact(path, bytes, ...)` validates CSV columns, finite positive unique player IDs, finite nonnegative forecasts, row count, season and event bounds before publication. It uses an exclusive directory publication lock, stages bytes under unique temporary names, publishes immutable artifact/sidecar files, and replaces the current pointer last. Identical reruns retain the original timestamp. A conflict, corrupt input or failed write preserves prior certified bytes and removes newly created partial artifacts. A competing writer fails without replacing an in-progress publication.

A process killed while holding the publication lock can leave `.prediction-publication.lock`; confirm no publisher is running before removing that stale lock. This is a filesystem publication guard, not a claim that multiple filesystem replacements form a single transaction. The served pointer changes atomically only after the immutable files exist.

`publish_prediction_manifest()` remains available for existing callers and delegates to the byte-validating publication routine. Existing legacy files gain no retrospective provenance from being readable.
