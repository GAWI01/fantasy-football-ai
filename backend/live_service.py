
from __future__ import annotations

from typing import Any

from .fpl_gateway import FplGatewayError, default_gateway

FPL_API = "https://fantasy.premierleague.com/api"


class LiveDataServiceError(RuntimeError):
    """Raised when live FPL data cannot be loaded or normalized."""


def normalize_manager_chip_state(
    current_event: int,
    payload: dict[str, Any],
    *,
    started_event: int | None = None,
) -> dict[str, Any]:
    if not isinstance(current_event, int) or not 1 <= current_event <= 38:
        raise ValueError("current_event must be between 1 and 38")
    period = 1 if current_event <= 19 else 2
    start, end = (1, 19) if period == 1 else (20, 38)
    availability_keys = {
        "wildcard": "wildcard_available",
        "freehit": "free_hit_available",
        "bboost": "bench_boost_available",
        "3xc": "triple_captain_available",
    }
    display_names = {
        "wildcard": "WILDCARD",
        "freehit": "FREE_HIT",
        "bboost": "BENCH_BOOST",
        "3xc": "TRIPLE_CAPTAIN",
    }
    chips = payload.get("chips") if isinstance(payload, dict) else None
    if not isinstance(chips, list):
        return {
            "known": False,
            "period": period,
            "period_events": [start, end],
            "used_in_period": [],
            **{key: False for key in availability_keys.values()},
        }

    used = []
    used_names = set()
    previous_free_hit = False
    active_chip = False
    for chip in chips:
        if not isinstance(chip, dict):
            continue
        name = str(chip.get("name", "")).lower()
        try:
            event = int(chip.get("event"))
        except (TypeError, ValueError):
            continue
        if name == "freehit" and event == current_event - 1:
            previous_free_hit = True
        if name in availability_keys and event == current_event:
            active_chip = True
        if name in availability_keys and start <= event <= end:
            used_names.add(name)
            used.append({"chip": display_names[name], "event": event})
    used.sort(key=lambda item: (item["event"], item["chip"]))
    opening_event = started_event if started_event is not None else payload.get("started_event", 1)
    opening_gameweek = current_event == opening_event
    available = {key: name not in used_names for name, key in availability_keys.items()}
    if opening_gameweek:
        available["wildcard_available"] = False
        available["free_hit_available"] = False
    if previous_free_hit:
        available["free_hit_available"] = False
    if active_chip:
        available = {key: False for key in available}
    return {
        "known": True,
        "period": period,
        "period_events": [start, end],
        "used_in_period": used,
        **available,
    }


def get_manager_chip_state(
    team_id: int, current_event: int, *, started_event: int | None = None,
) -> dict[str, Any]:
    if not isinstance(team_id, int) or team_id <= 0:
        raise ValueError("team_id must be a positive integer")
    return normalize_manager_chip_state(
        current_event,
        _get_json(f"entry/{team_id}/history/"),
        started_event=started_event,
    )


def _get_json(path: str) -> Any:
    ttl_seconds = 300 if path.lstrip("/") == "bootstrap-static/" else 60
    if path.lstrip("/").startswith("event/"):
        ttl_seconds = 45
    try:
        return default_gateway.get_json(path, ttl_seconds).data
    except FplGatewayError as exc:
        raise LiveDataServiceError(str(exc)) from exc


def _current_event(bootstrap: dict[str, Any]) -> dict[str, Any]:
    events = bootstrap.get("events") or []
    if not isinstance(events, list):
        raise LiveDataServiceError("FPL bootstrap events are invalid")
    current = next((e for e in events if e.get("is_current")), None)
    if current is None:
        current = max(
            (e for e in events if e.get("finished")),
            key=lambda e: int(e.get("id", 0)),
            default=None,
        )
    if not isinstance(current, dict) or not current.get("id"):
        raise LiveDataServiceError("Could not determine current gameweek")
    return current


