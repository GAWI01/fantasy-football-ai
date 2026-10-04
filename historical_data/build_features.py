"""Canonical FPL feature engineering shared by training, validation and live runs.

`build_feature_frame()` is the only implementation of the model features. It
takes fixture-level rows in the Vaastav `merged_gw.csv` layout and returns the
same rows with causal features attached: every rolling value for Gameweek G is
calculated from the player's completed Gameweeks before G. Rows for fixtures
that have not been played yet (unknown outcome) are allowed, so the live
predictor appends the target Gameweek's fixtures to the season history and
reads its features through exactly the same code as historical training.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# When this file is executed directly, Python puts historical_data/ on
# sys.path rather than the project root. Add the root explicitly so the
# shared feature contract can be imported reliably.
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from feature_contract import FEATURE_CONTRACT_VERSION, XP_SOURCE


SEASONS = [
    "2020-21",
    "2021-22",
    "2022-23",
    "2023-24",
    "2024-25",
    "2025-26",
]

BASE = BASE_DIR / "historical_data"

MODEL_POSITIONS = ("GK", "DEF", "MID", "FWD")
POSITION_ALIASES = {"GKP": "GK"}
ROLLING_WINDOW = 5

SUM_STATS = ("total_points", "minutes", "goals_scored", "assists")
MEAN_STATS = ("bps", "influence", "creativity", "threat", "ict_index")
OUTCOME_COLUMNS = (*SUM_STATS, *MEAN_STATS)

ROLLING_COLUMNS = (
    "history_gw_count",
    "history_cutoff_gw",
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
)


def _normalise_rows(gw: pd.DataFrame) -> pd.DataFrame:
    result = gw.copy()
    if "player_id" not in result.columns:
        if "element" in result.columns:
            result["player_id"] = result["element"]
        elif "id" in result.columns:
            result["player_id"] = result["id"]
        else:
            raise ValueError("Fixture rows need a player ID (element/player_id)")
    if "GW" not in result.columns:
        if "round" not in result.columns:
            raise ValueError("Fixture rows need a Gameweek (GW/round)")
        result["GW"] = result["round"]
    missing = [c for c in ("fixture", "value", "position", "was_home") if c not in result.columns]
    if missing:
        raise ValueError("Fixture rows lack required column(s): " + ", ".join(missing))

    result["player_id"] = pd.to_numeric(result["player_id"], errors="raise").astype(int)
    result["GW"] = pd.to_numeric(result["GW"], errors="raise").astype(int)
    result["fixture"] = pd.to_numeric(result["fixture"], errors="raise").astype(int)

    # Assistant-manager rows ("AM") and any unknown role are not players.
    position = result["position"].astype(str).str.strip().str.upper().replace(POSITION_ALIASES)
    result["position"] = position
    result = result[position.isin(MODEL_POSITIONS)].copy()

    for column in OUTCOME_COLUMNS:
        if column not in result.columns:
            result[column] = np.nan
        result[column] = pd.to_numeric(result[column], errors="coerce")
    if "opponent_team" not in result.columns:
        result["opponent_team"] = np.nan
    for column in ("value", "opponent_team"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["was_home"] = result["was_home"].map(
        lambda value: value if isinstance(value, bool) else str(value).strip().lower() in {"true", "1", "1.0"}
    ).astype(float)
    return result.sort_values(["player_id", "GW", "fixture"], kind="mergesort").reset_index(drop=True)


def _rolling_history(rows: pd.DataFrame) -> pd.DataFrame:
    """Per player and Gameweek, summarise the previous completed Gameweeks.

    A Double Gameweek has several fixture rows for one player/GW. History is
    aggregated to Gameweeks first, so no fixture can see another fixture from
    its own Gameweek. A Gameweek row whose outcome is unknown (a future
    fixture) contributes nothing to later windows.
    """
    played = rows["minutes"].notna()
    gw_level = (
        rows.assign(started=(rows["minutes"] >= 60).astype(float).where(played))
        .groupby(["player_id", "GW"], as_index=False, sort=False)
        .agg(
            **{column: (column, "sum") for column in SUM_STATS},
            starts=("started", "sum"),
            **{column: (column, "mean") for column in MEAN_STATS},
            completed=("minutes", lambda values: bool(values.notna().all())),
        )
        .sort_values(["player_id", "GW"], kind="mergesort")
        .reset_index(drop=True)
    )
    completed = gw_level[gw_level["completed"]].copy()
    if not gw_level["completed"].groupby(gw_level["player_id"]).apply(
        lambda flags: flags.is_monotonic_decreasing
    ).all():
        raise ValueError("A completed Gameweek follows an unplayed one; history is out of order")

    grouped = completed.groupby("player_id", sort=False)

    def window(column: str, size: int, agg: str) -> pd.Series:
        rolled = grouped[column].transform(lambda values: getattr(values.rolling(size, min_periods=1), agg)())
        return rolled

    summary = completed[["player_id", "GW"]].copy()
    summary["history_gw_count"] = grouped["GW"].transform(lambda values: values.rolling(ROLLING_WINDOW, min_periods=1).count())
    summary["history_cutoff_gw"] = completed["GW"]
    summary["points_last_3"] = window("total_points", 3, "sum")
    summary["points_last_5"] = window("total_points", ROLLING_WINDOW, "sum")
    summary["points_avg_5"] = window("total_points", ROLLING_WINDOW, "mean")
    summary["minutes_last_5"] = window("minutes", ROLLING_WINDOW, "sum")
    summary["starts_last_5"] = window("starts", ROLLING_WINDOW, "sum")
    summary["goals_last_5"] = window("goals_scored", ROLLING_WINDOW, "sum")
    summary["assists_last_5"] = window("assists", ROLLING_WINDOW, "sum")
    for column in MEAN_STATS:
        summary[f"{column}_avg_5"] = window(column, ROLLING_WINDOW, "mean")

    # The summary after completed GW H is the input for the player's next GW.
    targets = gw_level[["player_id", "GW"]].copy()
    merged = pd.merge_asof(
        targets.sort_values("GW", kind="mergesort"),
        summary.rename(columns={"GW": "summary_gw"}).sort_values("summary_gw", kind="mergesort"),
        left_on="GW",
        right_on="summary_gw",
        by="player_id",
        allow_exact_matches=False,
        direction="backward",
    ).drop(columns="summary_gw")
    merged[list(ROLLING_COLUMNS)] = merged[list(ROLLING_COLUMNS)].fillna(0.0)
    merged["history_gw_count"] = merged["history_gw_count"].astype(int)
    merged["history_cutoff_gw"] = merged["history_cutoff_gw"].astype(int)
    return merged


def fixture_difficulty(rows: pd.DataFrame, fixtures: pd.DataFrame) -> pd.Series:
    """Official FDR for the player's side of each fixture (home or away)."""
    table = fixtures[["id", "team_h_difficulty", "team_a_difficulty"]].copy()
    table["id"] = pd.to_numeric(table["id"], errors="raise").astype(int)
    joined = rows[["fixture", "was_home"]].merge(table, left_on="fixture", right_on="id", how="left")
    values = np.where(joined["was_home"] > 0, joined["team_h_difficulty"], joined["team_a_difficulty"])
    return pd.Series(pd.to_numeric(values, errors="coerce"), index=rows.index)


