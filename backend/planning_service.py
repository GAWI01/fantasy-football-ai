from __future__ import annotations

import pandas as pd


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


def build_fixture_scaled_horizon(
    predictions: pd.DataFrame,
    fixtures: pd.DataFrame,
    teams: pd.DataFrame,
    *,
    prediction_event: int,
    horizon: int = 5,
) -> dict[int, pd.DataFrame]:
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

    result: dict[int, pd.DataFrame] = {1: base}
    base_records = base.to_dict("records")
    future_events = {
        prediction_event + step - 1
        for step in range(2, horizon + 1)
    }
    requested_events = future_events | {prediction_event}
    fixtures_by_event_and_team: dict[
        int,
        dict[int, list[tuple[int, float, bool]]],
    ] = {event: {} for event in requested_events}
    for fixture in fixtures.loc[:, sorted(_FIXTURE_COLUMNS)].itertuples(index=False):
        try:
            event = int(fixture.event)
            team_h = int(fixture.team_h)
            team_a = int(fixture.team_a)
            home_difficulty = float(fixture.team_h_difficulty)
            away_difficulty = float(fixture.team_a_difficulty)
        except (TypeError, ValueError):
            continue
        if event not in requested_events:
            continue
        event_map = fixtures_by_event_and_team[event]
        event_map.setdefault(team_h, []).append((team_a, home_difficulty, True))
        event_map.setdefault(team_a, []).append((team_h, away_difficulty, False))

    base_matches = fixtures_by_event_and_team[prediction_event]
    base["fixture_count"] = base["team"].map(
        lambda team: len(base_matches.get(team_ids.get(str(team).casefold()), []))
    )
    # Keep the native total once. Future projections scale per fixture, not per DGW.
    base_records = base.to_dict("records")

    for step in range(2, horizon + 1):
        event = prediction_event + step - 1
        matches_by_team = fixtures_by_event_and_team[event]
        rows = []
        for player in base_records:
            team_id = team_ids.get(str(player["team"]).casefold())
            if team_id is None:
                raise ValueError(f"Unknown player team: {player['team']}")
            matches = matches_by_team.get(team_id, [])
            record = dict(player)
            record["gameweek"] = event

            if not matches:
                points = 0.0
                record.update({
                    "predicted_points": points,
                    "opponent": "Blank",
                    "home": None,
                    "difficulty": None,
                    "fixture_count": 0,
                    "projection_method": "blank_gameweek",
                    "uncertainty": 0.0,
                })
                rows.append(record)
                continue

            projected = 0.0
            opponents: list[str] = []
            difficulties: list[float] = []
            homes: list[bool] = []
            target_matches = base_matches.get(team_id, [])
            base_factor = sum(_fixture_factor(difficulty, home) for _, difficulty, home in target_matches)
            if not base_factor:
                base_factor = _base_factor(player)
            for opponent_id, difficulty, home in matches:
                projected += float(player["predicted_points"]) * _fixture_factor(difficulty, home) / base_factor
                opponents.append(team_names.get(opponent_id, f"Team {opponent_id}"))
                difficulties.append(difficulty)
                homes.append(home)

            points = round(projected, 3)
            record.update({
                "predicted_points": points,
                "opponent": " / ".join(opponents),
                "home": homes[0] if len(homes) == 1 else None,
                "difficulty": round(sum(difficulties) / len(difficulties), 2),
                "fixture_count": len(matches),
                "projection_method": "fixture_scaled_v1",
                "uncertainty": _uncertainty(points, step),
            })
            rows.append(record)

        result[step] = pd.DataFrame(rows, columns=list(base.columns))

    return result
