from __future__ import annotations
from typing import Any, Mapping
import pandas as pd

REQUIRED_COLUMNS = {"player_id", "predicted_points"}

def _prepare(frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise ValueError("prediction frame must be a pandas DataFrame")
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError("prediction frame missing required columns: " + ", ".join(sorted(missing)))
    result = frame.copy()
    result["player_id"] = pd.to_numeric(result["player_id"], errors="coerce")
    result["predicted_points"] = pd.to_numeric(result["predicted_points"], errors="coerce")
    if result["player_id"].isna().any() or result["predicted_points"].isna().any():
        raise ValueError("player_id and predicted_points must be numeric")
    result["player_id"] = result["player_id"].astype(int)
    if result["player_id"].duplicated().any():
        raise ValueError("prediction frame player_id must be unique")
    return result

def normalize_horizon_predictions(
    predictions: pd.DataFrame,
    horizon_predictions: Mapping[int, pd.DataFrame] | None,
    horizon: int = 3,
) -> dict[int, pd.DataFrame]:
    if not isinstance(horizon, int) or horizon < 1:
        raise ValueError("horizon must be a positive integer")
    supplied = horizon_predictions or {}
    result = {1: _prepare(supplied.get(1, predictions))}
    for gw, frame in supplied.items():
        gw = int(gw)
        if 2 <= gw <= horizon:
            result[gw] = _prepare(frame)
    return result

def _row_for(frame: pd.DataFrame, player_id: int) -> pd.Series | None:
    match = frame[frame["player_id"] == int(player_id)]
    return None if match.empty else match.iloc[0]

def player_horizon_projection(
    player_id: int,
    predictions_by_gw: Mapping[int, pd.DataFrame],
    horizon: int = 3,
) -> dict[str, Any]:
    gameweeks = []
    for gw in range(1, horizon + 1):
        frame = predictions_by_gw.get(gw)
        if frame is None:
            continue
        row = _row_for(frame, player_id)
        if row is None:
            continue
        points = float(row["predicted_points"])
        xmins = float(row["xmins"]) if "xmins" in row.index and pd.notna(row["xmins"]) else 90.0
        xmins = max(0.0, min(90.0 * max(1, int(row.get("fixture_count", 1) or 1)), xmins))
        gameweeks.append({
            "gameweek": int(row.get("gameweek", gw)),
            "horizon_index": gw,
            "predicted_points": round(points, 3),
            "xmins": round(xmins, 1),
            # Model points already reflect expected minutes and availability;
            # discounting them again for minutes would double-count the risk.
            # The key is kept for API compatibility and equals the points.
            "minutes_adjusted_points": round(points, 3),
            "opponent": row.get("opponent") if "opponent" in row.index else None,
            "home": bool(row["home"]) if "home" in row.index and pd.notna(row["home"]) else None,
            "difficulty": float(row["difficulty"]) if "difficulty" in row.index and pd.notna(row["difficulty"]) else None,
            "availability": str(row["availability"]) if "availability" in row.index and pd.notna(row["availability"]) else "AVAILABLE",
            "projection_method": str(row["projection_method"]) if "projection_method" in row.index and pd.notna(row["projection_method"]) else "native_model",
            "uncertainty": float(row["uncertainty"]) if "uncertainty" in row.index and pd.notna(row["uncertainty"]) else None,
            "fixture_count": int(row["fixture_count"]) if "fixture_count" in row.index and pd.notna(row["fixture_count"]) else 1,
        })
    return {
        "player_id": int(player_id),
        "gameweeks_available": len(gameweeks),
        "coverage": round(len(gameweeks) / max(horizon, 1), 3),
        "predicted_points": round(sum(x["predicted_points"] for x in gameweeks), 3),
        "minutes_adjusted_points": round(sum(x["minutes_adjusted_points"] for x in gameweeks), 3),
        "gameweeks": gameweeks,
    }

def fixture_outlook(
    player_id: int,
    predictions_by_gw: Mapping[int, pd.DataFrame],
    horizon: int = 3,
) -> list[dict[str, Any]]:
    return player_horizon_projection(player_id, predictions_by_gw, horizon)["gameweeks"]

def rank_horizon_players(
    predictions_by_gw: Mapping[int, pd.DataFrame],
    horizon: int = 3,
    top_n: int = 10,
) -> list[dict[str, Any]]:
    ids = set()
    for frame in predictions_by_gw.values():
        ids.update(int(x) for x in frame["player_id"])
    ranked = [
        player_horizon_projection(pid, predictions_by_gw, horizon)
        for pid in ids
    ]
    ranked.sort(key=lambda x: (-x["minutes_adjusted_points"], -x["predicted_points"], x["player_id"]))
    return ranked[:top_n]

def evaluate_transfer_horizon(
    transfers: list[dict[str, Any]],
    predictions_by_gw: Mapping[int, pd.DataFrame],
    horizon: int = 3,
) -> dict[str, Any]:
    """Evaluate a transfer set across the supplied horizon."""
    details = []
    total = 0.0
    coverage = []
    for transfer in transfers:
        out_id = int(transfer["player_out_id"])
        in_id = int(transfer["player_in_id"])
        out_projection = player_horizon_projection(out_id, predictions_by_gw, horizon)
        in_projection = player_horizon_projection(in_id, predictions_by_gw, horizon)
        delta = in_projection["minutes_adjusted_points"] - out_projection["minutes_adjusted_points"]
        details.append({
            "player_out_id": out_id,
            "player_in_id": in_id,
            "horizon_gain": round(delta, 3),
            "out_projection": out_projection,
            "in_projection": in_projection,
        })
        total += delta
        coverage.extend([out_projection["coverage"], in_projection["coverage"]])
    return {
        "horizon_gain": round(total, 3),
        "coverage": round(sum(coverage) / len(coverage), 3) if coverage else 0.0,
        "transfers": details,
    }
