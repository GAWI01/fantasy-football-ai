"""Build next-GW features from completed Gameweeks, without fetching data."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from feature_contract import FEATURE_CONTRACT_VERSION, XP_SOURCE
from historical_data.current_data.xmins import build_xmins_columns, calculate_xmins

BASE = Path(__file__).resolve().parent
PLAYERS_FILE = BASE / "players_current.csv"
GW1_FILE = BASE / "gw1_history.csv"
OUTPUT_FILE = BASE / "players_features_current.csv"


def _read_history(path: Path, event: int) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "player_id" not in frame:
        raise ValueError(f"History lacks player_id: {path.name}")
    if "GW" in frame or "round" in frame:
        frame["GW"] = pd.to_numeric(frame.get("GW", frame.get("round")), errors="raise")
        return frame
    # Legacy event files contain cumulative bootstrap metadata alongside event
    # statistics. Only event suffixes are authoritative; cumulative metadata
    # cannot prove when the bootstrap was collected and must not fill event ICT.
    result = frame[["player_id"]].copy()
    result["GW"] = event
    aliases = {"goals_scored": "goals", "starts": "started"}
    for column in ["minutes", "total_points", "goals_scored", "assists", "starts",
                   "bps", "influence", "creativity", "threat", "ict_index"]:
        source = f"{aliases.get(column, column)}_gw{event}"
        if source in frame:
            result[column] = frame[source]
    return result


def build_current_features(players: pd.DataFrame, history: pd.DataFrame,
                           target_gw: int, *, available_events: set[int]) -> pd.DataFrame:
    result = players.copy()
    if result["player_id"].duplicated().any():
        raise ValueError("Current player IDs must be unique")
    history = history[pd.to_numeric(history["GW"], errors="raise") < target_gw].copy()
    required = ["minutes", "total_points", "goals_scored", "assists", "bps",
                "influence", "creativity", "threat", "ict_index"]
    for column in required:
        if column not in history:
            raise ValueError(f"Completed history missing {column}; regenerate event history")
        history[column] = pd.to_numeric(history[column], errors="raise")
        if history[column].isna().any():
            raise ValueError(f"Completed history contains missing {column}")
    if "starts" not in history:
        history["starts"] = (history["minutes"] >= 60).astype(int)
    # Same historical semantics: sums per GW, ICT/BPS means per GW, then rolling
    # across completed GWs. A DGW never consumes its own first leg.
    level = history.groupby(["player_id", "GW"], as_index=False).agg(
        **{column: (column, "sum") for column in
           ["minutes", "total_points", "goals_scored", "assists", "starts"]},
        **{column: (column, "mean") for column in
           ["bps", "influence", "creativity", "threat", "ict_index"]})
    first_window = max(1, target_gw - 5)
    level = level[level["GW"] >= first_window].sort_values(["player_id", "GW"])
    summaries = []
    for player_id, group in level.groupby("player_id"):
        summary = {"player_id": player_id, "history_gw_count": len(group),
                   "history_cutoff_gw": int(group["GW"].max()),
                   "points_last_3": group.loc[group["GW"] >= target_gw - 3, "total_points"].sum(),
                   "points_last_5": group["total_points"].sum(),
                   "points_avg_5": group["total_points"].mean(),
                   "minutes_last_5": group["minutes"].sum(),
                   "starts_last_5": group["starts"].sum(),
                   "goals_last_5": group["goals_scored"].sum(),
                   "assists_last_5": group["assists"].sum()}
        summary.update({f"{column}_avg_5": group[column].mean() for column in
                        ["bps", "influence", "creativity", "threat", "ict_index"]})
        summaries.append(summary)
    rolling_columns = ["history_gw_count", "history_cutoff_gw", "points_last_3", "points_last_5",
                       "points_avg_5", "minutes_last_5", "starts_last_5", "goals_last_5",
                       "assists_last_5", "bps_avg_5", "influence_avg_5", "creativity_avg_5",
                       "threat_avg_5", "ict_index_avg_5"]
    result = result.drop(columns=[c for c in rolling_columns if c in result])
    summary_frame = pd.DataFrame(summaries, columns=["player_id", *rolling_columns])
    result = result.merge(summary_frame, on="player_id", how="left", validate="one_to_one")
    # Missing history is distinct from a recorded zero before the xMins fallback.
    missing_history = result["history_gw_count"].isna()
    result.loc[missing_history, ["history_gw_count", "history_cutoff_gw"]] = 0
    result = build_xmins_columns(result)
    result[rolling_columns] = result[rolling_columns].fillna(0)
    result["form_5"] = result["points_avg_5"]
    result["xP"] = result["points_avg_5"]
    result["feature_contract_version"] = FEATURE_CONTRACT_VERSION
    result["xp_source"] = XP_SOURCE
    result["history_complete"] = set(range(first_window, target_gw)).issubset(available_events)
    result["prediction_event"] = target_gw
    result["reliable_starter"] = ((result.xmins >= 60) & (result.availability_multiplier >= .75)).astype(int)
    if "web_name" in result:
        result["name"] = result["web_name"].fillna(result.get("second_name", result.player_id.astype(str)))
    elif "second_name" in result:
        result["name"] = result["second_name"].fillna(result.player_id.astype(str))
    result = result.drop(columns=["first_name"], errors="ignore")
    return result


def main() -> None:
    gameweeks = pd.read_csv(BASE / "gameweeks_current.csv")
    next_events = gameweeks[gameweeks["is_next"].astype(str).str.lower().eq("true")]
    if len(next_events) != 1:
        raise ValueError("Exactly one next Gameweek is required")
    target_gw = int(next_events.iloc[0]["id"])
    frames, available = [], set()
    for path in sorted(BASE.glob("gw*_history.csv")):
        match = re.fullmatch(r"gw(\d+)_history\.csv", path.name)
        if match and int(match[1]) < target_gw:
            event = int(match[1])
            frames.append(_read_history(path, event))
            available.add(event)
    if not frames:
        raise ValueError("No completed event history is available; fetch it before building features")
    result = build_current_features(pd.read_csv(PLAYERS_FILE), pd.concat(frames, ignore_index=True),
                                    target_gw, available_events=available)
    result.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved {len(result)} players for GW{target_gw}: {OUTPUT_FILE}")
    if not result.history_complete.all():
        print("History coverage is incomplete; prediction regeneration remains blocked.")


if __name__ == "__main__":
    main()
