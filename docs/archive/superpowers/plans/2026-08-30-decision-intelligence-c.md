# Decision Intelligence C Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the strategic Decision Intelligence layer described in the C design.

**Architecture:** Add focused risk, horizon, strategy, and intelligence modules around the existing optimizer core. Extend the canonical Decision Engine output additively so existing consumers remain valid.

**Tech Stack:** Python, pandas, existing scipy MILP optimizer, pytest.

**Spec:** `docs/superpowers/specs/2026-08-30-decision-intelligence-c-design.md`

## Global Constraints

- Do not rewrite the existing MILP optimizer.
- Do not duplicate decision logic in frontend.
- Missing horizon prediction data must be exposed through coverage rather than invented.
- Existing Decision Engine sections remain required.

---

### Task 1: Risk and squad health
**Files:** Create `decision_risk.py`; Test `tests/test_decision_risk.py`
- [ ] Test unavailable and healthy cases.
- [ ] Implement deterministic risk scoring from xMins, start probability, availability and rotation risk.
- [ ] Run `pytest tests/test_decision_risk.py -q`.

### Task 2: Multi-GW horizon
**Files:** Create `decision_horizon.py`; Test `tests/test_decision_horizon.py`
- [ ] Test 1–3 GW normalization and missing-data coverage.
- [ ] Implement player projections and fixture outlook from supplied prediction frames.
- [ ] Implement horizon transfer gain evaluation.
- [ ] Run `pytest tests/test_decision_horizon.py -q`.

### Task 3: Strategy and chips
**Files:** Create `decision_strategy.py`; Test `tests/test_decision_strategy.py`
- [ ] Test hold/transfer threshold, confidence and chip recommendations.
- [ ] Implement deterministic strategy thresholds and chip advice.
- [ ] Run `pytest tests/test_decision_strategy.py -q`.

### Task 4: Intelligence composition
**Files:** Create `decision_intelligence.py`; Test `tests/test_decision_intelligence.py`
- [ ] Test captain risk adjustment, hold behavior and 3-GW transfer evaluation.
- [ ] Compose risk, horizon, strategy, captain, transfer, chip and explanation evidence.
- [ ] Run `pytest tests/test_decision_intelligence.py -q`.

### Task 5: Contract and engine integration
**Files:** Modify `decision_contract.py`; Modify `decision_engine.py`
- [ ] Keep all legacy required sections and add optional validated intelligence.
- [ ] Add optional `horizon_predictions`, `horizon`, and `chip_state` arguments.
- [ ] Use the intelligence captain only when it is a valid XI member.
- [ ] Run the full existing test suite.

### Task 6: Verification
- [ ] Run the new Decision Intelligence tests.
- [ ] Run the complete project test suite in the user's environment.
- [ ] Run current prediction generation and verify the decision output contains the intelligence block.
