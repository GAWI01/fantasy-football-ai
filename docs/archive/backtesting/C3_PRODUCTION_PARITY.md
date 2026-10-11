# C3 Production Parity Audit

## Status

**C3.3 — Historical production-feature reconstruction: COMPLETE**

## Verified semantics

The historical feature builder creates each row for the row's own Gameweek:

- rolling player features use `shift(1)` and therefore exclude the current GW;
- `opponent_team` and `was_home` are the fixture context for that same GW;
- `total_points` is the realised outcome for that same GW.

The live prediction pipeline also selects the fixture for the Gameweek being
predicted and sends the canonical feature row through `feature_contract.py`.

Therefore the production-aligned supervised target is:

```text
feature row @ GW G -> total_points @ GW G
```

not:

```text
feature row @ GW G -> total_points @ GW G+1
```

## Corrective change

`historical_data/train_model.py::prepare_data()` now uses the row's own
`total_points` as `target`.

The previous `shift(-1)` target was removed because it paired GW G fixture
context with the following GW outcome.

No new model was trained in this step and the existing persisted model artifact
was not overwritten.

## Verification

Focused tests after the correction:

- `tests/test_train_model.py`
- `tests/test_feature_pipeline_v11.py`
- `tests/test_production_adapter.py`
- `tests/test_production_parity.py`

All focused tests pass in the available runtime.

## Remaining NOT VERIFIED items

1. The persisted `models/fpl_model_v1.pkl` was trained before this target
   correction and therefore must not be treated as the corrected model.
2. The exact historical/live `xP` calculation lineage still needs a separate
   audit. Historical `features.csv` carries source `xP`, while live prediction
   calculates `xP` from current form/PPG/minutes/xG/xA inputs.
3. The real persisted model must be loaded under its compatible scikit-learn
   environment before a production backtest.

## Consequence for C3

The next valid step is **C3.4 — leakage verification**, but the full model
backtest remains blocked until a corrected model artifact is produced and
verified. Retraining is a separate, explicit step; it has not been performed
here.
