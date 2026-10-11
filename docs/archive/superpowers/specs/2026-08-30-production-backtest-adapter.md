# Production Backtest Adapter C2

C2 connects the existing persisted FPL-AI model to Backtesting C1. It imports
the project's existing `feature_contract.py`; it must never ship a replacement
contract. For decision GW G, only rows with GW <= G are accepted, and the
latest legal row per player is passed through the canonical feature contract.
The realized target is exactly GW G+1. Seasons are evaluated independently.
