"""Mini-league standings, effective ownership and rival comparison."""
import pytest
from fastapi.testclient import TestClient

from backend import fpl_gateway, main
from benchmark.harness import replay

API = fpl_gateway.FPL_API
BOOTSTRAP = {
    "events": [{"id": 5, "finished": True, "is_current": False}, {"id": 6, "finished": False, "is_current": True},
               {"id": 7, "finished": False, "is_current": False, "is_next": True}],
    "teams": [{"id": 1, "short_name": "MCI"}, {"id": 2, "short_name": "ARS"}],
    "elements": [{"id": pid, "web_name": f"P{pid}", "team": 1 + pid % 2, "element_type": 3} for pid in range(1, 20)],
}


def _picks(ids, captain, bench=(), chip=None):
    return {"active_chip": chip, "picks": [
        {"element": pid, "multiplier": 0 if pid in bench else (3 if chip == "3xc" else 2) if pid == captain else 1}
        for pid in ids]}


def _responses():
    standings = {"league": {"id": 77, "name": "Friends"}, "standings": {"results": [
        {"entry": 1, "entry_name": "Leader FC", "player_name": "Ada Lead", "rank": 1, "last_rank": 1, "event_total": 60, "total": 400},
        {"entry": 2, "entry_name": "Me United", "player_name": "Bo Me", "rank": 2, "last_rank": 3, "event_total": 50, "total": 380},
        {"entry": 3, "entry_name": "Third", "player_name": "Cy Three", "rank": 3, "last_rank": 2, "event_total": 40, "total": 350},
    ]}}
    return {
        f"{API}/bootstrap-static/": BOOTSTRAP,
        f"{API}/entry/2/": {"leagues": {"classic": [
            {"id": 314, "name": "Overall", "league_type": "s", "rank_count": 11_000_000},
            {"id": 77, "name": "Friends", "league_type": "x", "rank_count": 3, "entry_rank": 2, "entry_last_rank": 3},
        ]}},
        f"{API}/leagues-classic/77/standings/": standings,
        # Everyone owns 1; leader and third captain it, third with Triple Captain.
        f"{API}/entry/1/event/6/picks/": _picks([1, 2, 3], captain=1),
        f"{API}/entry/2/event/6/picks/": _picks([1, 4, 5], captain=4, bench=(5,)),
        f"{API}/entry/3/event/6/picks/": _picks([1, 2, 6], captain=1, chip="3xc"),
    }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "_next_gw_projections", lambda _bootstrap: {1: 6.0, 2: 5.0, 3: 2.0, 4: 7.0, 5: 1.0})
    with replay(_responses()):
        yield TestClient(main.app)


def test_only_private_leagues_are_listed(client):
    leagues = client.get("/api/v1/leagues/2").json()["data"]["leagues"]
    assert [league["league_id"] for league in leagues] == [77]
    assert leagues[0]["rank"] == 2


def test_standings_gaps_and_effective_ownership(client):
    data = client.get("/api/v1/league/77?team_id=2").json()["data"]
    assert data["event"] == 6 and data["analysed_managers"] == 3
    assert [row["gap_to_you"] for row in data["standings"]] == [20, 0, -30]
    assert data["standings"][1]["is_you"] and data["standings"][2]["active_chip"] == "3xc"
    players = {p["player_id"]: p for p in data["players"]}
    # Player 1: owned by all three, captained by two (one Triple Captain): (2 + 1 + 3) / 3.
    assert players[1]["eo"] == pytest.approx(200.0)
    assert players[1]["owners"] == 3 and players[1]["captains"] == 2 and players[1]["you"] == "STARTER"
    # Player 2: two of three own it, you do not: a threat.
    assert players[2]["eo"] == pytest.approx(66.7) and players[2]["role"] == "THREAT"
    # Player 4: only you, and captained: a differential (no rival owns him).
    assert players[4]["you"] == "CAPTAIN" and players[4]["role"] == "DIFFERENTIAL"
    assert players[4]["rival_eo"] == 0.0 and players[2]["rival_eo"] == pytest.approx(100.0)
    # A bench player adds no effective ownership.
    assert players[5]["eo"] == 0.0 and players[5]["you"] == "BENCH"
    assert players[1]["next_gw_points"] == 6.0
    assert "GW6" in data["basis"]


def test_rival_comparison_splits_shared_and_unique_players(client):
    data = client.get("/api/v1/league/77/rival/1?team_id=2").json()["data"]
    assert [p["player_id"] for p in data["only_you"]] == [4, 5]
    assert [p["player_id"] for p in data["only_rival"]] == [2, 3]
    assert [p["player_id"] for p in data["shared"]] == [1]
    assert data["same_captain"] is False
    # Unique starters' next-GW points: you 7 (4; 5 is benched), rival 5 + 2.
    assert data["unique_next_gw_points"] == {"you": 7.0, "rival": 7.0}


def test_unknown_league_rival_and_self_are_rejected(client):
    assert client.get("/api/v1/league/78?team_id=2").status_code == 404
    assert client.get("/api/v1/league/77/rival/9?team_id=2").status_code == 404
    assert client.get("/api/v1/league/77/rival/2?team_id=2").status_code == 400
