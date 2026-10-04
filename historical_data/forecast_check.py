"""Score each finished Gameweek's pre-deadline forecast against its official results.

The refresh runs this after fetching final scores, so drift (like the
early-season under-forecast that motivated feature contract v4) shows up one
Gameweek after it happens instead of weeks later. Results are appended to
historical_data/current_data/forecast_checks.csv and, under GitHub Actions,
printed as a notice annotation.

The forecast scored is the one Review uses: the latest artifact published
before the Gameweek's deadline. Every current player counts, so a blank or
an unused squad player who scored 0 is part of the score, as in validation.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.review_service import ReviewDataError, select_review_prediction_file  # noqa: E402

CURRENT_DIR = PROJECT_ROOT / "historical_data" / "current_data"
LOG_PATH = CURRENT_DIR / "forecast_checks.csv"
LOG_COLUMNS = [
    "season", "gameweek", "artifact", "model_file", "validation_state", "players",
    "mean_predicted", "mean_actual", "bias", "mae", "rmse", "spearman", "top10_actual",
]


def score_gameweek(predictions: pd.DataFrame, history: pd.DataFrame, gw: int) -> dict:
    """Per-player comparison of forecast and official points for one Gameweek."""
    actual = (history[pd.to_numeric(history["GW"], errors="raise") == gw]
              .groupby("element")["total_points"].sum())
    frame = predictions[["player_id", "predicted_points"]].copy()
    frame["actual"] = frame["player_id"].map(actual).fillna(0.0)
    predicted = frame["predicted_points"].to_numpy(float)
    observed = frame["actual"].to_numpy(float)
    error = predicted - observed
    top10 = frame.nlargest(10, "predicted_points")["actual"].mean()
    return {
        "players": int(len(frame)),
        "mean_predicted": round(float(predicted.mean()), 3),
        "mean_actual": round(float(observed.mean()), 3),
        "bias": round(float(error.mean()), 3),
        "mae": round(float(np.abs(error).mean()), 3),
        "rmse": round(float(np.sqrt((error ** 2).mean())), 3),
        "spearman": round(float(spearmanr(predicted, observed).statistic), 3),
        "top10_actual": round(float(top10), 2),
    }


def check_finished_gameweeks(season: str, history: pd.DataFrame, gameweeks: pd.DataFrame,
                             predictions_dir: Path = CURRENT_DIR, log_path: Path = LOG_PATH) -> list[dict]:
    """Score every finished Gameweek not yet in the log; return the new records."""
    log = pd.read_csv(log_path) if log_path.is_file() else pd.DataFrame(columns=LOG_COLUMNS)
    done = {(str(row.season), int(row.gameweek)) for row in log.itertuples(index=False)}
    finished = sorted(set(pd.to_numeric(history["GW"], errors="raise").astype(int)))
    deadlines = dict(zip(pd.to_numeric(gameweeks["id"]).astype(int), gameweeks["deadline_time"]))
    records = []
    for gw in finished:
        if (season, gw) in done or gw not in deadlines:
            continue
        try:
            artifact = select_review_prediction_file(predictions_dir, gw, deadline_time=deadlines[gw])
        except ReviewDataError:
            continue
        sidecar = json.loads(artifact.with_suffix(artifact.suffix + ".manifest.json").read_text(encoding="utf-8"))
        provenance = sidecar.get("model_provenance") or {}
        records.append({
            "season": season, "gameweek": gw, "artifact": artifact.name,
            "model_file": provenance.get("model_file", "legacy"),
            "validation_state": provenance.get("validation_state", "unverified"),
            **score_gameweek(pd.read_csv(artifact), history, gw),
        })
    if records:
        new = pd.DataFrame(records, columns=LOG_COLUMNS)
        updated = pd.concat([log, new], ignore_index=True) if not log.empty else new
        updated.sort_values(["season", "gameweek"]).to_csv(log_path, index=False, lineterminator="\n")
    return records


def announce(records: list[dict]) -> None:
    for record in records:
        line = (f"GW{record['gameweek']} forecast ({record['artifact']}): predicted {record['mean_predicted']} "
                f"vs actual {record['mean_actual']} points per player (bias {record['bias']:+}), "
                f"RMSE {record['rmse']}, top 10 scored {record['top10_actual']}")
        print(line)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::notice title=Forecast check GW{record['gameweek']}::{line}", flush=True)
