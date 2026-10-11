
import pandas as pd
import pytest

from backend import live_service


def bootstrap():
    return {
        "events": [
            {"id": 1, "name": "Gameweek 1", "finished": True, "is_current": False, "is_next": False},
            {"id": 2, "name": "Gameweek 2", "finished": False, "is_current": True, "is_next": False},
            {"id": 3, "name": "Gameweek 3", "finished": False, "is_current": False, "is_next": True},
        ],
        "teams": [
            {"id": 1, "name": "Arsenal", "short_name": "ARS"},
            {"id": 2, "name": "Aston Villa", "short_name": "AVL"},
        ],
        "elements": [
            {"id": 10, "web_name": "Saka", "team": 1, "element_type": 3, "now_cost": 100,
             "selected_by_percent": "40.0", "form": "8.0", "status": "a", "event_points": 7,
             "total_points": 20, "ep_this": "6.5", "expected_goals": "1.25",
             "expected_assists": "0.75", "expected_goal_involvements": "2.00",
             "influence": "48.2", "creativity": "52.4", "threat": "88.0", "ict_index": "18.9"},
            {"id": 11, "web_name": "Odegaard", "team": 1, "element_type": 3, "now_cost": 75,
             "selected_by_percent": "12.0", "form": "5.0", "status": "a", "event_points": 3,
             "total_points": 12, "ep_this": "4.2"},
        ],
    }


def live_payload():
    return {
        "elements": [
            {"id": 10, "stats": {"total_points": 7, "minutes": 90, "goals_scored": 1, "assists": 1, "bonus": 2, "saves": 3, "penalties_saved": 1, "penalties_missed": 1, "yellow_cards": 1, "red_cards": 1, "own_goals": 1}},
            {"id": 11, "stats": {"total_points": 3, "minutes": 45, "goals_scored": 0, "assists": 0, "bonus": 0}},
        ]
    }


def test_current_gameweek_and_live_players_are_sorted_by_actual_points(monkeypatch):
    payloads = {"bootstrap-static/": bootstrap(), "event/2/live/": live_payload()}
    monkeypatch.setattr(live_service, "_get_json", lambda path: payloads[path])

    result = live_service.get_live_players(limit=2)

    assert result["current_event"] == 2
    assert result["status"] == "LIVE"
    assert [p["player_id"] for p in result["players"]] == [10, 11]
    assert result["players"][0]["event_points"] == 7
    assert result["players"][0]["minutes"] == 90
    assert result["players"][0] | {
        "goals": 1,
        "assists": 1,
        "bonus": 2,
        "saves": 3,
        "penalties_saved": 1,
        "penalties_missed": 1,
        "yellow_cards": 1,
        "red_cards": 1,
        "own_goals": 1,
        "expected_goals": 1.25,
        "expected_assists": 0.75,
        "expected_goal_involvements": 2.0,
        "influence": 48.2,
        "creativity": 52.4,
        "threat": 88.0,
        "ict_index": 18.9,
    } == result["players"][0]


def test_team_history_is_normalized_and_ordered(monkeypatch):
    history = {
        "current": [
            {"event": 2, "points": 55, "total_points": 105, "overall_rank": 123456, "rank": 4567},
            {"event": 1, "points": 50, "total_points": 50, "overall_rank": 200000, "rank": 10000},
        ],
        "past": [{"season_name": "2025/26", "total_points": 2400, "rank": 9000}],
    }
    monkeypatch.setattr(live_service, "_get_json", lambda path: history)
    result = live_service.get_team_history(123)
    assert result["team_id"] == 123
    assert [x["event"] for x in result["history"]] == [1, 2]
    assert result["history"][-1]["overall_rank"] == 123456


def test_live_status_marks_finished_when_event_is_finished(monkeypatch):
    b = bootstrap()
    b["events"][1]["finished"] = True
    monkeypatch.setattr(live_service, "_get_json", lambda path: b if path == "bootstrap-static/" else live_payload())
    result = live_service.get_live_players(limit=2)
    assert result["status"] == "FINISHED"


def test_live_player_market_accepts_the_full_fpl_universe(monkeypatch):
    monkeypatch.setattr(
        live_service,
        "_get_json",
        lambda path: bootstrap() if path == "bootstrap-static/" else live_payload(),
    )

    result = live_service.get_live_players(limit=700)

    assert len(result["players"]) == 2
