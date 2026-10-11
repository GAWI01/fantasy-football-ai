from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .availability import gameweek_multipliers


_PREDICTION_COLUMNS = {
    "player_id", "name", "position", "team", "price", "predicted_points",
}
_FIXTURE_COLUMNS = {
    "event", "team_h", "team_a", "team_h_difficulty", "team_a_difficulty",
}
_TEAM_COLUMNS = {"id", "name"}


def _require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise ValueError(f"{label} must be a pandas DataFrame")
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{label} missing columns: {', '.join(sorted(missing))}")


def _fixture_factor(difficulty: float, home: bool) -> float:
    difficulty = max(1.0, min(5.0, float(difficulty)))
    return max(0.65, 1.0 + (3.0 - difficulty) * 0.08 + (0.03 if home else -0.03))


def _base_factor(row: pd.Series) -> float:
    difficulty = row.get("difficulty", 3.0)
    if pd.isna(difficulty):
        difficulty = 3.0
    home = row.get("home", False)
    return _fixture_factor(float(difficulty), bool(home) if not pd.isna(home) else False)


def _uncertainty(points: float, step: int) -> float:
    # A transparent heuristic band, not a calibrated probability interval.
    return round(max(0.8, abs(points) * (0.18 + 0.07 * (step - 1))), 3)


def gameweek_flags(fixtures: pd.DataFrame, teams: pd.DataFrame, event: int) -> dict[str, bool]:
    _require_columns(fixtures, _FIXTURE_COLUMNS, "fixtures")
    _require_columns(teams, _TEAM_COLUMNS, "teams")
    event_fixtures = fixtures[pd.to_numeric(fixtures["event"], errors="coerce") == int(event)]
    counts = {int(team_id): 0 for team_id in teams["id"]}
    for _, fixture in event_fixtures.iterrows():
        counts[int(fixture["team_h"])] = counts.get(int(fixture["team_h"]), 0) + 1
        counts[int(fixture["team_a"])] = counts.get(int(fixture["team_a"]), 0) + 1
    return {
        "blank_gameweek": any(count == 0 for count in counts.values()),
        "double_gameweek": any(count > 1 for count in counts.values()),
    }


def _parse_kickoff(value) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else None


