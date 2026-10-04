from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _numeric(value: Any, default: float = 0.0) -> float:
    value = pd.to_numeric(value, errors="coerce")
    return default if pd.isna(value) else float(value)


def _chance_multiplier(row: pd.Series) -> float:
    chance = row.get("chance_of_playing_next_round", np.nan)

    if pd.isna(chance):
        return 1.0

    chance = _numeric(chance, 100.0)

    if chance <= 0:
        return 0.0

    return float(np.clip(chance / 100.0, 0.0, 1.0))


def _availability_multiplier(row: pd.Series) -> float:
    status = str(row.get("status", "a")).strip().lower()

    if status in {"s", "u", "n"}:
        return 0.0
    if status == "i" and pd.isna(row.get("chance_of_playing_next_round", np.nan)):
        return 0.0

    return _chance_multiplier(row)


def availability_multiplier(row: pd.Series) -> float:
    return _availability_multiplier(row)


def _has_explicit_gw1_history(row: pd.Series) -> bool:
    history_columns = (
        "minutes_gw1",
        "started_gw1",
        "played_gw1",
    )

    return any(
        column in row.index and pd.notna(row[column])
        for column in history_columns
    )


def _gw1_minutes(row: pd.Series) -> float:
    if "minutes_gw1" not in row.index:
        return 0.0

    return max(
        0.0,
        min(90.0, _numeric(row.get("minutes_gw1"), 0.0)),
    )


def _gw1_started(row: pd.Series) -> float:
    if "started_gw1" not in row.index:
        return 0.0

    return float(
        np.clip(
            _numeric(row.get("started_gw1"), 0.0),
            0.0,
            1.0,
        )
    )


def _recent_minutes(row: pd.Series) -> float:
    for column in (
        "minutes_last_5",
        "minutes_last_3",
        "recent_minutes",
    ):
        if column in row.index and pd.notna(row[column]):
            value = max(0.0, _numeric(row[column]))

            if value > 0:
                return value

    return 0.0


def _recent_starts(row: pd.Series) -> float:
    for column in (
        "starts_last_5",
        "starts_last_3",
        "recent_starts",
    ):
        if column in row.index and pd.notna(row[column]):
            return max(0.0, _numeric(row[column]))

    return 0.0


def calculate_xmins(row: pd.Series) -> float:
    availability = _availability_multiplier(row)

    if availability <= 0:
        return 0.0

    recent_minutes = _recent_minutes(row)
    recent_starts = _recent_starts(row)
    history_count = _numeric(row.get("history_gw_count", 5), 5)
    window = max(1.0, min(5.0, history_count))

    if recent_starts > 0:
        recent_start_rate = np.clip(
            recent_starts / window,
            0.0,
            1.0,
        )

        if recent_minutes > 0:
            recent_avg = np.clip(
                recent_minutes / window,
                0.0,
                90.0,
            )

            base = (
                90.0 * recent_start_rate * 0.70
                + recent_avg * 0.30
            )
        else:
            base = 90.0 * recent_start_rate

        return round(
            float(np.clip(base * availability, 0.0, 90.0)),
            1,
        )

    if recent_minutes > 0:
        base = (
            np.clip(
                recent_minutes / window,
                0.0,
                90.0,
            )
            * 0.75
        )

        return round(
            float(np.clip(base * availability, 0.0, 90.0)),
            1,
        )

    if "history_gw_count" in row and history_count > 0:
        return 0.0

    if _has_explicit_gw1_history(row):
        gw1_minutes = _gw1_minutes(row)
        gw1_started = _gw1_started(row)

        if gw1_started >= 1.0:
            base = gw1_minutes
        elif gw1_minutes > 0:
            base = gw1_minutes * 0.75
        else:
            base = 0.0

        return round(
            float(np.clip(base * availability, 0.0, 90.0)),
            1,
        )

    season_minutes = max(
        0.0,
        _numeric(row.get("minutes", 0.0)),
    )

    if season_minutes > 0:
        base = np.clip(
            season_minutes,
            0.0,
            90.0,
        )
    else:
        base = 0.0

    return (
        round(
            float(np.clip(base * availability, 0.0, 90.0)),
            1,
        )
        if base > 0
        else 0.0
    )


def availability_label(row: pd.Series) -> str:
    status = str(row.get("status", "a")).strip().lower()
    chance = row.get(
        "chance_of_playing_next_round",
        np.nan,
    )
    news = str(row.get("news", "")).strip()

    if _availability_multiplier(row) <= 0:
        return "UNAVAILABLE"

    if pd.notna(chance):
        chance = _numeric(chance, 100.0)

        if chance <= 0:
            return "UNAVAILABLE"

        if chance <= 25:
            return "MAJOR_RISK"

        if chance <= 50:
            return "RISK"

        if chance <= 75:
            return "MINOR_RISK"

    if news.lower() not in {"", "nan", "none"}:
        return "NEWS"

    return "AVAILABLE"


def build_xmins_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    result["xmins"] = result.apply(
        calculate_xmins,
        axis=1,
    )

    result["availability"] = result.apply(
        availability_label,
        axis=1,
    )

    result["start_probability"] = (
        np.clip(
            result["xmins"] / 90.0,
            0.0,
            1.0,
        )
        .round(3)
    )

    result["rotation_risk"] = np.select(
        [
            result["xmins"] >= 75,
            result["xmins"] >= 60,
            result["xmins"] >= 45,
            result["xmins"] > 0,
        ],
        [
            "LOW",
            "MEDIUM",
            "HIGH",
            "VERY_HIGH",
        ],
        default="OUT",
    )

    result["availability_multiplier"] = result.apply(availability_multiplier, axis=1).round(3)

    return result


def main() -> None:
    base = Path(__file__).resolve().parents[2]

    players_file = (
        base
        / "historical_data"
        / "current_data"
        / "players_current.csv"
    )

    output_file = (
        base
        / "historical_data"
        / "current_data"
        / "players_features_current.csv"
    )

    print("=" * 70)
    print("FPL AI - PLAYER AVAILABILITY / XMINS V2.1")
    print("=" * 70)

    if not output_file.is_file():
        raise FileNotFoundError("Build canonical player features before updating xMins.")
    players_file = output_file
    print(f"\nLoading: {players_file}")

    df = pd.read_csv(players_file)

    print(f"Players loaded: {len(df)}")

    df = build_xmins_columns(df)

    df.to_csv(output_file, index=False)

    print("\nAVAILABILITY")
    print("-" * 70)
    print(df["availability"].value_counts().to_string())

    print("\nROTATION RISK")
    print("-" * 70)
    print(df["rotation_risk"].value_counts().to_string())

    print(f"\nSaved: {output_file}")


if __name__ == "__main__":
    main()