def latest_finished_event(bootstrap: dict[str, Any]) -> dict[str, Any]:
    events = bootstrap.get("events") if isinstance(bootstrap, dict) else None
    if not isinstance(events, list):
        raise LiveDataServiceError("FPL bootstrap events are invalid")
    finished = [
        event
        for event in events
        if isinstance(event, dict) and event.get("finished") and event.get("id")
    ]
    if not finished:
        raise LiveDataServiceError("Could not determine the latest finished gameweek")
    return max(finished, key=lambda event: int(event["id"]))


def _validate_team_id(team_id: int) -> None:
    if not isinstance(team_id, int) or team_id <= 0:
        raise ValueError("team_id must be a positive integer")


def _validate_event(event: int) -> None:
    if not isinstance(event, int) or not 1 <= event <= 38:
        raise ValueError("event must be between 1 and 38")


def get_bootstrap_data() -> dict[str, Any]:
    payload = _get_json("bootstrap-static/")
    if not isinstance(payload, dict):
        raise LiveDataServiceError("FPL bootstrap response is invalid")
    return payload


def get_event_picks(team_id: int, event: int) -> dict[str, Any]:
    _validate_team_id(team_id)
    _validate_event(event)
    payload = _get_json(f"entry/{team_id}/event/{event}/picks/")
    if not isinstance(payload, dict) or not isinstance(payload.get("picks"), list):
        raise LiveDataServiceError("FPL manager picks response is invalid")
    return payload


def get_manager_transfers(team_id: int) -> list[dict[str, Any]]:
    _validate_team_id(team_id)
    payload = _get_json(f"entry/{team_id}/transfers/")
    if not isinstance(payload, list):
        raise LiveDataServiceError("FPL manager transfers response is invalid")
    return [item for item in payload if isinstance(item, dict)]


def derive_free_transfers(
    *,
    target_event: int,
    started_event: int,
    transfers: list[dict[str, Any]],
    chips: list[dict[str, Any]],
) -> dict[str, Any]:
    """Derive remaining public-team free transfers under current FPL rules."""
    _validate_event(target_event)
    _validate_event(started_event)
    if target_event < started_event:
        return {"free_transfers": 0, "known": False}
    if target_event == started_event:
        # The public rules allow unlimited moves before a manager's first
        # deadline, while the per-Gameweek technical transfer cap is 20.
        return {"free_transfers": 20, "known": True}
    if not isinstance(transfers, list) or not isinstance(chips, list):
        return {"free_transfers": 0, "known": False}

    transfer_counts: dict[int, int] = {}
    for item in transfers:
        if not isinstance(item, dict):
            continue
        try:
            event = int(item.get("event"))
        except (TypeError, ValueError):
            continue
        transfer_counts[event] = transfer_counts.get(event, 0) + 1

    unlimited_events: set[int] = set()
    for item in chips:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").lower()
        if name not in {"wildcard", "freehit"}:
            continue
        try:
            unlimited_events.add(int(item.get("event")))
        except (TypeError, ValueError):
            continue

    remaining = 0
    for event in range(started_event + 1, target_event + 1):
        banked_before_week = remaining
        remaining = min(5, remaining + 1)
        if event in unlimited_events:
            # Wildcard/Free Hit uses the newly awarded weekly transfer while
            # preserving transfers banked before this Gameweek.
            remaining = banked_before_week
        else:
            remaining = max(0, remaining - transfer_counts.get(event, 0))
    return {"free_transfers": remaining, "known": True}


def get_manager_transfer_state(
    team_id: int,
    target_event: int,
    started_event: int,
) -> dict[str, Any]:
    _validate_team_id(team_id)
    history = _get_json(f"entry/{team_id}/history/")
    if not isinstance(history, dict):
        raise LiveDataServiceError("FPL manager history response is invalid")
    transfers = get_manager_transfers(team_id)
    chips = history.get("chips")
    if not isinstance(chips, list):
        chips = []
    return derive_free_transfers(
        target_event=target_event,
        started_event=started_event,
        transfers=transfers,
        chips=chips,
    )


def get_event_live(event: int) -> dict[str, Any]:
    _validate_event(event)
    payload = _get_json(f"event/{event}/live/")
    if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
        raise LiveDataServiceError("FPL event live response is invalid")
    return payload