def _number(value, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return default if pd.isna(number) else number


def build_fixture_scaled_horizon(
    predictions: pd.DataFrame,
    fixtures: pd.DataFrame,
    teams: pd.DataFrame,
    *,
    prediction_event: int,
    horizon: int = 5,
) -> dict[int, pd.DataFrame]:
    """Per-Gameweek projections for the planning horizon.

    Step 1 is the served forecast unchanged (official availability applied).
    Later steps rescale the model's points *if available* (`ml_prediction`)
    to each later fixture's difficulty and venue, then apply that Gameweek's
    own availability (`backend.availability`). Availability for the target
    Gameweek is therefore never copied onto the whole horizon: a one-match
    ban, a short injury or a blank in the target Gameweek only affects the
    Gameweeks it actually covers.
    """
    _require_columns(predictions, _PREDICTION_COLUMNS, "predictions")
    _require_columns(fixtures, _FIXTURE_COLUMNS, "fixtures")
    _require_columns(teams, _TEAM_COLUMNS, "teams")
    if not isinstance(prediction_event, int) or not 1 <= prediction_event <= 38:
        raise ValueError("prediction_event must be between 1 and 38")
    if not isinstance(horizon, int) or not 1 <= horizon <= 5:
        raise ValueError("horizon must be between 1 and 5")
    horizon = min(horizon, 39 - prediction_event)

    team_ids = {
        str(row.name).casefold(): int(row.id)
        for row in teams.loc[:, ["id", "name"]].itertuples(index=False)
    }
    team_names = {
        int(row.id): str(row.name)
        for row in teams.loc[:, ["id", "name"]].itertuples(index=False)
    }
    base = predictions.copy()
    base["predicted_points"] = pd.to_numeric(base["predicted_points"], errors="raise").astype(float)
    if "opponent" not in base.columns:
        base["opponent"] = None
    base["gameweek"] = prediction_event
    base["projection_method"] = "native_model"
    base["uncertainty"] = base["predicted_points"].map(lambda value: _uncertainty(float(value), 1))

    events = [prediction_event + step for step in range(horizon)]
    has_kickoffs = "kickoff_time" in fixtures.columns
    columns = sorted(_FIXTURE_COLUMNS) + (["kickoff_time"] if has_kickoffs else [])
    # event -> team -> [(opponent, difficulty, home, kickoff)]
    matches_by_event: dict[int, dict[int, list[tuple[int, float, bool, datetime | None]]]] = {
        event: {} for event in events
    }
    for fixture in fixtures.loc[:, columns].itertuples(index=False):
        try:
            event = int(fixture.event)
            team_h = int(fixture.team_h)
            team_a = int(fixture.team_a)
            home_difficulty = float(fixture.team_h_difficulty)
            away_difficulty = float(fixture.team_a_difficulty)
        except (TypeError, ValueError):
            continue
        if event not in matches_by_event:
            continue
        kickoff = _parse_kickoff(fixture.kickoff_time) if has_kickoffs else None
        event_map = matches_by_event[event]
        event_map.setdefault(team_h, []).append((team_a, home_difficulty, True, kickoff))
        event_map.setdefault(team_a, []).append((team_h, away_difficulty, False, kickoff))

    base_matches = matches_by_event[prediction_event]
    base["fixture_count"] = base["team"].map(
        lambda team: len(base_matches.get(team_ids.get(str(team).casefold()), []))
    )
    target_kickoffs = [kickoff for team in base_matches.values() for *_, kickoff in team if kickoff]
    reference = min(target_kickoffs) if target_kickoffs else datetime.now(timezone.utc)
    result: dict[int, pd.DataFrame] = {1: base}
    base_records = base.to_dict("records")
    has_model_points = "ml_prediction" in base.columns

    plans = []
    for player in base_records:
        team_id = team_ids.get(str(player["team"]).casefold())
        if team_id is None:
            raise ValueError(f"Unknown player team: {player['team']}")
        target_matches = base_matches.get(team_id, [])
        kickoffs = []
        for event in events:
            matches = matches_by_event[event].get(team_id, [])
            kickoffs.append(min((m[3] for m in matches if m[3] is not None), default=None))
        status = player.get("status")
        news = player.get("news") if has_kickoffs else None
        multipliers = gameweek_multipliers(
            status if isinstance(status, str) else "a",
            player.get("chance_of_playing_next_round"),
            news if isinstance(news, str) else None,
            kickoffs,
            reference=reference,
        )
        # Points for one neutral fixture if the player is available.
        if has_model_points and _number(player.get("ml_prediction")) is not None:
            available_points = float(player["ml_prediction"])
        else:
            # Legacy artifacts store only availability-adjusted points.
            first = multipliers[0]
            available_points = float(player["predicted_points"]) / first if first > 0 else 0.0
        if target_matches:
            base_factor = sum(_fixture_factor(difficulty, home) for _, difficulty, home, _ in target_matches)
            per_fixture = available_points / base_factor
            method = "fixture_scaled_v2"
        elif _number(player.get("ml_per_fixture")) is not None:
            # Stored for an average-difficulty fixture, home and away averaged
            # (factor 1.0 by construction of `_fixture_factor`).
            per_fixture = float(player["ml_per_fixture"])
            method = "fixture_scaled_v2"
        else:
            # Blank in the target Gameweek and no per-fixture estimate stored.
            per_fixture = available_points / _base_factor(player)
            method = "fixture_scaled_v2" if available_points > 0 else "no_base_fixture"
        count = max(1, len(target_matches))
        xmins_available = _number(player.get("xmins_available"), _number(player.get("xmins"), 90.0))
        start_available = _number(player.get("start_probability_available"),
                                  _number(player.get("start_probability"), 1.0))
        plans.append((player, team_id, per_fixture, method, multipliers,
                      xmins_available / count if target_matches else xmins_available, start_available))

    for step in range(2, horizon + 1):
        event = prediction_event + step - 1
        matches_by_team = matches_by_event[event]
        rows = []
        for player, team_id, per_fixture, method, multipliers, minutes_per_fixture, start_available in plans:
            matches = matches_by_team.get(team_id, [])
            record = dict(player)
            record["gameweek"] = event
            multiplier = multipliers[step - 1]
            if not matches:
                record.update({
                    "predicted_points": 0.0,
                    "opponent": "Blank",
                    "home": None,
                    "difficulty": None,
                    "fixture_count": 0,
                    "xmins": 0.0,
                    "start_probability": 0.0,
                    "availability_multiplier": multiplier,
                    "projection_method": "blank_gameweek",
                    "uncertainty": 0.0,
                })
                rows.append(record)
                continue
            projected = sum(per_fixture * _fixture_factor(difficulty, home) for _, difficulty, home, _ in matches)
            points = round(projected * multiplier, 3)
            difficulties = [difficulty for _, difficulty, _, _ in matches]
            homes = [home for _, _, home, _ in matches]
            record.update({
                "predicted_points": points,
                "opponent": " / ".join(team_names.get(opponent, f"Team {opponent}") for opponent, *_ in matches),
                "home": homes[0] if len(homes) == 1 else None,
                "difficulty": round(sum(difficulties) / len(difficulties), 2),
                "fixture_count": len(matches),
                "xmins": round(min(90.0 * len(matches), minutes_per_fixture * len(matches)) * multiplier, 1),
                "start_probability": round(min(1.0, start_available) * multiplier, 3),
                "availability_multiplier": multiplier,
                "projection_method": method,
                "uncertainty": _uncertainty(points, step),
            })
            rows.append(record)
        frame_columns = list(dict.fromkeys([*base.columns, "availability_multiplier"]))
        result[step] = pd.DataFrame(rows, columns=frame_columns)

    return result
