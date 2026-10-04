"""Historical FPL feature engineering using the canonical feature contract."""

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

from feature_contract import FEATURE_COLUMNS, FEATURE_CONTRACT_VERSION, XP_SOURCE, build_feature_row


SEASONS = [
    "2020-21",
    "2021-22",
    "2022-23",
    "2023-24",
    "2024-25",
]

BASE = BASE_DIR / "historical_data"


def _rolling_previous(grouped, column, window=5, agg="sum"):
    shifted = grouped[column].shift(1)

    if agg == "sum":
        result = shifted.groupby(grouped.grouper).rolling(
            window, min_periods=1
        ).sum()
    elif agg == "mean":
        result = shifted.groupby(grouped.grouper).rolling(
            window, min_periods=1
        ).mean()
    else:
        raise ValueError(f"Unsupported rolling aggregation: {agg}")

    return result.reset_index(level=0, drop=True).sort_index().fillna(0.0)


def build_features(season):
    season_dir = BASE / season
    gw_file = season_dir / "merged_gw.csv"

    print()
    print("=" * 65)
    print(f"--- FEATURES {season} ---")
    print("=" * 65)

    if not gw_file.exists():
        print(f"ERROR: {gw_file} mangler")
        return False

    print("Leser Gameweek-data...")
    gw = pd.read_csv(gw_file)
    print(f"Gameweek-rader: {len(gw)}")

    if "element" in gw.columns:
        gw["player_id"] = gw["element"]
    elif "id" in gw.columns:
        gw["player_id"] = gw["id"]
    elif "player_id" not in gw.columns:
        print("ERROR: Fant ingen spiller-ID")
        print("Kolonner:", list(gw.columns))
        return False

    if "GW" not in gw.columns and "round" in gw.columns:
        gw["GW"] = gw["round"]

    required_base = [
        "player_id",
        "GW",
        "total_points",
        "minutes",
        "goals_scored",
        "assists",
        "bps",
        "influence",
        "creativity",
        "threat",
        "ict_index",
        "value",
    ]
    missing_base = [column for column in required_base if column not in gw.columns]
    if missing_base:
        print("ERROR: Mangler nødvendige kolonner:", ", ".join(missing_base))
        return False

    numeric_columns = [
        "minutes",
        "goals_scored",
        "assists",
        "clean_sheets",
        "goals_conceded",
        "own_goals",
        "penalties_saved",
        "penalties_missed",
        "yellow_cards",
        "red_cards",
        "saves",
        "bonus",
        "bps",
        "influence",
        "creativity",
        "threat",
        "ict_index",
        "total_points",
        "value",
        "xP",
        "was_home",
        "opponent_team",
    ]

    for column in numeric_columns:
        if column in gw.columns:
            gw[column] = pd.to_numeric(gw[column], errors="coerce").fillna(0.0)

    if "position" not in gw.columns:
        gw["position"] = "UNK"
    gw["position"] = gw["position"].astype(str).str.upper()

    gw = gw.sort_values(["player_id", "GW", "fixture"], kind="mergesort").reset_index(drop=True)

    print("Bygger leakage-safe rolling features på ferdige Gameweeks...")

    # The training rows are fixture-level rows: opponent_team/was_home describe
    # the fixture on that row and total_points is the outcome of that fixture.
    # A Double Gameweek therefore legitimately has multiple rows for one
    # player/GW. Rolling player history must be calculated from completed
    # Gameweek aggregates, never from one fixture inside the current GW.
    gw_level = (
        gw.groupby(["player_id", "GW"], as_index=False, sort=False)
        .agg(
            total_points=("total_points", "sum"),
            minutes=("minutes", "sum"),
            starts=("minutes", lambda x: (x >= 60).sum()),
            goals_scored=("goals_scored", "sum"),
            assists=("assists", "sum"),
            bps=("bps", "mean"),
            influence=("influence", "mean"),
            creativity=("creativity", "mean"),
            threat=("threat", "mean"),
            ict_index=("ict_index", "mean"),
        )
        .sort_values(["player_id", "GW"], kind="mergesort")
    )

    grouped = gw_level.groupby("player_id", sort=False)

    rolling = gw_level[["player_id", "GW"]].copy()
    rolling["history_cutoff_gw"] = grouped["GW"].shift(1).fillna(0).astype(int)
    rolling["points_last_3"] = (
        grouped["total_points"]
        .transform(lambda x: x.shift(1).rolling(3, min_periods=1).sum())
        .fillna(0.0)
    )
    rolling["points_last_5"] = (
        grouped["total_points"]
        .transform(lambda x: x.shift(1).rolling(5, min_periods=1).sum())
        .fillna(0.0)
    )
    rolling["points_avg_5"] = (
        grouped["total_points"]
        .transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
        .fillna(0.0)
    )
    rolling["minutes_last_5"] = (
        grouped["minutes"]
        .transform(lambda x: x.shift(1).rolling(5, min_periods=1).sum())
        .fillna(0.0)
    )
    rolling["starts_last_5"] = (
        grouped["starts"]
        .transform(lambda x: x.shift(1).rolling(5, min_periods=1).sum())
        .fillna(0.0)
    )
    rolling["goals_last_5"] = (
        grouped["goals_scored"]
        .transform(lambda x: x.shift(1).rolling(5, min_periods=1).sum())
        .fillna(0.0)
    )
    rolling["assists_last_5"] = (
        grouped["assists"]
        .transform(lambda x: x.shift(1).rolling(5, min_periods=1).sum())
        .fillna(0.0)
    )

    for column in ["bps", "influence", "creativity", "threat", "ict_index"]:
        rolling[f"{column}_avg_5"] = (
            grouped[column]
            .transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
            .fillna(0.0)
        )

    gw = gw.merge(
        rolling,
        on=["player_id", "GW"],
        how="left",
        validate="many_to_one",
    )

    gw["form_5"] = gw["points_avg_5"]
    # The archived same-GW FPL xP field has no verified pre-deadline timing.
    # Use the same causal recipe as live regeneration, rather than scraped xP
    # or cumulative-season xG/xA. This changes semantics and requires retraining.
    gw["xP"] = gw["points_avg_5"]
    gw["feature_contract_version"] = FEATURE_CONTRACT_VERSION
    gw["xp_source"] = XP_SOURCE
    gw["history_complete"] = True

    if "value" in gw.columns:
        gw["price"] = gw["value"] / 10.0
    else:
        gw["price"] = 0.0

    # Keep the canonical model columns available and validate one generated row.
    if "xP" not in gw.columns:
        gw["xP"] = 0.0
    if "was_home" not in gw.columns:
        gw["was_home"] = 0.0
    if "opponent_team" not in gw.columns:
        gw["opponent_team"] = 0.0

    gw = gw.replace([np.inf, -np.inf], np.nan)

    # Ensure every canonical numeric feature is numeric and finite.
    for column in FEATURE_COLUMNS:
        if column == "position":
            continue
        gw[column] = pd.to_numeric(gw[column], errors="coerce").fillna(0.0)

    # Validate the contract against the first available row.
    if not gw.empty:
        build_feature_row(gw.iloc[0].to_dict())

    output_file = season_dir / "features.csv"
    gw.to_csv(output_file, index=False)

    print()
    print(f"OK: Lagret: {output_file}")
    print(f"OK: Features: {len(gw.columns)}")
    print(f"OK: Rader: {len(gw)}")

    return True


def main():
    print("=" * 65)
    print("FPL AI - FEATURE ENGINEERING V1.1")
    print("=" * 65)

    success = True

    for season in SEASONS:
        if not build_features(season):
            success = False

    print()
    print("=" * 65)
    print("FEATURE ENGINEERING FERDIG" if success else "FEATURE ENGINEERING FULLFØRTE MED FEIL")
    print("=" * 65)

    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
