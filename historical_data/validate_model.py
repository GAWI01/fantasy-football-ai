"""Train, validate and certify the production FPL points model.

One command: `python -m historical_data.validate_model`.

1. Rebuild features for every season with the shared feature code.
2. Method evidence: rolling-origin validation on completed seasons (each
   season scored by a model trained only on the seasons before it). These
   folds were used to choose the model and features.
3. Train the production model on every completed season.
4. Held-out test: the current season's completed Gameweeks, which were used
   neither for training nor for model selection, against a simple baseline.
5. Causality: changing every outcome from Gameweek G onwards must leave the
   features for Gameweek G unchanged.
6. Production parity: the live forecasting path (history before G plus the
   G fixtures) must reproduce the historical feature rows and predictions.

The model is certified only if it beats the baseline on the held-out data and
both checks pass. Otherwise the report records `validation_state=failed`, no
certificate is written and the command exits non-zero.
"""

from __future__ import annotations

import hashlib
import json
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from scipy.stats import spearmanr

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from feature_contract import FEATURE_COLUMNS, feature_metadata  # noqa: E402
from historical_data.build_features import OUTCOME_COLUMNS, ROLLING_COLUMNS, build_feature_frame  # noqa: E402
from historical_data.forecast import live_feature_rows, players_snapshot_from_history, predict_fixture_points  # noqa: E402
from historical_data.train_model import (  # noqa: E402
    BASE_DIR,
    MODEL_OUTPUT,
    TRAIN_SEASONS,
    build_model,
    make_feature_matrix,
    prepare_data,
)

SELECTION_SEASONS = ("2023-24", "2024-25", "2025-26")
BASELINE = "points_avg_5"
REPORT_SUFFIX = ".validation.json"
CERTIFICATE_SUFFIX = ".metadata.json"
KNOWN_LIMITATIONS = [
    "Historical fixture difficulty comes from end-of-season snapshots of the official FDR; "
    "the current season uses the official values at prediction time.",
    "The official availability multiplier (injury/suspension chance) is a rule applied after "
    "the model and cannot be validated historically: past availability flags are not archived.",
    "Players with no completed history this season (new signings) are scored from price, "
    "position and fixture only.",
]


def season_rows(season: str) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    directory = BASE_DIR / season
    raw = pd.read_csv(directory / "merged_gw.csv")
    fixtures_file = directory / "fixtures.csv"
    return raw, (pd.read_csv(fixtures_file) if fixtures_file.exists() else None)


def season_features(season: str, write: bool = True) -> pd.DataFrame:
    raw, fixtures = season_rows(season)
    frame = build_feature_frame(raw, fixtures)
    if write:
        frame.to_csv(BASE_DIR / season / "features.csv", index=False, lineterminator="\n")
    return frame.assign(season=season)


def held_out_season() -> str:
    pattern = re.compile(r"\d{4}-\d{2}")
    later = sorted(
        path.name for path in BASE_DIR.iterdir()
        if path.is_dir() and pattern.fullmatch(path.name) and path.name not in TRAIN_SEASONS
        and int(path.name[:4]) > int(TRAIN_SEASONS[-1][:4]) and (path / "merged_gw.csv").is_file()
    )
    if len(later) != 1:
        raise RuntimeError(f"Expected exactly one current season after training seasons, found {later}")
    return later[0]


def score(rows: pd.DataFrame, predicted: np.ndarray) -> dict:
    """Fixture-level error plus player-level ranking quality per Gameweek."""
    actual = rows["total_points"].to_numpy(float)
    error = predicted - actual
    frame = rows[["GW", "player_id"]].assign(predicted=predicted, actual=actual)
    players = frame.groupby(["GW", "player_id"], as_index=False)[["predicted", "actual"]].sum()
    correlations, top_ten = [], []
    for _, group in players.groupby("GW"):
        if group["predicted"].nunique() > 1:
            correlations.append(spearmanr(group["predicted"], group["actual"]).statistic)
        top_ten.append(group.nlargest(10, "predicted")["actual"].mean())
    return {
        "rows": int(len(rows)),
        "mae": float(np.abs(error).mean()),
        "rmse": float(np.sqrt((error ** 2).mean())),
        "bias": float(error.mean()),
        "spearman_by_gw": float(np.mean(correlations)) if correlations else None,
        "top10_actual_points": float(np.mean(top_ten)),
    }


