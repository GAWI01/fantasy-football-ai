from datetime import datetime, timezone
import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app, get_official_team
from backend.live_service import LiveDataServiceError


def predictions():
    rows = []
    # 15-player valid current team + 2 alternatives
    data = [
        (1,"GK1","GK","A",5,4),(2,"GK2","GK","B",4,3),
        (3,"D1","DEF","A",5,5),(4,"D2","DEF","B",5,4),(5,"D3","DEF","C",5,4),
        (6,"D4","DEF","D",5,3),(7,"D5","DEF","E",3,3),
        (8,"M1","MID","A",8,6),(9,"M2","MID","B",7,5),(10,"M3","MID","C",7,5),
        (11,"M4","MID","D",6,4),(12,"M5","MID","E",5,3),
        (13,"F1","FWD","F",8,6),(14,"F2","FWD","G",7,5),(15,"F3","FWD","H",6,4),
        (16,"EliteMid","MID","I",8,9),(17,"AltMid","MID","J",7,7),
    ]
    return pd.DataFrame(data, columns=[
        "player_id","name","position","team","price","predicted_points"
    ])


def team():
    return {
        "id": 123,
        "name": "Test FC",
        "bank": 0.0,
        "value": 1000.0,
        "transfers": 1,
        "started_event": 1,
        "picks": [{"player_id": i} for i in range(1,16)],
    }


def mock_plan_context(monkeypatch, chip_reader=None):
    monkeypatch.setattr(
        "backend.main.get_bootstrap_data",
        lambda: {
            "events": [{"id": 2, "is_current": True}, {"id": 3, "is_next": True}],
            "elements": [
                {"id": int(row.player_id), "web_name": row.name, "status": "a"}
                for row in predictions().itertuples(index=False)
            ],
        },
    )
    monkeypatch.setattr(
        "backend.main.load_current_manifest",
        lambda path: type("Manifest", (), {"prediction_file": "gw3.csv", "prediction_event": 3})(),
    )
    monkeypatch.setattr(
        "backend.main.load_current_fixtures",
        lambda: pd.DataFrame(columns=["event", "team_h", "team_a", "team_h_difficulty", "team_a_difficulty"]),
    )
    monkeypatch.setattr(
        "backend.main.load_current_teams",
        lambda: pd.DataFrame([{"id": index, "name": name} for index, name in enumerate("ABCDEFGHIJ", 1)]),
    )
    monkeypatch.setattr(
        "backend.main.get_manager_chip_state",
        chip_reader or (lambda team_id, event, **kwargs: {
            "known": True,
            "period": 1,
            "period_events": [1, 19],
            "used_in_period": [],
            "wildcard_available": True,
            "free_hit_available": True,
            "bench_boost_available": True,
            "triple_captain_available": True,
        }),
    )
    monkeypatch.setattr(
        "backend.main.get_manager_transfer_state",
        lambda team_id, event, started_event: {
            "known": True,
            "free_transfers": 3,
        },
    )


def test_decision_endpoint_returns_unified_result(monkeypatch):
    monkeypatch.setattr(
        "backend.main.get_team_data",
        lambda team_id: team(),
    )
    monkeypatch.setattr(
        "backend.main.load_predictions",
        lambda: predictions(),
    )
    mock_plan_context(monkeypatch)

    client = TestClient(app)
    response = client.get("/api/decision/123")

    assert response.status_code == 200
    body = response.json()

    assert len(body["optimal_squad"]["players"]) == 15
    assert len(body["starting_xi"]["players"]) == 11
    assert len(body["bench"]["players"]) == 4
    assert "captain" in body
    assert "vice_captain" in body
    assert "transfers" in body
    assert body["intelligence"]["horizon"]["horizon"] == 5
    assert body["intelligence"]["chip_state"]["known"] is True
    assert body["transfers"]["free_transfers"] == 3
    assert body["transfers"]["free_transfers_source"] == "derived"


