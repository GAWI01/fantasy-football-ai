# FPL-AI D0-D4 — Implementation Review

## Scope

D0-D4 hardens the existing optimizer rather than replacing it.

### D0 — Optimizer contract
- Added `optimizer/optimizer_contract.py`
- Centralizes validation and normalization of optimizer inputs.
- Existing optimizer remains backward compatible.

### D1 — Squad MILP hardening
- Existing `optimizer/squad_optimizer.py` remains the authoritative MILP implementation.
- Existing FPL squad constraints remain unchanged.
- Input normalization is now explicit and test-covered.

### D2 — Unified objective
- Added `optimizer/objective.py`
- Added optional `objective_config` to `optimize_squad()`.
- Default behavior is unchanged: predicted points remain the objective.
- Optional risk/minutes-certainty modifiers are explicit, bounded and disabled by default.

### D3 — Multi-Gameweek optimization
- Added `optimizer/multi_gw.py`
- Supports horizon filtering and deterministic GW weights.
- Aggregates player values across the selected horizon and reuses the existing squad MILP.
- Does not consume realized future points.

### D4 — Transfer optimization
- Added `optimizer/transfer_optimizer.py`
- Reuses `transfer_analysis.optimize_transfer_plan()` for feasibility and FPL rules.
- Supports optional multi-GW prediction aggregation before transfer evaluation.
- Existing transfer-analysis API remains intact.

## Verification

Focused D0-D4 suite:

`45 passed`

Full non-UI Python suite:

`203 passed`

The audit runtime cannot collect `tests/test_app.py` and `tests/test_transfer_center.py` because Streamlit is not installed in that runtime. This is an environment limitation, not a test failure in the D0-D4 code.

## Files

### Added
- `optimizer/optimizer_contract.py`
- `optimizer/objective.py`
- `optimizer/multi_gw.py`
- `optimizer/transfer_optimizer.py`
- `tests/test_optimizer_contract.py`
- `tests/test_optimizer_objective.py`
- `tests/test_multi_gw_optimizer.py`
- `tests/test_transfer_optimizer.py`
- `tests/test_d0_d4_integration.py`

### Modified
- `optimizer/squad_optimizer.py`
- `tests/test_optimizer.py`

### Documentation
- `backtesting/D0_D4_IMPLEMENTATION_REVIEW.md`
- `docs/superpowers/plans/2026-08-30-d0-d4-optimizer-foundation.md`

## Not changed

- `models/fpl_model_v1.pkl`
- `models/fpl_model_v1_corrected.pkl`
- Existing decision-engine contract
- Existing starting-XI implementation
- Legacy files slated for post-D cleanup

## Status

D0-D4 implementation is locally verified in the audit environment. User-machine verification is still required before marking D0-D4 VERIFIED.
