from datetime import datetime, timezone

import pandas as pd
from fastapi.testclient import TestClient

import backend.main as main
from backend.review_service import ReviewDataError
from backend.fpl_gateway import GatewayResult


client = TestClient(main.app)


def _bootstrap():
    return {
        "events": [
            {"id": 1, "finished": True, "deadline_time": "2026-08-15T17:30:00Z"},
            {"id": 2, "finished": True, "deadline_time": "2026-08-22T17:30:00Z"},
            {"id": 3, "finished": False, "is_current": True, "deadline_time": "2026-08-29T17:30:00Z"},
        ],
        "elements": [
            {"id": 1, "web_name": "Alpha", "team": 1, "element_type": 3},
            {"id": 2, "web_name": "Beta", "team": 2, "element_type": 4},
        ],
        "teams": [
            {"id": 1, "short_name": "NOR"},
            {"id": 2, "short_name": "SOU"},
        ],
    }


def _install_successful_sources(monkeypatch):
    picks = {
        "picks": [
            {
                "element": 1,
                "position": 1,
                "multiplier": 2,
                "is_captain": True,
                "is_vice_captain": False,
            },
            {
                "element": 2,
                "position": 2,
                "multiplier": 1,
                "is_captain": False,
                "is_vice_captain": True,
            },
        ],
        "entry_history": {
            "event": 2,
            "points": 20,
            "event_transfers_cost": 0,
            "points_on_bench": 0,
        },
    }
    live = {
        "elements": [
            {"id": 1, "stats": {"total_points": 4, "minutes": 30}},
            {"id": 2, "stats": {"total_points": 12, "minutes": 90}},
        ]
    }
    predictions = pd.DataFrame(
        [
            {"player_id": 1, "predicted_points": 6.0, "xmins": 80.0},
            {"player_id": 2, "predicted_points": 5.0, "xmins": 90.0},
        ]
    )
    monkeypatch.setattr(main, "get_bootstrap_data", _bootstrap, raising=False)
    monkeypatch.setattr(main, "get_event_picks", lambda team_id, event: picks, raising=False)
    monkeypatch.setattr(main, "get_manager_transfers", lambda team_id: [], raising=False)
    monkeypatch.setattr(main, "get_event_live", lambda event: live, raising=False)
    monkeypatch.setattr(
        main,
        "_load_review_predictions",
        lambda event, deadline_time=None: (predictions, "gw2_predictions_v5.csv"),
        raising=False,
    )


def test_review_api_defaults_to_latest_finished_gameweek(monkeypatch):
    _install_successful_sources(monkeypatch)
    fetched_at = datetime(2026, 9, 1, 7, 30, tzinfo=timezone.utc)
    token = object()
    monkeypatch.setattr(main, "begin_gateway_trace", lambda: token)
    monkeypatch.setattr(
        main,
        "end_gateway_trace",
        lambda value: [GatewayResult(data={}, fetched_at=fetched_at, stale=True)],
    )

    response = client.get("/api/v1/review/123")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["available"] is True
    assert body["data"]["event"] == 2
    assert body["data"]["prediction_version"] == "gw2_predictions_v5.csv"
    assert body["data"]["summary"]["projected_points"] == 17.0
    assert body["data"]["largest_xmins_miss"] == {
        "player_id": 1,
        "name": "Alpha",
        "predicted_xmins": 80.0,
        "actual_minutes": 30,
        "residual": -50.0,
    }
    assert body["data"]["decision_quality"]["basis"] == "pre_deadline_projection"
    assert body["data"]["next_signals"][0]["type"] == "MINUTES_REVIEW"
    assert body["meta"]["source"] == "derived"
    assert body["meta"]["event"] == 2
    assert body["meta"]["version"] == "gw2_predictions_v5.csv"
    assert body["meta"]["stale"] is True
    assert body["meta"]["official"] == {
        "source": "official",
        "fetched_at": "2026-09-01T07:30:00+00:00",
        "stale": True,
        "version": None,
    }
    assert body["errors"] == []


def test_review_api_defaults_to_the_latest_reviewable_gameweek(monkeypatch):
    _install_successful_sources(monkeypatch)

    def load(event, deadline_time=None):
        if event == 2:
            raise ReviewDataError("No forecast was saved before the GW2 deadline")
        return pd.DataFrame([{"player_id": 1, "predicted_points": 6.0}, {"player_id": 2, "predicted_points": 5.0}]), "gw1_predictions_v5.csv"

    monkeypatch.setattr(main, "_load_review_predictions", load, raising=False)

    body = client.get("/api/v1/review/123").json()

    # GW2 has no saved forecast, so the page opens on GW1 instead.
    assert body["data"]["event"] == 1
    assert body["meta"]["event"] == 1


def test_review_api_returns_explicit_unavailable_state_for_unfinished_event(monkeypatch):
    monkeypatch.setattr(main, "get_bootstrap_data", _bootstrap, raising=False)

    response = client.get("/api/v1/review/123?event=3")

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {
        "available": False,
        "team_id": 123,
        "event": 3,
        "reason": "Gameweek 3 is not finished",
    }
    assert body["meta"]["source"] == "derived"
    assert body["errors"] == []


def test_review_api_returns_explicit_unavailable_state_when_artifact_is_missing(monkeypatch):
    monkeypatch.setattr(main, "get_bootstrap_data", _bootstrap, raising=False)
    monkeypatch.setattr(
        main,
        "_load_review_predictions",
        lambda event, deadline_time=None: (_ for _ in ()).throw(ReviewDataError("No prediction artifact found for GW2")),
        raising=False,
    )

    response = client.get("/api/v1/review/123?event=2")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["available"] is False
    assert body["data"]["reason"] == "No prediction artifact found for GW2"
    assert body["meta"]["version"] is None
    assert body["errors"] == [
        {"area": "model", "message": "No prediction artifact found for GW2"}
    ]


def test_review_api_rejects_unknown_or_invalid_gameweek(monkeypatch):
    monkeypatch.setattr(main, "get_bootstrap_data", _bootstrap, raising=False)

    assert client.get("/api/v1/review/123?event=0").status_code == 400
    unknown = client.get("/api/v1/review/123?event=4")
    assert unknown.status_code == 400
    assert unknown.json()["detail"] == "Gameweek 4 was not found"


def test_review_api_rejects_invalid_team_id():
    response = client.get("/api/v1/review/0")

    assert response.status_code == 400
    assert response.json()["detail"] == "team_id must be positive"
