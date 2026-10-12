"""Player price changes, as the official FPL game publishes them.

FPL now publishes, per player, how far they are towards their next price
change (`price_change_percent`: +100 means a rise is due, -100 a fall), how
fast that is moving (`price_change_hourly_rate`) and its own projection for the
next price-change windows with a likelihood from -5 (very likely to fall) to
+5 (very likely to rise). The windows themselves are in
`game_config.settings.price_change_deadlines`. Nothing here is estimated by
Fantasy Football AI: it is the official figures, reshaped for the app.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

POSITIONS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def build_price_changes(bootstrap: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    config = bootstrap.get("game_config") if isinstance(bootstrap.get("game_config"), dict) else {}
    settings = config.get("settings") if isinstance(config.get("settings"), dict) else {}
    status = config.get("status") if isinstance(config.get("status"), dict) else {}
    deadlines = [parsed for parsed in (_parse_time(item) for item in settings.get("price_change_deadlines") or []) if parsed]
    upcoming = sorted(moment for moment in deadlines if moment > now)
    teams = {int(team["id"]): team for team in bootstrap.get("teams") or [] if isinstance(team, dict) and team.get("id") is not None}

    players = []
    for element in bootstrap.get("elements") or []:
        if not isinstance(element, dict) or element.get("removed"):
            continue
        percent = _number(element.get("price_change_percent"))
        projections = []
        for item in element.get("price_change_projections") or []:
            if not isinstance(item, dict):
                continue
            likelihood = _number(item.get("likelihood"))
            projections.append({
                "offset": int(item.get("offset") or 0),
                "percent": _number(item.get("projected_percent")),
                "likelihood": int(likelihood) if likelihood is not None else 0,
            })
        projections.sort(key=lambda item: item["offset"])
        if percent is None and not projections:
            continue
        team = teams.get(int(element.get("team") or 0), {})
        locked = _parse_time(element.get("price_change_locked_until"))
        players.append({
            "player_id": int(element["id"]),
            "name": str(element.get("web_name") or element.get("second_name") or element["id"]),
            "team": str(team.get("name", "")),
            "team_short": str(team.get("short_name", "")),
            "position": POSITIONS.get(int(element.get("element_type") or 0), ""),
            "price": round(float(element["now_cost"]) / 10, 1) if element.get("now_cost") is not None else None,
            "ownership": _number(element.get("selected_by_percent")),
            "percent": percent,
            "hourly_rate": _number(element.get("price_change_hourly_rate")),
            "projections": projections,
            # A player who has just changed price cannot change again until then.
            "locked_until": locked.isoformat() if locked and locked > now else None,
            "calibrating": bool(element.get("price_change_calibrating")),
            "cost_change_event": int(element.get("cost_change_event") or 0),
            "transfers_in_event": int(element.get("transfers_in_event") or 0),
            "transfers_out_event": int(element.get("transfers_out_event") or 0),
        })

    players.sort(key=lambda player: -abs(player["percent"] or 0))
    return {
        "next_change_at": upcoming[0].isoformat() if upcoming else None,
        "change_windows": [moment.isoformat() for moment in upcoming],
        "updated_at": status.get("price_change_last_updated"),
        "players": players,
    }


# How much a likely price change nudges a Wildcard, in weighted horizon points.
# Small on purpose: about a tenth of a typical transfer gain, so it only decides
# between near-equal squads and never trades real points for £0.1m.
RISE_BONUS = {4: 0.25, 5: 0.4}


def price_likelihoods(bootstrap: dict[str, Any]) -> dict[int, int]:
    """FPL's strongest likelihood over the next two change windows, per player
    (+5 very likely to rise … -5 very likely to fall). Locked players are 0."""
    result: dict[int, int] = {}
    for element in bootstrap.get("elements") or []:
        if not isinstance(element, dict) or element.get("id") is None or element.get("price_change_locked_until"):
            continue
        values = [int(_number(item.get("likelihood")) or 0) for item in element.get("price_change_projections") or []
                  if isinstance(item, dict) and int(item.get("offset") or 0) <= 1]
        if values:
            result[int(element["id"])] = max(values, key=abs)
    return result


def riser_bonus(likelihoods: dict[int, int]) -> dict[int, float]:
    """A selection nudge for likely risers and against likely fallers."""
    bonus = {}
    for player_id, likelihood in likelihoods.items():
        size = RISE_BONUS.get(abs(likelihood), 0.0)
        if size:
            bonus[player_id] = size if likelihood > 0 else -size
    return bonus
