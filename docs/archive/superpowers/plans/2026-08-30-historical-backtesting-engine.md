# Historical Backtesting Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, leakage-safe next-GW historical evaluator.

**Architecture:** The engine iterates decision Gameweeks, passes only prior data to an injected predictor, joins the next-GW actuals, then produces metrics and reports.

**Tech Stack:** Python, pandas, NumPy, pytest.

**Spec:** `docs/superpowers/specs/2026-08-30-historical-backtesting-design.md`

## Global Constraints
- No look-ahead bias.
- Target is exactly decision GW + 1.
- Do not duplicate the production predictor.
- Do not modify existing project tests.

### Task 1: Engine and leakage guard
- [x] Implement time-ordered snapshots and leakage validation.
- [x] Add tests for future-row exclusion and next-GW targets.
### Task 2: Metrics
- [x] Implement deterministic prediction and decision metrics.
### Task 3: Reporting
- [x] Implement CSV/JSON report persistence.
### Task 4: Adapter boundary
- [x] Keep project prediction integration explicit.
### Task 5: Verification
- [x] Run isolated tests and compile new modules.
