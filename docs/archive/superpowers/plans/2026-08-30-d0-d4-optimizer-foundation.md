# D0-D4 Optimizer Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the existing FPL-AI optimizer and connect prediction, multi-Gameweek and transfer optimization through one explicit, testable contract without replacing working components.

**Architecture:** Keep `optimizer/squad_optimizer.py` and `optimizer/starting_xi.py` as the authoritative squad/lineup engines. Add a focused optimizer contract/objective layer and a multi-GW/transfer orchestration layer that consumes the existing prediction schema, while preserving existing public functions. Use TDD and regression tests around FPL constraints, determinism, multi-GW scoring, and transfer costs.

**Tech Stack:** Python 3.13, pandas, NumPy, SciPy MILP, pytest.

**Spec:** D0-D4 design approved in chat on 2026-08-30.

## Global Constraints

- Preserve existing working optimizer and decision-engine interfaces unless a compatibility wrapper is required.
- Do not create a second competing squad optimizer.
- Prediction values must be separated from realized historical outcomes; no future information may enter optimization inputs.
- FPL squad constraints remain authoritative.
- Multi-GW objectives must be deterministic and inspectable.
- Transfer hit cost must be explicit.
- All new behavior requires regression tests.
- Do not delete legacy files during D implementation; cleanup follows D9.

---

### Task 1: D0 baseline and optimizer contract

**Files:**
- Create: `optimizer/optimizer_contract.py`
- Modify: `optimizer/squad_optimizer.py`
- Test: `tests/test_optimizer_contract.py`
- Test: `tests/test_optimizer.py`

**Interfaces:**
- `validate_optimizer_input(df: pd.DataFrame) -> None`
- `normalize_optimizer_input(df: pd.DataFrame) -> pd.DataFrame`
- `OPTIMIZER_REQUIRED_COLUMNS`
- `OPTIMIZER_OUTPUT_COLUMNS`

- [ ] Write failing tests for missing required columns, numeric prediction validation, deterministic normalization, and preservation of player identifiers.
- [ ] Run the focused tests and confirm the new contract tests fail before implementation.
- [ ] Implement the contract as a thin validation/normalization layer; keep `optimize_squad()` behavior unchanged except for calling the contract.
- [ ] Run `pytest tests/test_optimizer_contract.py tests/test_optimizer.py -q`.
- [ ] Run the existing optimizer tests and confirm no regression.

### Task 2: D1 harden squad MILP

**Files:**
- Modify: `optimizer/squad_optimizer.py`
- Test: `tests/test_optimizer.py`

**Interfaces:**
- Preserve `optimize_squad(predictions: pd.DataFrame, budget: float = 100.0) -> pd.DataFrame`.

- [ ] Add tests for exact 15-player output, exact position counts, club cap, budget boundary, deterministic output and invalid-input rejection.
- [ ] Run tests to establish any missing invariants.
- [ ] Implement only the minimal constraint/validation changes required.
- [ ] Run `pytest tests/test_optimizer.py tests/test_starting_xi.py -q`.
- [ ] Run the broader decision/optimizer regression suite.

### Task 3: D2 unified objective

**Files:**
- Create: `optimizer/objective.py`
- Modify: `optimizer/squad_optimizer.py`
- Test: `tests/test_optimizer_objective.py`

**Interfaces:**
- `OptimizerObjectiveConfig`
- `score_predictions(df: pd.DataFrame, config: OptimizerObjectiveConfig) -> pd.Series`
- `build_objective_column(df: pd.DataFrame, config: OptimizerObjectiveConfig) -> pd.DataFrame`

The default objective starts from predicted points and applies explicit, bounded modifiers for minutes certainty and risk only when those columns are supplied. Missing optional signals must not silently create penalties.

- [ ] Write tests for base prediction preservation, bounded risk adjustment, xMins/minutes certainty behavior, missing optional columns, and deterministic output.
- [ ] Run focused tests and verify they fail.
- [ ] Implement the objective layer without embedding business rules into the MILP constraints.
- [ ] Run focused objective + optimizer tests.
- [ ] Verify existing starting-XI behavior remains unchanged.

### Task 4: D3 multi-GW optimization

**Files:**
- Create: `optimizer/multi_gw.py`
- Modify: `optimizer/squad_optimizer.py`
- Test: `tests/test_multi_gw_optimizer.py`

**Interfaces:**
- `MultiGWConfig`
- `optimize_multi_gw(predictions: pd.DataFrame, budget: float = 100.0, config: MultiGWConfig | None = None) -> pd.DataFrame`
- `aggregate_multi_gw_value(predictions: pd.DataFrame, config: MultiGWConfig) -> pd.DataFrame`

- [ ] Write tests for horizon filtering, weighted GW values, deterministic aggregation, unchanged squad constraints, and no use of future actual points.
- [ ] Run tests to verify the new module is missing.
- [ ] Implement multi-GW aggregation around the existing squad optimizer rather than duplicating MILP constraints.
- [ ] Run focused multi-GW and optimizer tests.
- [ ] Add a DGW test ensuring multiple fixtures in one GW aggregate correctly at the player/GW level.

### Task 5: D4 transfer optimization

**Files:**
- Create: `optimizer/transfer_optimizer.py`
- Modify: `transfer_analysis.py`
- Test: `tests/test_transfer_optimizer.py`
- Test: `tests/test_decision_engine.py`

**Interfaces:**
- `TransferOptimizationConfig`
- `optimize_transfers(current_squad: pd.DataFrame, candidates: pd.DataFrame, config: TransferOptimizationConfig | None = None) -> dict`
- `calculate_transfer_value(current_squad: pd.DataFrame, candidate_squad: pd.DataFrame, *, hit_cost: float = 0.0) -> float`

- [ ] Write tests for zero-transfer hold, one-transfer improvement, explicit hit-cost deduction, budget validity, club/position constraints, and deterministic alternatives.
- [ ] Run focused tests before implementation.
- [ ] Implement candidate evaluation by reusing the authoritative squad optimizer and current transfer-analysis helpers.
- [ ] Preserve `analyze_transfer_optimizer()` compatibility through a wrapper/adaptor if necessary.
- [ ] Run optimizer, transfer, and decision-engine tests.
- [ ] Add one integration test proving the decision engine receives the post-transfer squad rather than the pre-transfer squad.

### Task 6: D0-D4 integration and regression

**Files:**
- Modify: `decision_engine.py` only if required for contract integration
- Create/Modify: `tests/test_d0_d4_integration.py`
- Modify: `backtesting/C3_FINAL_REVIEW.md` only if D changes C3 assumptions

**Interfaces:**
- Existing decision-engine output contract remains authoritative.

- [ ] Write an integration test from prediction frame through squad optimization and transfer recommendation.
- [ ] Run the complete optimizer/decision test suite.
- [ ] Run the complete Python test suite.
- [ ] Run type/lint/build checks available in the repository.
- [ ] Run a deterministic smoke test twice and compare serialized optimizer output.
- [ ] Produce a D0-D4 implementation report with changed files, tests, metrics, known limitations and next D5-D9 work.
