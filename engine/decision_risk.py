from __future__ import annotations
from typing import Any
import math

def _num(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default

def player_risk(row: dict[str, Any]) -> dict[str, Any]:
    xmins = max(0.0, min(90.0, _num(row.get("xmins", row.get("minutes", 0.0)))))
    start_probability = max(0.0, min(1.0, _num(row.get("start_probability", xmins / 90.0 if xmins else 0.0))))
    availability = str(row.get("availability", "AVAILABLE")).upper()
    rotation = str(row.get("rotation_risk", "")).upper()
    availability_penalty = {
        "AVAILABLE": 0.0, "NEWS": 0.10, "MINOR_RISK": 0.20,
        "RISK": 0.40, "MAJOR_RISK": 0.65, "UNAVAILABLE": 1.0,
    }.get(availability, 0.15)
    rotation_penalty = {
        "LOW": 0.0, "MEDIUM": 0.10, "HIGH": 0.25,
        "VERY_HIGH": 0.40, "OUT": 1.0,
    }.get(rotation, 0.0)
    score = max(0.0, min(1.0,
        0.45 * (1.0 - start_probability)
        + 0.35 * availability_penalty
        + 0.20 * rotation_penalty
    ))
    label = "LOW" if score < .20 else "MEDIUM" if score < .45 else "HIGH" if score < .75 else "VERY_HIGH"
    return {
        "score": round(score, 3),
        "label": label,
        "xmins": round(xmins, 1),
        "start_probability": round(start_probability, 3),
        "availability": availability,
        "rotation_risk": rotation,
    }

def squad_health(players: list[dict[str, Any]]) -> dict[str, Any]:
    risks = []
    for player in players:
        risks.append({
            "player_id": int(player["player_id"]),
            "name": player.get("name"),
            **player_risk(player),
        })
    unavailable = [r for r in risks if r["availability"] == "UNAVAILABLE"]
    high_risk = [r for r in risks if r["label"] in {"HIGH", "VERY_HIGH"} and r["availability"] != "UNAVAILABLE"]
    avg_xmins = sum(r["xmins"] for r in risks) / len(risks) if risks else 0.0
    status = (
        "CRITICAL" if len(unavailable) >= 3
        else "WARNING" if unavailable or len(high_risk) >= 4
        else "HEALTHY"
    )
    return {
        "players": risks,
        "unavailable_count": len(unavailable),
        "high_risk_count": len(high_risk),
        "average_xmins": round(avg_xmins, 1),
        "status": status,
    }


def risk_adjusted_points(row: dict[str, Any], predicted_points: float | None = None) -> dict[str, Any]:
    """Return raw points plus an explicit risk-adjusted decision score."""
    raw = _num(predicted_points if predicted_points is not None else row.get("predicted_points", 0.0))
    risk = player_risk(row)
    adjusted = max(0.0, raw * (1.0 - 0.35 * risk["score"]))
    return {
        "predicted_points": round(raw, 3),
        "risk_score": risk["score"],
        "risk_adjusted_points": round(adjusted, 3),
    }
