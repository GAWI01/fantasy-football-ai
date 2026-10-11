# FPL-AI Decision Intelligence C Design

**Goal:** Add a strategic decision layer that combines current-GW decisions with a 1–3 GW horizon, risk, captaincy, transfer economics, chip advice, wildcard pressure, confidence, and evidence-backed insights while preserving the existing optimizer core.

**Architecture:** Existing ML predictions and MILP/transfer/lineup components remain the calculation core. New focused modules calculate risk, horizon projections, strategic action, and the unified intelligence package. `decision_engine.py` remains the single orchestration point and remains backward compatible when no future predictions or chip state are supplied.

**Outputs:** `intelligence.action`, confidence, intelligent captain/vice ranking, squad health, horizon coverage/projections, horizon-aware transfer strategy, chip advisor, wildcard pressure, and evidence-backed insights.

**Constraints:** Do not rewrite the MILP optimizer. Do not move decision logic to the frontend. Multi-GW calculations must expose data coverage and never pretend missing future prediction data exists. Existing decision sections remain required and valid.
