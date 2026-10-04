"""Train the FPL-AI V1.1 prediction model.

Training is strictly time-ordered:
- Train: 2020-21 through 2023-24
- Test: 2024-25

The persisted model input is defined exclusively by feature_contract.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
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
    build_feature_row,
    feature_metadata,
    validate_feature_provenance,
    validate_model_feature_names,
)


BASE_DIR = PROJECT_ROOT / "historical_data"
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_OUTPUT = MODEL_DIR / "fpl_model_v1_corrected.pkl"

TRAIN_SEASONS = (
    "2020-21",
    "2021-22",
    "2022-23",
    "2023-24",
)

TEST_SEASON = "2024-25"

FEATURES = list(FEATURE_COLUMNS)


def load_season(season: str) -> pd.DataFrame:
    """Load one generated historical feature dataset."""
    file = BASE_DIR / season / "features.csv"

    if not file.exists():
        raise FileNotFoundError(
            f"Missing feature dataset for {season}: {file}"
        )

    print(f"Leser {season}...")

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
    """Build a leakage-safe same-fixture target and validate model inputs."""
    result = df.sort_values(["player_id", "GW"]).copy()
    for _, row in result.iterrows():
        validate_feature_provenance(row.to_dict(), int(row["GW"]))

    # The generated historical feature row is the prediction snapshot for
    # its own Gameweek: rolling player features are shifted to exclude the
    # current GW, while fixture context (opponent/home-away) belongs to this
    # GW. Therefore the correct target for row GW G is total_points at G.
    #
    # The previous implementation shifted this target to G+1, which paired
    # GW G fixture context with GW G+1 outcomes and therefore did not match
    # the production prediction semantics.
    result["target"] = pd.to_numeric(
        result["total_points"],
        errors="coerce",
    )

    result = result.dropna(subset=["target"]).copy()

    # Normalize the target and every canonical numeric feature.
    result["target"] = pd.to_numeric(result["target"], errors="coerce")

    for column in NUMERIC_COLUMNS:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    result["position"] = result["position"].astype(str).str.strip()

    invalid_positions = result["position"].eq("").any()
    if invalid_positions:
        raise ValueError("Historical data contains an empty position value.")

    result = result.dropna(subset=["target"]).copy()

    if result.empty:
        raise ValueError("No trainable rows remain after target preparation.")

    # Validate every input; an invalid historical value is not a recorded zero.
    for _, row in result.iterrows():
        build_feature_row(row.to_dict())

    return result


def build_model() -> Pipeline:
    """Create the V1.1 preprocessing + Random Forest pipeline."""
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

    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=12,
        min_samples_leaf=10,
        random_state=42,
        n_jobs=-1,
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", model),
        ]
    )


def make_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Convert rows to the exact canonical model-input matrix."""
    rows = [
        build_feature_row(row)
        for _, row in df.iterrows()
    ]

    matrix = pd.DataFrame(rows, columns=FEATURES)

    # Keep the matrix in exactly the same order as the persisted contract.
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

    print()
    print("=" * 70)
    print("MODEL EVALUERING V1.1")
    print("=" * 70)
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
    results["error"] = results["predicted"] - results["total_points"]

    results = results.sort_values(
        ["predicted", "name"],
        ascending=[False, True],
        kind="mergesort",
    )

    print()
    print("=" * 70)
    print("TOP 20 PREDIKSJONER")
    print("=" * 70)

    for _, row in results.head(20).iterrows():
        print(
            f"{str(row['name']):<30} "
            f"GW {int(row['GW']):2d} "
            f"Actual {float(row['total_points']):4.1f} "
            f"Pred {float(row['predicted']):5.2f}"
        )

    # Store metrics on the function object is deliberately avoided; the
    # persisted artifact remains only the trained pipeline for compatibility.
    return None


def main() -> None:
    print("=" * 70)
    print("FPL AI - ML TRAINING V1.1")
    print("=" * 70)

    print()
    print("KANONISK FEATURE CONTRACT")
    print("-" * 70)
    print(f"Features: {len(FEATURES)}")
    print(" | ".join(FEATURES))

    print()
    print("LASTER DATA")
    print("-" * 70)

    train_frames: list[pd.DataFrame] = []

    for season in TRAIN_SEASONS:
        frame = prepare_data(load_season(season))
        train_frames.append(frame)
        print(f"  {season}: {len(frame)} trainbare rader")

    train = pd.concat(train_frames, ignore_index=True)

    test = prepare_data(load_season(TEST_SEASON))

    print()
    print(f"TRAIN TOTAL: {len(train)} rader")
    print(f"TEST TOTAL:  {len(test)} rader")

    print()
    print("BYGGER MODELLINPUT")
    print("-" * 70)

    X_train = make_feature_matrix(train)
    y_train = train["target"].astype(float)

    X_test = make_feature_matrix(test)
    y_test = test["target"].astype(float)

    print(f"X_train: {X_train.shape}")
    print(f"X_test:  {X_test.shape}")

    print()
    print("TRENER RANDOM FOREST V1.1...")
    print("-" * 70)

    pipeline = build_model()
    pipeline.fit(X_train, y_train)
    pipeline.feature_contract_metadata_ = {**feature_metadata(), "validation_state": "unverified"}

    # sklearn records feature_names_in_ on the pipeline from X_train.
    validate_model_feature_names(
        tuple(pipeline.feature_names_in_)
    )

    print("OK: Modell trent")
    print("OK: Feature contract verifisert")

    evaluate_model(
        pipeline,
        X_test,
        y_test,
        test,
    )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_OUTPUT)

    print()
    print("=" * 70)
    print("MODELL LAGRET")
    print("=" * 70)
    print(f"OK: {MODEL_OUTPUT}")
    print("OK: Persisted input contract verified")
    print()
    print("=" * 70)
    print("ML TRAINING V1.1 FERDIG")
    print("=" * 70)


if __name__ == "__main__":
    main()
