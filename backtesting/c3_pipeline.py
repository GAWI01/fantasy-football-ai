"""One-command C3 training, backtest, and verification pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from feature_contract import FEATURE_COLUMNS, feature_metadata, validate_model_feature_names, validate_feature_provenance
from historical_data.train_model import (
    TRAIN_SEASONS,
    TEST_SEASON,
    build_model,
    load_season,
    make_feature_matrix,
    prepare_data,
)
from .production_adapter import FPLHistoricalPredictionAdapter


@dataclass(frozen=True)
class C3PipelineConfig:
    project_root: Path
    corrected_model_name: str = "fpl_model_v1_corrected.pkl"
    small_start_gw: int = 1
    small_end_gw: int = 6
    full_start_gw: int = 1
    full_end_gw: int | None = None

    @property
    def original_model_path(self) -> Path:
        return self.project_root / "models" / "fpl_model_v1.pkl"

    @property
    def corrected_model_path(self) -> Path:
        return self.project_root / "models" / self.corrected_model_name

    @property
    def report_dir(self) -> Path:
        return self.project_root / "backtesting" / "reports"


def calculate_backtest_metrics(frame: pd.DataFrame) -> dict:
    """Return deterministic aggregate prediction metrics."""
    required = {"predicted_points", "actual_points"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(
            "Backtest result missing column(s): " + ", ".join(sorted(missing))
        )
    if frame.empty:
        raise ValueError("Cannot calculate metrics from an empty backtest.")

    y_true = pd.to_numeric(frame["actual_points"], errors="coerce")
    y_pred = pd.to_numeric(frame["predicted_points"], errors="coerce")
    valid = y_true.notna() & y_pred.notna()
    if not valid.any():
        raise ValueError("Backtest contains no numeric prediction/actual pairs.")

    y_true = y_true[valid]
    y_pred = y_pred[valid]

    return {
        "rows": int(len(y_true)),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mean_actual": float(y_true.mean()),
        "mean_predicted": float(y_pred.mean()),
    }



def calculate_xp_baseline_metrics(
    result: pd.DataFrame,
    feature_frame: pd.DataFrame,
) -> dict:
    """Evaluate the existing historical xP feature as a simple baseline."""
    for _, row in feature_frame.iterrows():
        validate_feature_provenance(row.to_dict(), int(row["GW"]))
    baseline = (
        feature_frame.groupby(["GW", "player_id"], as_index=False)["xP"]
        .sum()
        .rename(columns={"GW": "target_gw", "xP": "xp_baseline"})
    )
    merged = result.merge(
        baseline,
        on=["target_gw", "player_id"],
        how="left",
        validate="one_to_one",
    )
    merged["xp_baseline"] = pd.to_numeric(
        merged["xp_baseline"], errors="coerce"
    ).fillna(0.0)
    baseline_frame = merged[
        ["actual_points", "xp_baseline"]
    ].rename(columns={"xp_baseline": "predicted_points"})
    return calculate_backtest_metrics(baseline_frame)


def calculate_per_gw_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Return MAE/RMSE and sample size for each target Gameweek."""
    rows = []
    for gw, group in frame.groupby("target_gw", sort=True):
        metrics = calculate_backtest_metrics(group)
        rows.append({"target_gw": int(gw), **metrics})
    return pd.DataFrame(rows)


def validate_backtest_results(
    frame: pd.DataFrame,
    *,
    decision_gw_column: str = "GW",
) -> None:
    """Reject structurally invalid or lookahead-shaped backtest results."""
    required = {
        decision_gw_column,
        "target_gw",
        "predicted_points",
        "actual_points",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(
            "Backtest result missing column(s): " + ", ".join(sorted(missing))
        )
    if frame.empty:
        raise ValueError("Backtest produced no comparable rows.")

    decision = pd.to_numeric(frame[decision_gw_column], errors="coerce")
    target = pd.to_numeric(frame["target_gw"], errors="coerce")
    if decision.isna().any() or target.isna().any():
        raise ValueError("Backtest contains invalid Gameweek values.")
    if not (target == decision + 1).all():
        raise ValueError("Backtest target GW must always equal decision GW + 1.")


def train_corrected_model(config: C3PipelineConfig) -> Path:
    """Train the corrected V1 artifact without overwriting the original."""
    if not config.original_model_path.exists():
        raise FileNotFoundError(
            f"Original model artifact missing: {config.original_model_path}"
        )

    train_frames = [
        prepare_data(load_season(season))
        for season in TRAIN_SEASONS
    ]
    train = pd.concat(train_frames, ignore_index=True)

    x_train = make_feature_matrix(train)
    y_train = train["target"].astype(float)

    pipeline = build_model()
    pipeline.fit(x_train, y_train)
    pipeline.feature_contract_metadata_ = {**feature_metadata(), "validation_state": "unverified"}

    validate_model_feature_names(tuple(pipeline.feature_names_in_))
    config.corrected_model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, config.corrected_model_path)

    return config.corrected_model_path


