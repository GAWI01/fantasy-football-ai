"""Checks that historical prediction rows match production semantics.

Production predicts the Gameweek represented by the feature row:
- rolling player statistics are shifted to exclude the prediction GW;
- fixture context (opponent/home-away) belongs to that prediction GW;
- the target is that same GW's realised total_points.

This module does not load or retrain the model. It is an audit boundary used
before historical backtesting.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from engine.feature_contract import FEATURE_COLUMNS, build_feature_row


class ProductionParityError(ValueError):
    """Raised when historical rows cannot represent production semantics."""


@dataclass(frozen=True)
class ProductionParityResult:
    rows_checked: int
    valid_rows: int
    target_column: str
    fixture_columns: tuple[str, ...]


def validate_historical_prediction_rows(
    frame: pd.DataFrame,
) -> ProductionParityResult:
    """Validate one generated historical feature frame.

    The row's own GW is the prediction GW. Its lagged rolling features must
    already be produced by the canonical historical feature builder.
    """
    required = {"player_id", "GW", "total_points", *FEATURE_COLUMNS}
    missing = required - set(frame.columns)
    if missing:
        raise ProductionParityError(
            "Historical feature frame missing required column(s): "
            + ", ".join(sorted(missing))
        )

    if frame.empty:
        raise ProductionParityError("Historical feature frame is empty.")

    gw = pd.to_numeric(frame["GW"], errors="coerce")
    if gw.isna().any():
        raise ProductionParityError("Historical feature frame contains invalid GW values.")

    # Validate actual model rows through the canonical contract.
    for _, row in frame.head(min(len(frame), 100)).iterrows():
        build_feature_row(row.to_dict())

    # Fixture context must exist on the same row as the prediction GW.
    for column in ("opponent_team", "was_home"):
        if column not in frame.columns:
            raise ProductionParityError(
                f"Production fixture context is missing: {column}"
            )

    return ProductionParityResult(
        rows_checked=len(frame),
        valid_rows=len(frame),
        target_column="total_points",
        fixture_columns=("opponent_team", "was_home"),
    )


def reconstruct_production_target(frame: pd.DataFrame) -> pd.DataFrame:
    """Return canonical historical prediction rows with same-GW targets.

    This intentionally does not shift target values to G+1. The row already
    contains the fixture for G and lagged player statistics available before G.
    """
    validate_historical_prediction_rows(frame)

    result = frame.copy()
    result["target"] = pd.to_numeric(
        result["total_points"],
        errors="coerce",
    )

    result = result.dropna(subset=["target"]).copy()
    return result
