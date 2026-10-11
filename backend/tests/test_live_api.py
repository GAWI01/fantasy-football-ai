
from fastapi.testclient import TestClient

from backend.main import app


def test_live_players_endpoint(monkeypatch):
    monkeypatch.setattr(
        "backend.main.get_live_players",
        lambda limit=20, position=None: {
            "current_event": 2,
            "gameweek_name": "Gameweek 2",
            "status": "LIVE",
            "finished": False,
            "players": [{"player_id": 10, "name": "Saka", "event_points": 7}],
        },
    )
    response = TestClient(app).get("/live/players?limit=10")
    assert response.status_code == 200
    assert response.json()["players"][0]["event_points"] == 7


def test_team_history_endpoint(monkeypatch):
    monkeypatch.setattr(
        "backend.main.get_team_history",
        lambda team_id: {
            "team_id": team_id,
            "history": [{"event": 1, "points": 50, "overall_rank": 100}],
        },
    )
    response = TestClient(app).get("/team/123/history")
    assert response.status_code == 200
    assert response.json()["team_id"] == 123
    assert response.json()["history"][0]["event"] == 1


def test_live_team_endpoint_merges_actual_gameweek_points(monkeypatch):
    monkeypatch.setattr(
        "backend.main.get_team_data",
        lambda team_id: {
            "team_id": team_id,
            "name": "Test FC",
            "picks": [
                {"player_id": 10, "position": 3, "is_captain": True, "multiplier": 2},
                {"player_id": 11, "position": 3, "is_captain": False, "multiplier": 1},
            ],
        },
    )
    monkeypatch.setattr(
        "backend.main.get_live_players",
        lambda limit=100, position=None: {
            "current_event": 2,
            "gameweek_name": "Gameweek 2",
            "status": "LIVE",
            "finished": False,
            "players": [
                {"player_id": 10, "name": "Saka", "event_points": 7},
                {"player_id": 11, "name": "Odegaard", "event_points": 3},
            ],
        },
    )
    monkeypatch.setattr(
        "backend.main.get_event_fixtures",
        lambda event: {"event": event, "fixtures": []},
        raising=False,
    )
    response = TestClient(app).get("/team/123/live")
    assert response.status_code == 200
    body = response.json()
    assert body["current_event"] == 2
    assert body["picks"][0]["event_points"] == 7
    assert body["picks"][0]["multiplied_points"] == 14


def test_live_team_excludes_bench_points_and_reports_official_match_progress(monkeypatch):
    monkeypatch.setattr(
        "backend.main.get_team_data",
        lambda team_id: {
            "team_id": team_id,
            "name": "Test FC",
            "picks": [
                {"player_id": 10, "position": 1, "multiplier": 2, "is_captain": True},
                {"player_id": 11, "position": 2, "multiplier": 1},
                {"player_id": 12, "position": 12, "multiplier": 0},
            ],
        },
    )
    monkeypatch.setattr(
        "backend.main.get_live_players",
        lambda limit=700, position=None: {
            "current_event": 2,
            "gameweek_name": "Gameweek 2",
            "status": "LIVE",
            "finished": False,
            "players": [
                {"player_id": 10, "name": "Saka", "team_short": "ARS", "team_id": 1, "event_points": 7, "minutes": 90, "goals": 1, "assists": 1, "bonus": 2},
                {"player_id": 11, "name": "Odegaard", "team_short": "ARS", "team_id": 2, "event_points": 3, "minutes": 55, "yellow_cards": 1},
                {"player_id": 12, "name": "Bench Star", "team_short": "CHE", "team_id": 3, "event_points": 9, "minutes": 90, "red_cards": 1},
            ],
        },
    )
    monkeypatch.setattr(
        "backend.main.get_event_fixtures",
        lambda event: {
            "event": event,
            "fixtures": [
                {"fixture_id": 21, "home_team_id": 1, "away_team_id": 4, "home_team": "A", "away_team": "D", "home_score": 2, "away_score": 0, "started": True, "finished": True, "minutes": 90},
                {"fixture_id": 22, "home_team_id": 2, "away_team_id": 5, "home_team": "B", "away_team": "E", "home_score": 1, "away_score": 1, "started": True, "finished": False, "minutes": 55},
                {"fixture_id": 23, "home_team_id": 3, "away_team_id": 6, "home_team": "C", "away_team": "F", "home_score": None, "away_score": None, "started": False, "finished": False, "minutes": 0},
            ],
        },
        raising=False,
    )

    response = TestClient(app).get("/team/123/live")

    assert response.status_code == 200
    body = response.json()
    assert body["picks"][2]["multiplied_points"] == 0
    assert body["summary"] == {
        "live_points": 17,
        "captain_contribution": 14,
        "players_finished": 1,
        "players_live": 1,
        "players_remaining": 0,
        "players_without_fixture": 0,
    }
    assert [fixture["fixture_id"] for fixture in body["fixtures"]] == [21, 22, 23]
    assert body["events"] == [
        {"player_id": 10, "player_name": "Saka", "team_short": "ARS", "event_type": "GOAL", "count": 1, "active": True, "provisional": False},
        {"player_id": 10, "player_name": "Saka", "team_short": "ARS", "event_type": "ASSIST", "count": 1, "active": True, "provisional": False},
        {"player_id": 10, "player_name": "Saka", "team_short": "ARS", "event_type": "BONUS", "count": 2, "active": True, "provisional": False},
        {"player_id": 11, "player_name": "Odegaard", "team_short": "ARS", "event_type": "YELLOW_CARD", "count": 1, "active": True, "provisional": False},
        {"player_id": 12, "player_name": "Bench Star", "team_short": "CHE", "event_type": "RED_CARD", "count": 1, "active": False, "provisional": False},
    ]