def get_event_fixtures(event: int) -> dict[str, Any]:
    """Return the official score/state feed for one Gameweek."""
    _validate_event(event)
    bootstrap = _get_json("bootstrap-static/")
    fixtures = _get_json(f"fixtures/?event={event}")
    if not isinstance(bootstrap, dict) or not isinstance(fixtures, list):
        raise LiveDataServiceError("FPL event fixtures response is invalid")

    teams = _team_map(bootstrap)
    rows: list[dict[str, Any]] = []
    for fixture in fixtures:
        if not isinstance(fixture, dict) or fixture.get("id") is None:
            continue
        try:
            home_id = int(fixture["team_h"])
            away_id = int(fixture["team_a"])
        except (KeyError, TypeError, ValueError):
            continue
        home = teams.get(home_id, {})
        away = teams.get(away_id, {})
        rows.append({
            "fixture_id": int(fixture["id"]),
            "home_team_id": home_id,
            "away_team_id": away_id,
            "home_team": str(home.get("name") or "Unknown"),
            "home_team_short": str(home.get("short_name") or "UNK"),
            "away_team": str(away.get("name") or "Unknown"),
            "away_team_short": str(away.get("short_name") or "UNK"),
            "home_score": fixture.get("team_h_score"),
            "away_score": fixture.get("team_a_score"),
            "kickoff_time": fixture.get("kickoff_time"),
            "started": bool(fixture.get("started")),
            "finished": bool(fixture.get("finished")),
            "minutes": int(fixture.get("minutes", 0) or 0),
        })
    rows.sort(key=lambda item: (item.get("kickoff_time") or "", item["fixture_id"]))
    return {"event": event, "fixtures": rows}


def _status(event: dict[str, Any]) -> str:
    if event.get("finished"):
        return "FINISHED"
    return "LIVE"


def _team_map(bootstrap: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(t["id"]): t for t in (bootstrap.get("teams") or []) if t.get("id") is not None}


def _player_map(bootstrap: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(p["id"]): p for p in (bootstrap.get("elements") or []) if p.get("id") is not None}


def _position_name(element_type: int) -> str:
    return {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}.get(element_type, "UNK")