def test_decision_uses_user_free_transfers_over_derived_count(monkeypatch):
    monkeypatch.setattr("backend.main.get_team_data", lambda team_id: team())
    monkeypatch.setattr("backend.main.load_predictions", lambda: predictions())
    mock_plan_context(monkeypatch)

    response = TestClient(app).get("/api/decision/123?free_transfers=0")

    assert response.status_code == 200
    body = response.json()
    assert body["transfers"]["free_transfers"] == 0
    assert body["transfers"]["free_transfers_source"] == "user"


def test_decision_marks_free_transfers_unknown_when_history_fails(monkeypatch):
    monkeypatch.setattr("backend.main.get_team_data", lambda team_id: team())
    monkeypatch.setattr("backend.main.load_predictions", lambda: predictions())
    mock_plan_context(monkeypatch)

    def unavailable(team_id, event, started_event):
        raise LiveDataServiceError("transfers unavailable")

    monkeypatch.setattr("backend.main.get_manager_transfer_state", unavailable)

    response = TestClient(app).get("/api/decision/123")

    assert response.status_code == 200
    assert response.json()["transfers"]["free_transfers_source"] == "unknown"


def test_decision_remains_available_when_chip_history_fails(monkeypatch):
    monkeypatch.setattr("backend.main.get_team_data", lambda team_id: team())
    monkeypatch.setattr("backend.main.load_predictions", lambda: predictions())

    def unavailable(team_id, event, **kwargs):
        raise LiveDataServiceError("history unavailable")

    mock_plan_context(monkeypatch, unavailable)

    response = TestClient(app).get("/api/decision/123")

    assert response.status_code == 200
    body = response.json()
    assert body["intelligence"]["chip_state"]["known"] is False
    assert body["intelligence"]["chip_advisor"]["recommended_chip"] is None


def test_decision_endpoint_validates_team_id():
    client = TestClient(app)
    response = client.get("/api/decision/not-an-id")
    assert response.status_code == 422


def test_official_team_builds_display_ready_player_evidence_without_a_prediction_artifact(monkeypatch):
    monkeypatch.setattr(
        "backend.main.fetch_public_team",
        lambda team_id: {
            "team_id": team_id,
            "name": "Official XI",
            "event": 2,
            "bank": 0.5,
            "picks": [{"player_id": 10, "position": 1}],
        },
    )
    monkeypatch.setattr(
        "backend.main.get_bootstrap_data",
        lambda: {
            "elements": [{
                "id": 10,
                "web_name": "Saka",
                "element_type": 3,
                "team": 1,
                "now_cost": 100,
                "status": "a",
                "news": "",
                "form": "7.2",
                "selected_by_percent": "42.1",
                "total_points": 32,
                "starts": 2,
                "goals_scored": 1,
                "assists": 2,
                "bonus": 4,
                "expected_goals": "1.40",
                "expected_assists": "1.10",
                "ict_index": "21.7",
            }],
            "teams": [{"id": 1, "name": "Arsenal", "short_name": "ARS"}],
        },
    )
    monkeypatch.setattr(
        "backend.main.load_predictions",
        lambda: (_ for _ in ()).throw(AssertionError("model must not load")),
    )

    result = get_official_team(123)

    assert result["name"] == "Official XI"
    assert result["picks"][0]["name"] == "Saka"
    assert result["picks"][0]["price"] == 10.0
    assert {
        "form": 7.2,
        "ownership": 42.1,
        "season_points": 32,
        "starts": 2,
        "season_goals": 1,
        "season_assists": 2,
        "season_bonus": 4,
        "expected_goals": 1.4,
        "expected_assists": 1.1,
        "ict_index": 21.7,
    }.items() <= result["picks"][0].items()
    assert "prediction" not in result["picks"][0]