def run_backtests(config: C3PipelineConfig) -> dict:
    """Run small and full 2024-25 out-of-sample backtests."""
    adapter = FPLHistoricalPredictionAdapter(
        config.project_root,
        model_path=config.corrected_model_path,
    )

    feature_frame = adapter.load_season(TEST_SEASON)

    small = adapter.backtest_season(
        TEST_SEASON,
        start_gw=config.small_start_gw,
        end_gw=config.small_end_gw,
    )
    validate_backtest_results(small)

    full = adapter.backtest_season(
        TEST_SEASON,
        start_gw=config.full_start_gw,
        end_gw=config.full_end_gw,
    )
    validate_backtest_results(full)

    small_metrics = calculate_backtest_metrics(small)
    full_metrics = calculate_backtest_metrics(full)
    xp_metrics = calculate_xp_baseline_metrics(full, feature_frame)

    per_gw = calculate_per_gw_metrics(full)

    report = {
        "model": str(config.corrected_model_path.relative_to(config.project_root)),
        "train_seasons": list(TRAIN_SEASONS),
        "test_season": TEST_SEASON,
        "small": {
            "start_gw": config.small_start_gw,
            "end_gw": config.small_end_gw,
            "metrics": small_metrics,
        },
        "full": {
            "start_gw": config.full_start_gw,
            "end_gw": int(full["target_gw"].max()),
            "metrics": full_metrics,
            "xp_baseline_metrics": xp_metrics,
            "model_beats_xp_baseline_mae": (
                full_metrics["mae"] < xp_metrics["mae"]
            ),
        },
    }

    config.report_dir.mkdir(parents=True, exist_ok=True)
    small.to_csv(
        config.report_dir / "c3_small_backtest_2024-25.csv",
        index=False,
    )
    full.to_csv(
        config.report_dir / "c3_full_backtest_2024-25.csv",
        index=False,
    )
    per_gw.to_csv(
        config.report_dir / "c3_full_metrics_by_gw_2024-25.csv",
        index=False,
    )
    (config.report_dir / "c3_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    return report


def run(config: C3PipelineConfig) -> dict:
    """Execute corrected training followed by small and full backtests."""
    corrected = train_corrected_model(config)
    report = run_backtests(config)
    report["corrected_model_created"] = str(corrected)
    return report


def main() -> None:
    config = C3PipelineConfig(
        project_root=Path(__file__).resolve().parents[1]
    )
    print("=" * 70)
    print("FPL-AI C3 — CORRECTED TRAINING + BACKTEST")
    print("=" * 70)
    print(f"Original model : {config.original_model_path}")
    print(f"Corrected model: {config.corrected_model_path}")
    print(f"Train seasons  : {', '.join(TRAIN_SEASONS)}")
    print(f"Test season    : {TEST_SEASON}")
    print()
    report = run(config)
    print("TRAINING: PASS")
    print("MODEL ARTIFACT: PASS")
    print("SMALL BACKTEST: PASS")
    print("FULL BACKTEST: PASS")
    print()
    print("SMALL METRICS:")
    print(json.dumps(report["small"]["metrics"], indent=2))
    print()
    print("FULL METRICS:")
    print(json.dumps(report["full"]["metrics"], indent=2))
    print()
    print(f"REPORT: {config.report_dir / 'c3_report.json'}")
    print(f"CORRECTED MODEL: {config.corrected_model_path}")


if __name__ == "__main__":
    main()
