"""Match forecasts from the clubs' expected goals.

Each side's goals are modelled as independent Poisson counts, with the same
club strengths and venue factors as the clean sheet chance in
`fixture_service`: a side's expected goals = league average x own attack x
opponent defence x venue. From the two rates come the result, both-teams-to-
score, total-goals and scoreline probabilities.

These are model probabilities for reading a fixture, not odds and not advice
to bet. Independent Poisson slightly under-predicts draws; the walk-forward
check in `scripts/backtest_match_forecasts.py` measures how far.
"""
from __future__ import annotations

import math
from typing import Any

from .fixture_service import AWAY_CONCEDED, HOME_CONCEDED, team_strengths

MAX_GOALS = 10
TOTAL_LINES = (1.5, 2.5, 3.5)


def expected_goals(strengths: dict[int, dict[str, float]], home_id: int, away_id: int) -> tuple[float, float] | None:
    home, away = strengths.get(home_id), strengths.get(away_id)
    if not home or not away:
        return None
    average = home["league_average"]
    home_goals = average * (home["xg_per_match"] / average) * (away["xgc_per_match"] / average) * AWAY_CONCEDED
    away_goals = average * (away["xg_per_match"] / average) * (home["xgc_per_match"] / average) * HOME_CONCEDED
    return home_goals, away_goals


def _poisson(rate: float) -> list[float]:
    probabilities = [math.exp(-rate) * rate ** goals / math.factorial(goals) for goals in range(MAX_GOALS + 1)]
    probabilities[-1] += max(0.0, 1.0 - sum(probabilities))  # fold the tail into the last cell
    return probabilities


def match_probabilities(home_rate: float, away_rate: float) -> dict[str, Any]:
    home, away = _poisson(home_rate), _poisson(away_rate)
    grid = [[h * a for a in away] for h in home]
    cells = [(i, j, grid[i][j]) for i in range(MAX_GOALS + 1) for j in range(MAX_GOALS + 1)]
    home_win = sum(p for i, j, p in cells if i > j)
    draw = sum(p for i, j, p in cells if i == j)
    away_win = sum(p for i, j, p in cells if i < j)
    scorelines = sorted(cells, key=lambda cell: cell[2], reverse=True)[:3]
    return {
        "expected_goals": {"home": round(home_rate, 2), "away": round(away_rate, 2)},
        "result": {"home": round(home_win, 3), "draw": round(draw, 3), "away": round(away_win, 3)},
        "both_teams_score": round((1 - home[0]) * (1 - away[0]), 3),
        "total_goals_over": {
            str(line): round(sum(p for i, j, p in cells if i + j > line), 3) for line in TOTAL_LINES
        },
        "team_goals_over": {
            side: {"0.5": round(1 - probs[0], 3), "1.5": round(1 - probs[0] - probs[1], 3)}
            for side, probs in (("home", home), ("away", away))
        },
        "clean_sheet": {"home": round(away[0], 3), "away": round(home[0], 3)},
        "likely_scores": [{"home": i, "away": j, "probability": round(p, 3)} for i, j, p in scorelines],
    }


def event_forecasts(bootstrap: dict[str, Any], raw_fixtures: list[dict[str, Any]], event: int) -> list[dict[str, Any]]:
    """Forecasts for every fixture in `event`, from data up to now."""
    strengths = team_strengths(bootstrap, raw_fixtures)
    teams = {int(team["id"]): team for team in bootstrap.get("teams") or [] if team.get("id") is not None}
    rows = []
    for fixture in raw_fixtures or []:
        if fixture.get("event") != event:
            continue
        home_id, away_id = int(fixture.get("team_h") or 0), int(fixture.get("team_a") or 0)
        rates = expected_goals(strengths, home_id, away_id)
        if rates is None:
            continue
        home, away = teams.get(home_id, {}), teams.get(away_id, {})
        rows.append({
            "fixture_id": fixture.get("id"),
            "kickoff_time": fixture.get("kickoff_time"),
            "started": bool(fixture.get("started")),
            "finished": bool(fixture.get("finished") or fixture.get("finished_provisional")),
            "score": None if fixture.get("team_h_score") is None else {
                "home": fixture.get("team_h_score"), "away": fixture.get("team_a_score")},
            "home": {"id": home_id, "name": home.get("name"), "short": home.get("short_name"),
                     "matches": strengths[home_id]["matches"]},
            "away": {"id": away_id, "name": away.get("name"), "short": away.get("short_name"),
                     "matches": strengths[away_id]["matches"]},
            **match_probabilities(*rates),
        })
    rows.sort(key=lambda row: (row["kickoff_time"] is None, row["kickoff_time"] or "", row["fixture_id"] or 0))
    return rows


_BACKTEST_PATH = __import__("pathlib").Path(__file__).resolve().parent / "data" / "match_forecast_backtest.json"


def backtest_summary() -> dict[str, Any] | None:
    """The walk-forward check shipped with the code, for the page's honesty labels."""
    import json
    try:
        return json.loads(_BACKTEST_PATH.read_text())
    except (OSError, ValueError):
        return None


def get_match_forecasts(event: int | None = None) -> dict[str, Any]:
    from .fixture_service import FixtureServiceError, _gameweek_status, _get_json

    bootstrap = _get_json("bootstrap-static/")
    if not isinstance(bootstrap, dict):
        raise FixtureServiceError("FPL bootstrap response is invalid")
    current_event, next_event = _gameweek_status(bootstrap)
    selected = event if event is not None else next_event or current_event
    if selected is None:
        raise FixtureServiceError("Could not determine the next gameweek")
    raw_fixtures = _get_json("fixtures/")
    if not isinstance(raw_fixtures, list):
        raise FixtureServiceError("FPL fixtures response is invalid")
    return {
        "event": selected,
        "current_event": current_event,
        "next_event": next_event,
        "fixtures": event_forecasts(bootstrap, raw_fixtures, selected),
        "backtest": backtest_summary(),
    }