def test_dashboard_v1_composes_existing_domain_services(monkeypatch):
    monkeypatch.setattr(
        "backend.main.load_current_manifest",
        lambda path: type(
            "Manifest",
            (),
            {
                "prediction_file": "gw3_predictions_v11.csv",
                "prediction_event": 3,
                "model_provenance": None,
            },
        )(),
    )
    monkeypatch.setattr(
        "backend.main.get_bootstrap_data",
        lambda: {
            "events": [
                {
                    "id": 2,
                    "is_current": True,
                    "deadline_time": "2026-08-28T17:30:00Z",
                },
                {
                    "id": 3,
                    "is_next": True,
                    "deadline_time": "2099-09-04T17:30:00Z",
                },
            ]
        },
    )
    monkeypatch.setattr(
        "backend.main.get_official_team",
        lambda team_id: {
            "team_id": team_id,
            "name": "Test FC",
            "event": 2,
            "picks": [],
        },
    )
    monkeypatch.setattr(
        "backend.main.get_live_team",
        lambda team_id: {"status": "LIVE", "picks": []},
    )
    monkeypatch.setattr(
        "backend.main.get_team_history_endpoint",
        lambda team_id: {"history": []},
    )
    monkeypatch.setattr(
        "backend.main.get_upcoming_fixtures",
        lambda team_id, limit=10: {"fixtures": []},
    )
    monkeypatch.setattr(
        "backend.main.get_enriched_player_rankings",
        lambda limit=20, position=None: {"players": []},
    )
    monkeypatch.setattr(
        "backend.main.get_decision",
        lambda team_id, free_transfers=None: {"transfers": {"net_gain": 0}},
    )

    response = TestClient(app).get("/api/v1/dashboard/123")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["team"]["team_id"] == 123
    assert body["data"]["live"]["status"] == "LIVE"
    assert body["meta"]["event"] == 2
    assert body["meta"]["current_event"] == 2
    assert body["meta"]["prediction_event"] == 3
    assert body["meta"]["actions_locked"] is False
    assert body["meta"]["prediction_version"] == "gw3_predictions_v11.csv"
    assert body["meta"]["model_validation_state"] == "unverified"
    assert body["errors"] == [{"area": "model", "message": "Model provenance and production validation are unverified"}]


def test_dashboard_v1_passes_user_free_transfers_to_decision(monkeypatch):
    seen = {}

    def decision(team_id, free_transfers=None):
        seen["free_transfers"] = free_transfers
        return {"transfers": {"free_transfers": free_transfers}}

    monkeypatch.setattr(
        "backend.main.get_official_team",
        lambda team_id: {"team_id": team_id, "name": "Test FC", "event": 2, "picks": []},
    )
    for name in ("get_live_team", "get_team_history_endpoint"):
        monkeypatch.setattr(f"backend.main.{name}", lambda team_id: {})
    monkeypatch.setattr("backend.main.get_upcoming_fixtures", lambda team_id, limit=10: {})
    monkeypatch.setattr("backend.main.get_enriched_player_rankings", lambda limit=20, position=None: {})
    monkeypatch.setattr("backend.main.get_decision", decision)

    client = TestClient(app)
    response = client.get("/api/v1/dashboard/123?free_transfers=0")

    assert response.status_code == 200
    assert seen["free_transfers"] == 0
    assert response.json()["data"]["decision"]["transfers"]["free_transfers"] == 0
    assert client.get("/api/v1/dashboard/123?free_transfers=6").status_code == 400


def test_plan_v1_wraps_decision_with_model_version(monkeypatch):
    monkeypatch.setattr(
        "backend.main.get_decision",
        lambda team_id: {"intelligence": {"action": "HOLD"}},
    )
    monkeypatch.setattr(
        "backend.main.load_current_manifest",
        lambda path: type("Manifest", (), {
            "prediction_file": "gw3_predictions_v11.csv",
            "prediction_event": 3,
            "generated_at": datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc),
        })(),
    )

    response = TestClient(app).get("/api/v1/plan/123")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["intelligence"]["action"] == "HOLD"
    assert body["meta"]["source"] == "model"
    assert body["meta"]["version"] == "gw3_predictions_v11.csv"
    assert body["meta"]["event"] == 3
    assert body["meta"]["fetched_at"] == "2026-09-01T08:00:00+00:00"
