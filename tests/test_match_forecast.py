"""Match forecasts: probabilities that add up, follow the rates, and an endpoint that never claims odds."""
import pytest
from fastapi.testclient import TestClient

from backend import fpl_gateway, main
from backend.match_forecast import match_probabilities
from benchmark.harness import replay

API = fpl_gateway.FPL_API


def test_probabilities_add_up_and_follow_the_rates():
    p = match_probabilities(2.0, 0.8)
    assert sum(p["result"].values()) == pytest.approx(1.0, abs=0.002)
    assert p["result"]["home"] > p["result"]["away"]
    assert p["clean_sheet"]["home"] > p["clean_sheet"]["away"]
    assert p["total_goals_over"]["1.5"] > p["total_goals_over"]["2.5"] > p["total_goals_over"]["3.5"]
    assert p["likely_scores"][0]["probability"] >= p["likely_scores"][1]["probability"]


def test_equal_sides_are_symmetric():
    p = match_probabilities(1.3, 1.3)
    assert p["result"]["home"] == pytest.approx(p["result"]["away"], abs=0.001)


def _responses():
    teams = [{"id": i, "name": f"Club {i}", "short_name": f"C{i}"} for i in (1, 2, 3, 4)]
    elements = [{"id": 10 + i, "team": i, "element_type": 4, "expected_goals": 2.0 * i} for i in (1, 2, 3, 4)]
    elements += [{"id": 20 + i, "team": i, "element_type": 1, "expected_goals_conceded": 6.0 - i} for i in (1, 2, 3, 4)]
    events = [{"id": 1, "is_current": True, "is_next": False, "finished": True},
              {"id": 2, "is_current": False, "is_next": True, "finished": False}]
    fixtures = [
        {"id": 1, "event": 1, "team_h": 1, "team_a": 2, "finished": True, "team_h_score": 1, "team_a_score": 0},
        {"id": 2, "event": 1, "team_h": 3, "team_a": 4, "finished": True, "team_h_score": 2, "team_a_score": 2},
        {"id": 3, "event": 2, "team_h": 4, "team_a": 1, "finished": False, "kickoff_time": "2026-10-24T14:00:00Z"},
        {"id": 4, "event": 2, "team_h": 2, "team_a": 3, "finished": False, "kickoff_time": "2026-10-24T11:30:00Z"},
    ]
    return {f"{API}/bootstrap-static/": {"teams": teams, "elements": elements, "events": events},
            f"{API}/fixtures/": fixtures}


def test_endpoint_returns_next_gameweek_in_kickoff_order():
    with replay(_responses()):
        body = TestClient(main.app).get("/api/v1/match-forecasts").json()
    data = body["data"]
    assert data["event"] == 2
    assert [f["fixture_id"] for f in data["fixtures"]] == [4, 3]
    assert body["meta"]["source"] == "model"
    assert "odds" not in str(body).lower()


def test_endpoint_rejects_out_of_range_event():
    assert TestClient(main.app).get("/api/v1/match-forecasts?event=40").status_code == 400


def test_backtest_summary_ships_in_the_backend_image():
    from pathlib import Path
    rules = (Path(__file__).resolve().parent.parent / ".dockerignore").read_text().splitlines()
    assert "!backend/data/match_forecast_backtest.json" in rules
