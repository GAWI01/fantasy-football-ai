"""Realistic point ranges for an expected score.

The table (backend/data/point_ranges.json, built by scripts/build_point_ranges.py)
holds what players with a given expected score actually scored in an
out-of-sample backtest: quantiles and the chance of a haul (10+) or a blank (2 or
fewer). Between rows the values are interpolated; above the top row they scale
with the expected score.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

TABLE = Path(__file__).resolve().parent / "data" / "point_ranges.json"
KEYS = ("p10", "p25", "p50", "p75", "p90", "haul", "blank")


@lru_cache(maxsize=1)
def _rows() -> list[dict[str, float]]:
    return json.loads(TABLE.read_text())["rows"]


def point_range(expected: float | None) -> dict[str, Any] | None:
    """Quantiles of actual points for a player expected to score `expected`."""
    if expected is None:
        return None
    rows = _rows()
    value = max(0.0, float(expected))
    if value <= rows[0]["mean"]:
        row = dict(rows[0])
    elif value >= rows[-1]["mean"]:
        top = rows[-1]
        scale = value / top["mean"]
        row = {key: top[key] * scale for key in ("p10", "p25", "p50", "p75", "p90")}
        row["haul"], row["blank"] = top["haul"], top["blank"]
    else:
        upper = next(index for index, item in enumerate(rows) if item["mean"] >= value)
        low, high = rows[upper - 1], rows[upper]
        weight = (value - low["mean"]) / (high["mean"] - low["mean"])
        row = {key: low[key] + weight * (high[key] - low[key]) for key in KEYS}
    return {
        "low": round(row["p10"], 1),
        "high": round(row["p90"], 1),
        "median": round(row["p50"], 1),
        "haul_chance": round(row["haul"], 3),
        "blank_chance": round(row["blank"], 3),
    }
