"""Train the FPL points model (feature contract v3).

Training is strictly time-ordered. Model choices were made with
rolling-origin validation on completed seasons only (each season scored by a
model trained on the seasons before it). The production model is trained on
every completed season and certified by `historical_data.validate_model`,
which scores it on the current season's completed Gameweeks: data the model
never saw during training or model selection.

Run `python -m historical_data.validate_model` to train, validate and certify.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

# Allow the script to be executed directly from historical_data/ while
# importing the canonical contract from the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from feature_contract import (  # noqa: E402
    CATEGORICAL_COLUMNS,
    FEATURE_COLUMNS,
    NUMERIC_COLUMNS,
    feature_matrix,
    validate_frame_provenance,
)


BASE_DIR = PROJECT_ROOT / "historical_data"
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_OUTPUT = MODEL_DIR / "fpl_model_v4.pkl"

# Every completed season. The current season is the held-out test.
TRAIN_SEASONS = (
    "2020-21",
    "2021-22",
    "2022-23",
    "2023-24",
    "2024-25",
    "2025-26",
)

# Kept for the historical backtest harness: the last completed season.
TEST_SEASON = "2025-26"

FEATURES = list(FEATURE_COLUMNS)


def load_season(season: str) -> pd.DataFrame:
    """Load one generated historical feature dataset."""
    file = BASE_DIR / season / "features.csv"

    if not file.exists():
        raise FileNotFoundError(
            f"Missing feature dataset for {season}: {file}"
        )

    df = pd.read_csv(file)

    required = {"player_id", "GW", "total_points"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"{season}/features.csv mangler kolonne(r): "
            + ", ".join(sorted(missing))
        )

    df["season"] = season
    return df


def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    """Validate feature provenance and attach the same-fixture target.

    A feature row for Gameweek G is the prediction snapshot for one fixture
    in G: rolling player features exclude G itself, fixture context belongs
    to G, and the target is the points from that fixture.
    """
    result = df.sort_values(["player_id", "GW"], kind="mergesort").copy()
    validate_frame_provenance(result)
    result["target"] = pd.to_numeric(result["total_points"], errors="coerce")
    result = result.dropna(subset=["target"]).copy()
    result["position"] = result["position"].astype(str).str.strip()

    if result["position"].eq("").any():
        raise ValueError("Historical data contains an empty position value.")

    if result.empty:
        raise ValueError("No trainable rows remain after target preparation.")

    # Every input is validated; an invalid historical value is not a recorded zero.
    feature_matrix(result)
    return result


def build_model() -> Pipeline:
    """Position one-hot encoding + histogram gradient boosting."""
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                list(CATEGORICAL_COLUMNS),
            ),
            (
                "numeric",
                "passthrough",
                list(NUMERIC_COLUMNS),
            ),
        ]
    )

    model = HistGradientBoostingRegressor(
        max_iter=400,
        learning_rate=0.05,
        max_leaf_nodes=31,
        min_samples_leaf=100,
        l2_regularization=1.0,
        random_state=42,
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", model),
        ]
    )


def make_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Convert rows to the exact canonical model-input matrix."""
    matrix = feature_matrix(df)
    if tuple(matrix.columns) != FEATURE_COLUMNS:
        raise ValueError(
            "Generated feature matrix does not match FEATURE_COLUMNS."
        )
    return matrix


def evaluate_model(
    pipeline: Pipeline,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    test_rows: pd.DataFrame,
) -> None:
    """Print deterministic evaluation metrics and sample predictions."""
    predictions = pipeline.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)
    rmse = float(np.sqrt(mean_squared_error(y_test, predictions)))
    r2 = r2_score(y_test, predictions)

    print(f"MAE:  {mae:.3f}")
    print(f"RMSE: {rmse:.3f}")
    print(f"R²:   {r2:.3f}")

    results = test_rows[["position", "GW", "total_points"]].copy()

    def display_name(row):
        for column in ["web_name", "second_name"]:
            value = row.get(column)
            if pd.notna(value) and str(value).strip():
                return str(value).strip()
        return f"Player {row.get('player_id', 'Unknown')}"

    results["name"] = test_rows.apply(display_name, axis=1)
    results["predicted"] = predictions
    results = results.sort_values(
        ["predicted", "name"],
        ascending=[False, True],
        kind="mergesort",
    )

    for _, row in results.head(20).iterrows():
        print(
            f"{str(row['name']):<30} "
            f"GW {int(row['GW']):2d} "
            f"Actual {float(row['total_points']):4.1f} "
            f"Pred {float(row['predicted']):5.2f}"
        )


def main() -> None:
    from historical_data.validate_model import main as validate

    validate()


if __name__ == "__main__":
    main()