def compare(model, rows: pd.DataFrame) -> dict:
    model_metrics = score(rows, predict_fixture_points(model, rows))
    baseline_metrics = score(rows, rows[BASELINE].to_numpy(float))
    return {"model": model_metrics, "baseline": baseline_metrics,
            "beats_baseline": bool(model_metrics["mae"] < baseline_metrics["mae"]
                                   and model_metrics["rmse"] < baseline_metrics["rmse"])}


def fit(frames: list[pd.DataFrame]):
    train = prepare_data(pd.concat(frames, ignore_index=True))
    model = build_model()
    model.fit(make_feature_matrix(train), train["target"].astype(float))
    return model


def rolling_origin(frames: dict[str, pd.DataFrame]) -> list[dict]:
    folds = []
    for season in SELECTION_SEASONS:
        earlier = [frames[name] for name in TRAIN_SEASONS if int(name[:4]) < int(season[:4])]
        model = fit(earlier)
        folds.append({"validation_season": season,
                      "train_seasons": [name for name in TRAIN_SEASONS if int(name[:4]) < int(season[:4])],
                      **compare(model, prepare_data(frames[season]))})
    return folds


def causality_check(raw: pd.DataFrame, fixtures: pd.DataFrame, frame: pd.DataFrame) -> dict:
    """Scrambling outcomes from GW G onwards must not change GW G features."""
    rng = np.random.default_rng(7)
    checked, worst = [], 0.0
    columns = [c for c in (*FEATURE_COLUMNS, *ROLLING_COLUMNS) if c != "position"]
    for gw in sorted(frame["GW"].unique()):
        scrambled = raw.copy()
        future = pd.to_numeric(scrambled["GW"], errors="raise") >= gw
        for column in OUTCOME_COLUMNS:
            if column in scrambled.columns:
                scrambled.loc[future, column] = rng.integers(0, 120, int(future.sum()))
        rebuilt = build_feature_frame(scrambled, fixtures)
        left = frame[frame["GW"] == gw].set_index(["player_id", "fixture"]).sort_index()[columns]
        right = rebuilt[rebuilt["GW"] == gw].set_index(["player_id", "fixture"]).sort_index()[columns]
        if not left.index.equals(right.index):
            return {"passed": False, "gameweek": int(gw), "reason": "row sets differ"}
        worst = max(worst, float(np.abs(left.to_numpy(float) - right.to_numpy(float)).max()))
        checked.append(int(gw))
    return {"passed": worst == 0.0, "gameweeks": checked, "max_abs_difference": worst}


