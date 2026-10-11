from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
import pandas as pd
from engine.transfer_analysis import optimize_transfer_plan
from .action_planner import DecisionPolicy
from .multi_gw import MultiGWConfig

@dataclass(frozen=True)
class TransferOptimizationConfig:
    max_transfers: int = 1
    free_transfers: int = 1
    bank: float | None = None
    hit_cost: float = 4.0
    evaluate_wildcard: bool = False
    def __post_init__(self):
        if self.max_transfers < 0 or self.free_transfers < 0: raise ValueError("transfer counts cannot be negative")
        if self.hit_cost < 0: raise ValueError("hit_cost cannot be negative")

def calculate_transfer_value(current_squad: pd.DataFrame,candidate_squad: pd.DataFrame,*,hit_cost: float=0.0)->float:
    current=float(pd.to_numeric(current_squad["predicted_points"],errors="raise").sum())
    candidate=float(pd.to_numeric(candidate_squad["predicted_points"],errors="raise").sum())
    return candidate-current-float(hit_cost)

def _horizon_frames(
    predictions: pd.DataFrame,
    horizon_predictions: pd.DataFrame | Mapping[int, pd.DataFrame] | None,
    horizon: int,
) -> list[pd.DataFrame]:
    """Per-Gameweek frames in order, the target Gameweek first.

    Accepts either {horizon index: frame} (as built by the planning service)
    or one long frame with a `GW` column.
    """
    if horizon_predictions is None:
        return [predictions]
    if isinstance(horizon_predictions, Mapping):
        ordered = [horizon_predictions[key] for key in sorted(horizon_predictions)]
    else:
        frame = horizon_predictions.copy()
        frame["GW"] = pd.to_numeric(frame["GW"], errors="raise")
        ordered = [group for _, group in sorted(frame.groupby("GW"), key=lambda item: item[0])]
    return ordered[:horizon] or [predictions]

def optimize_transfers(
    current_squad: dict,
    predictions: pd.DataFrame,
    config: TransferOptimizationConfig | None = None,
    *,
    horizon_predictions: pd.DataFrame | Mapping[int, pd.DataFrame] | None = None,
    horizon_config: MultiGWConfig | None = None,
    policy: DecisionPolicy | None = None,
) -> dict:
    """The canonical Gameweek action (hold, free transfers or a hit) over the horizon."""
    config = config or TransferOptimizationConfig()
    horizon_config = horizon_config or MultiGWConfig()
    frames = _horizon_frames(predictions, horizon_predictions, horizon_config.horizon)
    weights = list(horizon_config.gw_weights or (1.0,) * horizon_config.horizon)[: len(frames)]
    return optimize_transfer_plan(
        current_squad,
        predictions,
        free_transfers=config.free_transfers,
        max_transfers=config.max_transfers,
        bank=config.bank,
        hit_cost=config.hit_cost,
        horizon_predictions=frames,
        horizon_weights=weights,
        policy=policy,
        evaluate_wildcard=config.evaluate_wildcard,
    )
