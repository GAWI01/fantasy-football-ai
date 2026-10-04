from types import SimpleNamespace
from datetime import datetime, timezone

import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app
from backend.fpl_gateway import GatewayResult


def test_v1_players_wraps_live_rankings_with_source_metadata(monkeypatch):
    fetched_at = datetime(2026, 9, 1, 9, 15, tzinfo=timezone.utc)
    token = object()
    monkeypatch.setattr("backend.main.begin_gateway_trace", lambda: token)
    monkeypatch.setattr(
        "backend.main.end_gateway_trace",
        lambda value: [GatewayResult(data={}, fetched_at=fetched_at, stale=True)],
    )
    monkeypatch.setattr(
        "backend.main.get_enriched_player_rankings",
        lambda limit=20, position=None: {
            "event": 2,
            "players": [{"player_id": 1, "name": "Palmer", "position": position}],
        },
    )

    response = TestClient(app).get("/api/v1/players?position=MID&limit=12")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["players"][0]["position"] == "MID"
    assert body["meta"]["source"] == "live"
    assert body["meta"]["fetched_at"] == "2026-09-01T09:15:00+00:00"
    assert body["meta"]["stale"] is True
    assert body["errors"] == []


def test_v1_players_combines_official_status_with_model_minutes(monkeypatch):
    monkeypatch.setattr("backend.main.get_bootstrap_data", lambda: {
        "events": [{"id": 2, "is_current": True}, {"id": 3, "is_next": True}],
        "elements": [{"id": 1, "web_name": "Palmer", "status": "d", "chance_of_playing_next_round": 75}],
    })
    monkeypatch.setattr(
        "backend.main.get_live_player_rankings",
        lambda limit=20, position=None: {
            "current_event": 2,
            "players": [{
                "player_id": 1,
                "name": "Palmer",
                "position": "MID",
                "status": "d",
                "news": "Knock - 75% chance of playing",
            }],
        },
    )
    monkeypatch.setattr(
        "backend.main.load_predictions",
        lambda: pd.DataFrame([{
            "player_id": 1,
            "predicted_points": 8.4,
            "xmins": 78,
            "start_probability": 0.86,
        }]),
    )
    monkeypatch.setattr(
        "backend.main.load_current_manifest",
        lambda path: SimpleNamespace(prediction_file="gw3_predictions_v11.csv", prediction_event=3, model_provenance=None),
    )

    response = TestClient(app).get("/api/v1/players?position=MID&limit=12")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["players"][0]["news"].startswith("Knock")
    assert body["data"]["players"][0]["predicted_points"] == 8.4
    assert body["data"]["players"][0]["xmins"] == 78
    assert body["data"]["players"][0]["start_probability"] == 0.86
    assert body["meta"]["model_version"] == "gw3_predictions_v11.csv"


def test_v1_fixtures_wraps_team_schedule_with_official_metadata(monkeypatch):
    fetched_at = datetime(2026, 9, 1, 9, 30, tzinfo=timezone.utc)
    token = object()
    monkeypatch.setattr("backend.main.begin_gateway_trace", lambda: token)
    monkeypatch.setattr(
        "backend.main.end_gateway_trace",
        lambda value: [GatewayResult(data={}, fetched_at=fetched_at, stale=False)],
    )
    monkeypatch.setattr(
        "backend.main.get_upcoming_fixtures",
        lambda team_id, limit=10: {
            "team_id": team_id,
            "fixtures": [{"fixture_id": 9, "difficulty": 4}],
        },
    )

    response = TestClient(app).get("/api/v1/fixtures?team_id=123&limit=6")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["team_id"] == 123
    assert body["meta"]["source"] == "official"
    assert body["meta"]["fetched_at"] == "2026-09-01T09:30:00+00:00"
    assert body["errors"] == []


def test_v1_fixtures_requires_positive_team_id():
    response = TestClient(app).get("/api/v1/fixtures?team_id=0")
    assert response.status_code == 400


def test_v1_fixture_matrix_wraps_all_club_schedule_with_official_metadata(monkeypatch):
    monkeypatch.setattr(
        "backend.main.get_fixture_matrix",
        lambda start_event=None, horizon=5: {
            "start_event": start_event or 3,
            "horizon": horizon,
            "gameweeks": [3, 4],
            "teams": [{"team_id": 1, "team_short": "ARS", "fixtures": []}],
        },
        raising=False,
    )

    response = TestClient(app).get("/api/v1/fixture-matrix?start_event=3&horizon=2")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["start_event"] == 3
    assert body["data"]["horizon"] == 2
    assert body["meta"]["source"] == "official"


def test_v1_fixture_matrix_rejects_invalid_query_range():
    assert TestClient(app).get("/api/v1/fixture-matrix?horizon=0").status_code == 400
    assert TestClient(app).get("/api/v1/fixture-matrix?start_event=39").status_code == 400
