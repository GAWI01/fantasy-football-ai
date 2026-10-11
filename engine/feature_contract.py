"""Canonical, validated model-input contract shared by training and live runs."""

from __future__ import annotations

from collections.abc import Mapping
import math


FEATURE_CONTRACT_VERSION = 4
XP_SOURCE = "previous_completed_gw_points_mean_v1"
MODEL_TARGET = "same_fixture_total_points"


def feature_metadata() -> dict[str, object]:
    return {"feature_contract_version": FEATURE_CONTRACT_VERSION,
            "xp_source": XP_SOURCE, "target": MODEL_TARGET}


# This must match the persisted model exactly.
#
# Version 3 removed `opponent_team` (a season-specific club ID used as a
# number, which carries no meaning across seasons) and the `xP`/`form_5`
# columns (exact copies of points_avg_5), and added the official fixture
# difficulty. Rolling-origin validation over 2023-24, 2024-25 and 2025-26
# preferred this set; see docs/MODEL_PIPELINE.md.
#
# Version 4 added `history_gw_count` (completed Gameweeks in the window,
# 0-5). Without it "no history yet" and "five Gameweeks without minutes"
# were the same all-zero row, so regular starters were forecast like
# benched players at the start of a season (GW1 bias about -1 point).
FEATURE_COLUMNS = (
    "price",
    "was_home",
    "points_last_3",
    "points_last_5",
    "points_avg_5",
    "minutes_last_5",
    "starts_last_5",
    "goals_last_5",
    "assists_last_5",
    "bps_avg_5",
    "influence_avg_5",
    "creativity_avg_5",
    "threat_avg_5",
    "ict_index_avg_5",
    "history_gw_count",
    "fixture_difficulty",
    "position",
)

CATEGORICAL_COLUMNS = (
    "position",
)

NUMERIC_COLUMNS = tuple(
    column
    for column in FEATURE_COLUMNS
    if column not in CATEGORICAL_COLUMNS
)


class FeatureContractError(ValueError):
    """Raised when a source cannot provide a valid canonical model row."""


def build_feature_row(
    source: Mapping[str, object],
) -> dict[str, object]:
    """
    Normalize one source row into the canonical model-input contract.

    The returned dictionary always follows FEATURE_COLUMNS order.
    """

    missing = [
        column
        for column in FEATURE_COLUMNS
        if column not in source
    ]

    if missing:
        raise FeatureContractError(
            f"Missing required feature(s): {', '.join(missing)}"
        )

    row: dict[str, object] = {}

    for column in FEATURE_COLUMNS:
        value = source[column]

        if column == "position":
            if not isinstance(value, str) or not value.strip():
                raise FeatureContractError(
                    "position must be a non-empty string"
                )

            row[column] = value.strip()
            continue

        if isinstance(value, bool):
            row[column] = float(value)
            continue

        try:
            row[column] = float(value)
        except (TypeError, ValueError) as error:
            raise FeatureContractError(
                f"{column} must be numeric"
            ) from error
        if not math.isfinite(row[column]):
            raise FeatureContractError(f"{column} must be finite")

    return row


def feature_matrix(frame) -> "pd.DataFrame":
    """Vectorised build_feature_row(): the exact model input for many rows."""
    import numpy as np
    import pandas as pd

    missing = [column for column in FEATURE_COLUMNS if column not in frame.columns]
    if missing:
        raise FeatureContractError(f"Missing required feature(s): {', '.join(missing)}")
    matrix = frame.loc[:, list(FEATURE_COLUMNS)].copy()
    position = matrix["position"]
    if not position.map(lambda value: isinstance(value, str) and bool(value.strip())).all():
        raise FeatureContractError("position must be a non-empty string")
    matrix["position"] = position.str.strip()
    for column in NUMERIC_COLUMNS:
        try:
            values = pd.to_numeric(matrix[column], errors="raise").astype(float)
        except (TypeError, ValueError) as error:
            raise FeatureContractError(f"{column} must be numeric") from error
        if not np.isfinite(values.to_numpy()).all():
            raise FeatureContractError(f"{column} must be finite")
        matrix[column] = values
    return matrix.reset_index(drop=True)


def validate_frame_provenance(frame, gw_column: str = "GW") -> None:
    """Vectorised validate_feature_provenance() for a whole feature frame."""
    import numpy as np
    import pandas as pd

    for column in ("feature_contract_version", "xp_source", "history_cutoff_gw", "xP", "points_avg_5"):
        if column not in frame.columns:
            raise FeatureContractError(
                "Feature provenance is missing or incompatible; regenerate features and retrain required.")
    if (pd.to_numeric(frame["feature_contract_version"], errors="coerce") != FEATURE_CONTRACT_VERSION).any() \
            or (frame["xp_source"] != XP_SOURCE).any():
        raise FeatureContractError(
            "Feature provenance is missing or incompatible; regenerate features and retrain required.")
    cutoff = pd.to_numeric(frame["history_cutoff_gw"], errors="coerce").to_numpy(float)
    target = pd.to_numeric(frame[gw_column], errors="coerce").to_numpy(float)
    if not np.isfinite(cutoff).all() or (cutoff < 0).any() or (cutoff >= target).any() \
            or (cutoff != np.round(cutoff)).any():
        raise FeatureContractError("History cutoff must precede the target Gameweek")
    xp = pd.to_numeric(frame["xP"], errors="coerce").to_numpy(float)
    average = pd.to_numeric(frame["points_avg_5"], errors="coerce").to_numpy(float)
    if not (np.isfinite(xp) & np.isfinite(average)).all() or not np.allclose(xp, average, rtol=0, atol=1e-8):
        raise FeatureContractError("xP does not match its completed-history recipe")


def validate_feature_provenance(source: Mapping[str, object], target_gw: int) -> None:
    """Version semantics separately from column names; legacy rows are unverified."""
    if (source.get("feature_contract_version") != FEATURE_CONTRACT_VERSION
            or source.get("xp_source") != XP_SOURCE):
        raise FeatureContractError(
            "Feature provenance is missing or incompatible; regenerate features and retrain required.")
    try:
        cutoff = float(source["history_cutoff_gw"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FeatureContractError("Feature provenance lacks a valid history cutoff") from exc
    if not math.isfinite(cutoff) or cutoff < 0 or cutoff >= target_gw or cutoff != int(cutoff):
        raise FeatureContractError("History cutoff must precede the target Gameweek")
    try:
        xp, average = float(source["xP"]), float(source["points_avg_5"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FeatureContractError("xP recipe requires a completed-history points mean") from exc
    if not math.isfinite(xp) or not math.isfinite(average) or not math.isclose(xp, average, abs_tol=1e-8):
        raise FeatureContractError("xP does not match its completed-history recipe")


def validate_model_metadata(model: object) -> dict[str, object]:
    metadata = getattr(model, "feature_contract_metadata_", None)
    if not isinstance(metadata, Mapping) or any(
        metadata.get(key) != value for key, value in feature_metadata().items()
    ):
        raise FeatureContractError(
            "Persisted model provenance is missing or incompatible; honest retraining and revalidation required.")
    validate_model_feature_names(tuple(getattr(model, "feature_names_in_", ())))
    return dict(metadata)


def validate_model_feature_names(
    feature_names: list[str] | tuple[str, ...],
) -> None:
    """
    Reject a persisted model trained against a different feature contract.
    """

    if tuple(feature_names) != FEATURE_COLUMNS:
        raise FeatureContractError(
            "Persisted model feature contract differs from "
            "the current contract; retrain required."
        )