def normalize_live_players(
    bootstrap: dict[str, Any],
    live_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    teams = _team_map(bootstrap)
    players = _player_map(bootstrap)
    live_by_player = {
        int(item["id"]): item
        for item in (live_payload.get("elements") or [])
        if isinstance(item, dict) and item.get("id") is not None
    }
    rows: list[dict[str, Any]] = []

    # Bootstrap is the authoritative current transfer market. Players signed
    # after the Gameweek deadline may not yet exist in event/{gw}/live, but
    # they must still be discoverable with zero current-GW statistics.
    for player_id, player in players.items():
        item = live_by_player.get(player_id, {})
        stats = item.get("stats") or {}
        team = teams.get(int(player["team"]), {})
        rows.append({
            "player_id": player_id,
            "team_id": int(player["team"]),
            "name": player.get("web_name", player.get("first_name", "Unknown")),
            "team": team.get("name", "Unknown"),
            "team_short": team.get("short_name", "UNK"),
            "position": _position_name(int(player.get("element_type", 0))),
            "price": float(player["now_cost"]) / 10 if player.get("now_cost") is not None else None,
            "ownership": float(player["selected_by_percent"]) if player.get("selected_by_percent") is not None else None,
            "event_points": int(stats.get("total_points", 0) or 0),
            "minutes": int(stats.get("minutes", 0) or 0),
            "goals": int(stats.get("goals_scored", 0) or 0),
            "assists": int(stats.get("assists", 0) or 0),
            "bonus": int(stats.get("bonus", 0) or 0),
            "saves": int(stats.get("saves", 0) or 0),
            "penalties_saved": int(stats.get("penalties_saved", 0) or 0),
            "penalties_missed": int(stats.get("penalties_missed", 0) or 0),
            "yellow_cards": int(stats.get("yellow_cards", 0) or 0),
            "red_cards": int(stats.get("red_cards", 0) or 0),
            "own_goals": int(stats.get("own_goals", 0) or 0),
            "bps": int(stats.get("bps", 0) or 0),
            "clean_sheets": int(stats.get("clean_sheets", 0) or 0),
            "form": float(player["form"]) if player.get("form") is not None else None,
            "ep_this": float(player["ep_this"]) if player.get("ep_this") is not None else None,
            "expected_goals": float(player["expected_goals"]) if player.get("expected_goals") not in (None, "") else None,
            "expected_assists": float(player["expected_assists"]) if player.get("expected_assists") not in (None, "") else None,
            "expected_goal_involvements": float(player["expected_goal_involvements"]) if player.get("expected_goal_involvements") not in (None, "") else None,
            "influence": float(player["influence"]) if player.get("influence") not in (None, "") else None,
            "creativity": float(player["creativity"]) if player.get("creativity") not in (None, "") else None,
            "threat": float(player["threat"]) if player.get("threat") not in (None, "") else None,
            "ict_index": float(player["ict_index"]) if player.get("ict_index") not in (None, "") else None,
            "status": str(player.get("status") or "u"),
            "chance_of_playing_next_round": player.get("chance_of_playing_next_round"),
            "news": str(player.get("news") or ""),
            "news_added": player.get("news_added"),
        })
    rows.sort(key=lambda x: (-x["event_points"], -x["minutes"], x["player_id"]))
    return rows


def get_live_players(limit: int = 20, position: str | None = None) -> dict[str, Any]:
    if limit < 1 or limit > 700:
        raise ValueError("limit must be between 1 and 700")
    bootstrap = _get_json("bootstrap-static/")
    if not isinstance(bootstrap, dict):
        raise LiveDataServiceError("FPL bootstrap response is invalid")
    event = _current_event(bootstrap)
    event_id = int(event["id"])
    events = bootstrap.get("events") or []
    next_event = next(
        (item for item in events if isinstance(item, dict) and item.get("is_next")),
        None,
    )
    if next_event is None:
        next_event = min(
            (
                item
                for item in events
                if isinstance(item, dict)
                and int(item.get("id", 0) or 0) > event_id
                and not item.get("finished")
            ),
            key=lambda item: int(item["id"]),
            default=None,
        )
    live = _get_json(f"event/{event_id}/live/")
    players = normalize_live_players(bootstrap, live)
    if position:
        players = [p for p in players if p["position"].upper() == position.upper()]
    return {
        "current_event": event_id,
        "gameweek_name": event.get("name", f"Gameweek {event_id}"),
        "status": _status(event),
        "finished": bool(event.get("finished")),
        "next_event": int(next_event["id"]) if next_event else None,
        "next_deadline_time": next_event.get("deadline_time") if next_event else None,
        "players": players[:limit],
    }


def normalize_team_history(team_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    if team_id <= 0:
        raise ValueError("team_id must be positive")
    current = payload.get("current") or []
    if isinstance(current, dict):
        current = [current]
    if not isinstance(current, list):
        raise LiveDataServiceError("FPL team history current response is invalid")
    history = []
    for item in current:
        if not isinstance(item, dict) or item.get("event") is None:
            continue
        history.append({
            "event": int(item["event"]),
            "points": int(item.get("points", 0) or 0),
            "total_points": int(item.get("total_points", 0) or 0),
            "overall_rank": item.get("overall_rank"),
            "event_rank": item.get("rank"),
            "bank": item.get("bank"),
            "value": item.get("value"),
            "transfers": item.get("event_transfers"),
        })
    history.sort(key=lambda x: x["event"])
    deduped = {x["event"]: x for x in history}
    return {"team_id": team_id, "history": [deduped[k] for k in sorted(deduped)]}


def get_team_history(team_id: int) -> dict[str, Any]:
    if not isinstance(team_id, int) or team_id <= 0:
        raise ValueError("team_id must be a positive integer")
    return normalize_team_history(
        team_id,
        _get_json(f"entry/{team_id}/history/"),
    )