def parity_check(model, raw: pd.DataFrame, fixtures: pd.DataFrame, frame: pd.DataFrame) -> dict:
    """The live path must reproduce historical feature rows and predictions."""
    columns = [c for c in (*FEATURE_COLUMNS, *ROLLING_COLUMNS) if c != "position"]
    checked, worst_feature, worst_prediction = [], 0.0, 0.0
    for gw in sorted(frame["GW"].unique()):
        played = raw[pd.to_numeric(raw["GW"], errors="raise") == gw]
        players = players_snapshot_from_history(played, fixtures)
        live, _ = live_feature_rows(raw, players, fixtures, int(gw))
        live = live.set_index(["player_id", "fixture"]).sort_index()
        expected = frame[frame["GW"] == gw].set_index(["player_id", "fixture"]).sort_index()
        if not live.index.equals(expected.index):
            missing = len(expected.index.difference(live.index))
            extra = len(live.index.difference(expected.index))
            return {"passed": False, "gameweek": int(gw), "reason": f"row sets differ ({missing} missing, {extra} extra)"}
        if not (live["position"] == expected["position"]).all():
            return {"passed": False, "gameweek": int(gw), "reason": "positions differ"}
        worst_feature = max(worst_feature, float(np.abs(
            live[columns].to_numpy(float) - expected[columns].to_numpy(float)).max()))
        worst_prediction = max(worst_prediction, float(np.abs(
            predict_fixture_points(model, live.reset_index()) - predict_fixture_points(model, expected.reset_index())
        ).max()))
        checked.append(int(gw))
    return {"passed": worst_feature == 0.0 and worst_prediction == 0.0, "gameweeks": checked,
            "max_abs_feature_difference": worst_feature, "max_abs_prediction_difference": worst_prediction}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(model_path: Path = MODEL_OUTPUT) -> dict:
    holdout = held_out_season()
    frames = {season: season_features(season) for season in TRAIN_SEASONS}
    current_raw, current_fixtures = season_rows(holdout)
    current_frame = season_features(holdout)
    current_frame = current_frame[current_frame["total_points"].notna()]

    folds = rolling_origin(frames)
    model = fit([frames[season] for season in TRAIN_SEASONS])
    model.feature_contract_metadata_ = {**feature_metadata(), "validation_state": "unverified"}
    held_out = compare(model, prepare_data(current_frame))
    causality = causality_check(current_raw, current_fixtures, current_frame)
    parity = parity_check(model, current_raw, current_fixtures, current_frame)
    passed = held_out["beats_baseline"] and causality["passed"] and parity["passed"]

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path, compress=3)
    inputs = {}
    for season in (*TRAIN_SEASONS, holdout):
        for name in ("merged_gw.csv", "fixtures.csv"):
            file = BASE_DIR / season / name
            if file.is_file():
                inputs[f"{season}/{name}"] = sha256(file)
    report = {
        **feature_metadata(),
        "validation_state": "validated" if passed else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_file": model_path.name,
        "model_sha256": sha256(model_path),
        "model_type": type(model.named_steps["model"]).__name__,
        "feature_columns": list(FEATURE_COLUMNS),
        "sklearn_version": sklearn.__version__,
        "python_version": platform.python_version(),
        "train_seasons": list(TRAIN_SEASONS),
        "held_out_season": holdout,
        "held_out_gameweeks": sorted(int(gw) for gw in current_frame["GW"].unique()),
        "metrics": held_out["model"],
        "baseline": {"name": BASELINE, "metrics": held_out["baseline"]},
        "model_beats_baseline": held_out["beats_baseline"],
        "selection": {"method": "rolling-origin over completed seasons", "folds": folds},
        "xp_timing_verified": causality["passed"],
        "causality": causality,
        "production_parity_verified": parity["passed"],
        "parity": parity,
        "input_sha256": inputs,
        "known_limitations": KNOWN_LIMITATIONS,
    }
    report_path = model_path.with_suffix(model_path.suffix + REPORT_SUFFIX)
    report_bytes = (json.dumps(report, indent=2) + "\n").encode("utf-8")
    report_path.write_bytes(report_bytes)
    certificate_path = model_path.with_suffix(model_path.suffix + CERTIFICATE_SUFFIX)
    if passed:
        certificate = {
            **feature_metadata(),
            "validation_state": "validated",
            "model_sha256": report["model_sha256"],
            "sklearn_version": sklearn.__version__,
            "validation_report_file": report_path.name,
            "validation_report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        }
        certificate_path.write_text(json.dumps(certificate, indent=2) + "\n", encoding="utf-8")
    else:
        certificate_path.unlink(missing_ok=True)
    return report


def main() -> None:
    report = run()
    held = report["metrics"]
    base = report["baseline"]["metrics"]
    print(f"Held-out {report['held_out_season']} GW{report['held_out_gameweeks'][0]}-"
          f"GW{report['held_out_gameweeks'][-1]} ({held['rows']} fixture rows)")
    print(f"  model    MAE {held['mae']:.3f}  RMSE {held['rmse']:.3f}  top-10 {held['top10_actual_points']:.2f}")
    print(f"  baseline MAE {base['mae']:.3f}  RMSE {base['rmse']:.3f}  top-10 {base['top10_actual_points']:.2f}")
    for fold in report["selection"]["folds"]:
        print(f"  fold {fold['validation_season']}: model MAE {fold['model']['mae']:.3f} "
              f"vs baseline {fold['baseline']['mae']:.3f}")
    print(f"  causality: {report['causality']['passed']}  parity: {report['production_parity_verified']}")
    print(f"Validation state: {report['validation_state']}")
    if report["validation_state"] != "validated":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
