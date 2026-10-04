"""Canonical, validated model-input contract shared by training and live runs."""

from __future__ import annotations

from collections.abc import Mapping
import math


FEATURE_CONTRACT_VERSION = 2
XP_SOURCE = "previous_completed_gw_points_mean_v1"
MODEL_TARGET = "same_fixture_total_points"


def feature_metadata() -> dict[str, object]:
    return {"feature_contract_version": FEATURE_CONTRACT_VERSION,
            "xp_source": XP_SOURCE, "target": MODEL_TARGET}


# This must match the persisted model exactly.
FEATURE_COLUMNS = (
    "xP",
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
    "form_5",
    "position",
    "opponent_team",
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

    xP is optional for backwards compatibility with older training/test
    sources. When it is absent, it defaults to 0.0.

    The returned dictionary always follows FEATURE_COLUMNS order.
    """

    # xP was added to the live/model contract later than some of the
    # original training/test fixtures. Keep it optional at the boundary,
    # while always emitting it in the canonical row.
    missing = [
        column
        for column in FEATURE_COLUMNS
        if column != "xP" and column not in source
    ]

    if missing:
        raise FeatureContractError(
            f"Missing required feature(s): {', '.join(missing)}"
        )

    row: dict[str, object] = {}

    for column in FEATURE_COLUMNS:
        # Backwards-compatible default for old training/test rows.
        if column == "xP" and column not in source:
            row[column] = 0.0
            continue

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
