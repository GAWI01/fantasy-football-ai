from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from .fpl_gateway import FplGatewayError, default_gateway


FPL_API = "https://fantasy.premierleague.com/api"


class FixtureServiceError(RuntimeError):
    """Raised when FPL fixture data cannot be loaded or normalized."""


def _get_json(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{FPL_API}/{path.lstrip('/')}"
    if params:
        url = f"{url}?{urlencode(params)}"
    ttl_seconds = 300 if path.lstrip("/") == "bootstrap-static/" else 900
    if path.lstrip("/").startswith("entry/"):
        ttl_seconds = 60
    try:
        return default_gateway.get_json(url, ttl_seconds).data
    except FplGatewayError as exc:
        raise FixtureServiceError(str(exc)) from exc


def _gameweek_status(bootstrap: dict[str, Any]) -> tuple[int | None, int | None]:
    events = bootstrap.get("events") or []

    current = next(
        (int(event["id"]) for event in events if event.get("is_current")),
        None,
    )
    next_event = next(
        (int(event["id"]) for event in events if event.get("is_next")),
        None,
    )

    if current is None:
        finished = [
            int(event["id"])
            for event in events
            if event.get("finished")
        ]
        current = max(finished) if finished else None

    if next_event is None and current is not None:
        next_candidates = [
            int(event["id"])
            for event in events
            if int(event["id"]) > current and not event.get("finished")
        ]
        next_event = min(next_candidates) if next_candidates else None

    return current, next_event


def _parse_kickoff(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_fixtures(
    fixtures: list[dict[str, Any]],
    team_map: dict[int, dict[str, Any]],
    selected_team_ids: set[int],
) -> list[dict[str, Any]]:
    """Normalize fixtures for the clubs represented in the manager squad."""

    normalized: list[dict[str, Any]] = []

    for fixture in fixtures:
        event = fixture.get("event")
        home_id = fixture.get("team_h")
        away_id = fixture.get("team_a")

        if event is None or home_id is None or away_id is None:
            continue

        home_id = int(home_id)
        away_id = int(away_id)
        involved = selected_team_ids.intersection({home_id, away_id})

        for team_id in involved:
            is_home = team_id == home_id
            opponent_id = away_id if is_home else home_id
            team = team_map.get(team_id, {})
            opponent = team_map.get(opponent_id, {})
            difficulty_key = (
                "team_h_difficulty" if is_home else "team_a_difficulty"
            )

            normalized.append(
                {
                    "fixture_id": fixture.get("id"),
                    "event": int(event),
                    "team_id": team_id,
                    "team": team.get("name", "Unknown"),
                    "team_short": team.get("short_name", "UNK"),
                    "opponent_id": opponent_id,
                    "opponent": opponent.get("name", "Unknown"),
                    "opponent_short": opponent.get("short_name", "UNK"),
                    "home": is_home,
                    "difficulty": fixture.get(difficulty_key),
                    "kickoff_time": fixture.get("kickoff_time"),
                    "started": bool(fixture.get("started")),
                    "finished": bool(fixture.get("finished")),
                    "finished_provisional": bool(
                        fixture.get("finished_provisional")
                    ),
                }
            )

    normalized.sort(
        key=lambda item: (
            item["kickoff_time"] is None,
            item["kickoff_time"] or "",
        )
    )
    return normalized


def _get_current_picks(
    manager_id: int,
    bootstrap: dict[str, Any],
    current_event: int,
) -> list[dict[str, Any]]:
    picks_data = _get_json(f"entry/{manager_id}/event/{current_event}/picks/")
    picks = picks_data.get("picks") or []

    players_by_id = {
        int(player["id"]): player
        for player in (bootstrap.get("elements") or [])
    }

    result = []
    for pick in picks:
        player_id = int(pick["element"])
        player = players_by_id.get(player_id)
        if not player:
            continue

        result.append(
            {
                "player_id": player_id,
                "name": player.get("web_name") or player.get("second_name") or f"Player {player_id}",
                "team_id": int(player["team"]),
                "position": int(player["element_type"]),
                "position_name": {
                    1: "GKP",
                    2: "DEF",
                    3: "MID",
                    4: "FWD",
                }.get(int(player["element_type"]), "UNK"),
                "is_captain": bool(pick.get("is_captain")),
                "is_vice_captain": bool(pick.get("is_vice_captain")),
                "multiplier": int(pick.get("multiplier", 1)),
            }
        )

    return result


def _future_fixtures_for_team_ids(
    raw_fixtures: list[dict[str, Any]],
    team_ids: set[int],
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    result = []

    for fixture in raw_fixtures:
        home_id = fixture.get("team_h")
        away_id = fixture.get("team_a")
        if home_id is None or away_id is None:
            continue

        home_id = int(home_id)
        away_id = int(away_id)

        if not team_ids.intersection({home_id, away_id}):
            continue
        if fixture.get("finished"):
            continue

        kickoff = _parse_kickoff(fixture.get("kickoff_time"))
        if kickoff and kickoff < now and fixture.get("started"):
            # A genuinely live fixture remains relevant; an old unfinished
            # record should not be surfaced as a future fixture.
            continue

        result.append(fixture)

    return result


def _unique_fixtures(fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique = []
    seen: set[tuple[Any, int]] = set()

    for fixture in fixtures:
        key = (fixture.get("fixture_id"), int(fixture["team_id"]))
        if key in seen:
            continue
        seen.add(key)
        unique.append(fixture)

    return unique


def get_team_fixtures(team_id: int, limit: int = 5) -> dict[str, Any]:
    """
    Return the next fixtures involving clubs represented in an FPL manager's
    current squad. team_id is the FPL manager/entry ID.
    """
    if limit < 1:
        raise ValueError("limit must be >= 1")

    bootstrap = _get_json("bootstrap-static/")
    current_event, next_event = _gameweek_status(bootstrap)

    if current_event is None:
        raise FixtureServiceError("Could not determine the current gameweek.")

    team_map = {
        int(team["id"]): team
        for team in (bootstrap.get("teams") or [])
    }

    picks = _get_current_picks(team_id, bootstrap, current_event)
    selected_team_ids = {pick["team_id"] for pick in picks}

    if not selected_team_ids:
        return {
            "team_id": team_id,
            "current_event": current_event,
            "next_event": next_event,
            "fixtures": [],
        }

    raw_fixtures = _get_json("fixtures/")
    future = _future_fixtures_for_team_ids(raw_fixtures, selected_team_ids)

    # The dashboard means "next fixtures", not unfinished fixtures from the
    # current gameweek. Prefer the FPL API's next gameweek and only fall back
    # to the current event when no next event is available.
    target_event = next_event if next_event is not None else current_event
    future = [
        fixture
        for fixture in future
        if int(fixture.get("event") or 0) == target_event
    ]

    normalized = normalize_fixtures(future, team_map, selected_team_ids)
    normalized = _unique_fixtures(normalized)

    return {
        "team_id": team_id,
        "current_event": current_event,
        "next_event": next_event,
        "fixtures": normalized[:limit],
    }


def get_team_player_fixtures(
    team_id: int,
    limit: int = 5,
) -> dict[str, Any]:
    """
    Return each player's next fixtures.

    This is deliberately separate from get_team_fixtures so the dashboard can
    use one compact team-fixture list while AI/player analysis can use the
    richer per-player fixture context.
    """
    if limit < 1:
        raise ValueError("limit must be >= 1")

    bootstrap = _get_json("bootstrap-static/")
    current_event, next_event = _gameweek_status(bootstrap)

    if current_event is None:
        raise FixtureServiceError("Could not determine the current gameweek.")

    team_map = {
        int(team["id"]): team
        for team in (bootstrap.get("teams") or [])
    }
    picks = _get_current_picks(team_id, bootstrap, current_event)

    if not picks:
        return {
            "team_id": team_id,
            "current_event": current_event,
            "next_event": next_event,
            "players": [],
        }

    selected_team_ids = {pick["team_id"] for pick in picks}
    raw_fixtures = _get_json("fixtures/")
    future = _future_fixtures_for_team_ids(raw_fixtures, selected_team_ids)
    all_fixtures = normalize_fixtures(
        future,
        team_map,
        selected_team_ids,
    )
    all_fixtures = _unique_fixtures(all_fixtures)

    fixtures_by_team: dict[int, list[dict[str, Any]]] = {}
    for fixture in all_fixtures:
        fixtures_by_team.setdefault(int(fixture["team_id"]), []).append(fixture)

    players = []
    for pick in picks:
        players.append(
            {
                **pick,
                "team": team_map.get(pick["team_id"], {}).get(
                    "name",
                    "Unknown",
                ),
                "team_short": team_map.get(pick["team_id"], {}).get(
                    "short_name",
                    "UNK",
                ),
                "fixtures": fixtures_by_team.get(pick["team_id"], [])[:limit],
            }
        )

    return {
        "team_id": team_id,
        "current_event": current_event,
        "next_event": next_event,
        "players": players,
    }


def get_upcoming_team_fixtures(team_id: int, limit: int = 10) -> dict[str, Any]:
    """
    Return upcoming fixtures involving any club in the manager's squad.

    Unlike get_team_fixtures(), this endpoint intentionally spans multiple
    gameweeks and represents each match once as home_team vs away_team.
    """
    if not isinstance(team_id, int) or team_id <= 0:
        raise ValueError("team_id must be a positive integer")
    if limit < 1 or limit > 50:
        raise ValueError("limit must be between 1 and 50")

    bootstrap = _get_json("bootstrap-static/")
    current_event, next_event = _gameweek_status(bootstrap)
    if current_event is None:
        raise FixtureServiceError("Could not determine the current gameweek.")

    team_map = {
        int(team["id"]): team for team in (bootstrap.get("teams") or [])
    }
    picks = _get_current_picks(team_id, bootstrap, current_event)
    selected_team_ids = {int(pick["team_id"]) for pick in picks}
    raw = _get_json("fixtures/")

    now = datetime.now(timezone.utc)
    rows = []
    seen = set()
    for fixture in raw:
        fixture_id = fixture.get("id")
        home_id = fixture.get("team_h")
        away_id = fixture.get("team_a")
        if fixture_id is None or home_id is None or away_id is None:
            continue
        home_id, away_id = int(home_id), int(away_id)
        if not selected_team_ids.intersection({home_id, away_id}):
            continue
        if fixture.get("finished"):
            continue
        kickoff = _parse_kickoff(fixture.get("kickoff_time"))
        if kickoff and kickoff < now and fixture.get("started"):
            continue
        if fixture_id in seen:
            continue
        seen.add(fixture_id)
        home = team_map.get(home_id, {})
        away = team_map.get(away_id, {})
        rows.append({
            "fixture_id": int(fixture_id),
            "event": int(fixture.get("event") or 0),
            "kickoff_time": fixture.get("kickoff_time"),
            "home_team_id": home_id,
            "home_team": home.get("name", "Unknown"),
            "home_short": home.get("short_name", "UNK"),
            "away_team_id": away_id,
            "away_team": away.get("name", "Unknown"),
            "away_short": away.get("short_name", "UNK"),
            "difficulty": (
                fixture.get("team_h_difficulty")
                if home_id in selected_team_ids
                else fixture.get("team_a_difficulty")
            ),
            "home_difficulty": fixture.get("team_h_difficulty"),
            "away_difficulty": fixture.get("team_a_difficulty"),
            "selected_team_ids": sorted(selected_team_ids.intersection({home_id, away_id})),
        })
    rows.sort(key=lambda x: (x["kickoff_time"] is None, x["kickoff_time"] or "", x["fixture_id"]))
    return {
        "team_id": team_id,
        "current_event": current_event,
        "next_event": next_event,
        "fixtures": rows[:limit],
    }


def build_fixture_matrix(
    bootstrap: dict[str, Any],
    raw_fixtures: list[dict[str, Any]],
    *,
    start_event: int,
    horizon: int = 5,
) -> dict[str, Any]:
    if not isinstance(start_event, int) or not 1 <= start_event <= 38:
        raise ValueError("start_event must be between 1 and 38")
    if not isinstance(horizon, int) or not 1 <= horizon <= 8:
        raise ValueError("horizon must be between 1 and 8")
    teams = bootstrap.get("teams") if isinstance(bootstrap, dict) else None
    if not isinstance(teams, list):
        raise FixtureServiceError("FPL bootstrap teams are invalid")
    if not isinstance(raw_fixtures, list):
        raise FixtureServiceError("FPL fixtures response is invalid")

    team_map = {
        int(team["id"]): team
        for team in teams
        if isinstance(team, dict) and team.get("id") is not None
    }
    gameweeks = list(range(start_event, min(38, start_event + horizon - 1) + 1))
    fixtures_by_event: dict[int, list[dict[str, Any]]] = {event: [] for event in gameweeks}
    for fixture in raw_fixtures:
        if not isinstance(fixture, dict) or fixture.get("event") is None:
            continue
        event = int(fixture["event"])
        if event in fixtures_by_event and not fixture.get("finished"):
            fixtures_by_event[event].append(fixture)

    rows = []
    for team_id, team in sorted(
        team_map.items(), key=lambda item: str(item[1].get("name", ""))
    ):
        cells = []
        for event in gameweeks:
            opponents: list[str] = []
            difficulties: list[float] = []
            for fixture in fixtures_by_event[event]:
                home_id = int(fixture.get("team_h", 0) or 0)
                away_id = int(fixture.get("team_a", 0) or 0)
                if team_id == home_id:
                    opponent = team_map.get(away_id, {})
                    opponents.append(f"{opponent.get('short_name', 'UNK')} (H)")
                    if fixture.get("team_h_difficulty") is not None:
                        difficulties.append(float(fixture["team_h_difficulty"]))
                elif team_id == away_id:
                    opponent = team_map.get(home_id, {})
                    opponents.append(f"{opponent.get('short_name', 'UNK')} (A)")
                    if fixture.get("team_a_difficulty") is not None:
                        difficulties.append(float(fixture["team_a_difficulty"]))
            cells.append(
                {
                    "event": event,
                    "opponents": opponents,
                    "difficulty": (
                        round(sum(difficulties) / len(difficulties), 1)
                        if difficulties
                        else None
                    ),
                    "fixture_count": len(opponents),
                }
            )
        rows.append(
            {
                "team_id": team_id,
                "team": str(team.get("name", "Unknown")),
                "team_short": str(team.get("short_name", "UNK")),
                "fixtures": cells,
            }
        )

    current_event, next_event = _gameweek_status(bootstrap)
    return {
        "current_event": current_event,
        "next_event": next_event,
        "start_event": start_event,
        "horizon": len(gameweeks),
        "gameweeks": gameweeks,
        "teams": rows,
    }


def get_fixture_matrix(
    start_event: int | None = None,
    horizon: int = 5,
) -> dict[str, Any]:
    bootstrap = _get_json("bootstrap-static/")
    if not isinstance(bootstrap, dict):
        raise FixtureServiceError("FPL bootstrap response is invalid")
    current_event, next_event = _gameweek_status(bootstrap)
    selected_start = start_event if start_event is not None else next_event or current_event
    if selected_start is None:
        raise FixtureServiceError("Could not determine the next gameweek")
    raw_fixtures = _get_json("fixtures/")
    return build_fixture_matrix(
        bootstrap,
        raw_fixtures,
        start_event=selected_start,
        horizon=horizon,
    )