def build_feature_frame(gw: pd.DataFrame, fixtures: pd.DataFrame | None = None) -> pd.DataFrame:
    """Attach causal model features to fixture-level rows.

    Outcome columns may be missing (NaN) for fixtures that have not been
    played; those rows still receive features from earlier Gameweeks.
    """
    rows = _normalise_rows(gw)
    history = _rolling_history(rows)
    result = rows.drop(columns=[c for c in ROLLING_COLUMNS if c in rows.columns]).merge(
        history, on=["player_id", "GW"], how="left", validate="many_to_one",
    )
    result["form_5"] = result["points_avg_5"]
    # xP is the mean of completed-Gameweek points: the archived same-GW FPL xP
    # field has no verified pre-deadline timing and is never used.
    result["xP"] = result["points_avg_5"]
    result["price"] = result["value"] / 10.0
    if fixtures is not None:
        result["fixture_difficulty"] = fixture_difficulty(result, fixtures)
    result["feature_contract_version"] = FEATURE_CONTRACT_VERSION
    result["xp_source"] = XP_SOURCE
    result["history_complete"] = True
    numeric = result.select_dtypes(include="number").columns
    result[numeric] = result[numeric].replace([np.inf, -np.inf], np.nan)
    if result[list(ROLLING_COLUMNS)].isna().any(axis=None):
        raise ValueError("Rolling history features have missing values")
    # Every modelled row is validated strictly by feature_contract.feature_matrix();
    # rows that are never modelled (e.g. a blank player's placeholder) may lack
    # fixture context.
    return result


def build_features(season):
    season_dir = BASE / season
    gw_file = season_dir / "merged_gw.csv"
    if not gw_file.exists():
        print(f"ERROR: {gw_file} mangler")
        return False
    fixtures_file = season_dir / "fixtures.csv"
    fixtures = pd.read_csv(fixtures_file) if fixtures_file.exists() else None
    gw = pd.read_csv(gw_file)
    result = build_feature_frame(gw, fixtures)
    output_file = season_dir / "features.csv"
    result.to_csv(output_file, index=False, lineterminator="\n")
    print(f"{season}: {len(result)} rows -> {output_file}")
    return True


def main():
    success = True
    for season in sys.argv[1:] or SEASONS:
        if not build_features(season):
            success = False
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
