"""Free Hit planning, API bounds and error mapping, paged mini-league standings."""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend import fpl_gateway, main
from backend.team_service import TeamNotFoundError, fetch_public_team
from benchmark.harness import replay

API = fpl_gateway.FPL_API


def _team_responses():
    return {
        f"{API}/entry/9/": {"id": 9, "name": "Test FC", "current_event": 8},
        f"{API}/entry/9/event/8/picks/": {
            "active_chip": "freehit",
            "entry_history": {"bank": 3},
            "picks": [{"element": 100 + i, "position": i + 1} for i in range(15)],
        },
        f"{API}/entry/9/event/7/picks/": {
            "active_chip": None,
            "entry_history": {"bank": 12},
            "picks": [{"element": 200 + i, "position": i + 1} for i in range(15)],
        },
    }


def test_live_view_keeps_the_free_hit_squad_but_planning_reverts_it():
    with replay(_team_responses()):
        live = fetch_public_team(9)
        assert live["active_chip"] == "freehit"
        assert live["picks"][0]["player_id"] == 100
        assert live["bank"] == 0.3

        main_team = main.get_planning_team(9)
        assert main_team["free_hit_reverted"] is True
        assert main_team["picks"][0]["player_id"] == 200
        assert main_team["bank"] == 1.2


@pytest.mark.parametrize("query", ["budget=0", "budget=201", "max_transfers=16", "max_transfers=-1"])
def test_decision_rejects_out_of_range_inputs_before_any_work(monkeypatch, query):
    monkeypatch.setattr(main, "_decision_inputs", lambda *a: pytest.fail("should not compute"))
    assert TestClient(main.app).get(f"/api/decision/123?{query}").status_code == 400


@pytest.mark.parametrize("path", ["/api/decision/123", "/team/123", "/team/123/live"])
def test_unknown_team_is_404_not_502(monkeypatch, path):
    def missing(*_a, **_k):
        raise TeamNotFoundError("404")
    monkeypatch.setattr(main, "fetch_public_team", missing)
    response = TestClient(main.app).get(path)
    assert response.status_code == 404


@pytest.mark.parametrize("path", ["/team/0", "/team/-4/live", "/api/decision/0"])
def test_non_positive_team_ids_are_rejected(path):
    assert TestClient(main.app).get(path).status_code == 400


def test_unexpected_errors_answer_json_without_details(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("/srv/secret/path exploded")
    monkeypatch.setattr(main, "load_current_manifest", boom)
    response = TestClient(main.app, raise_server_exceptions=False).get("/api/v1/plan/123")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}


def test_waiting_on_a_hung_solve_times_out_with_503():
    import threading
    cache = main._DecisionCache()
    cache.wait_timeout = 0.05
    started, release = threading.Event(), threading.Event()

    def slow():
        started.set()
        release.wait(5)
        return {}

    owner = threading.Thread(target=lambda: cache.get_or_compute("k", slow))
    owner.start()
    started.wait(5)
    with pytest.raises(main.HTTPException) as caught:
        cache.get_or_compute("k", lambda: {})
    assert caught.value.status_code == 503
    release.set()
    owner.join()


def test_reference_squad_survives_a_row_without_price(monkeypatch):
    from tests.test_decision_api import mock_plan_context, predictions, team
    rows = pd.concat([predictions(), pd.DataFrame([{
        "player_id": 99, "name": "Broken", "position": "MID", "team": "Z",
        "price": float("nan"), "predicted_points": 9.0,
    }])], ignore_index=True)
    monkeypatch.setattr(main, "get_team_data", lambda _: team())
    monkeypatch.setattr(main, "load_predictions", lambda: rows)
    mock_plan_context(monkeypatch)
    response = TestClient(main.app).get("/api/decision/123")
    assert response.status_code == 200
    assert 99 not in [p["player_id"] for p in response.json()["optimal_squad"]["players"]]


def test_manager_beyond_the_first_standings_page_is_found():
    first = [{"entry": i, "entry_name": f"T{i}", "rank": i, "total": 500 - i} for i in range(1, 51)]
    second = [{"entry": i, "entry_name": f"T{i}", "rank": i, "total": 500 - i} for i in range(51, 61)]
    responses = {
        f"{API}/leagues-classic/77/standings/": {
            "league": {"id": 77}, "standings": {"has_next": True, "results": first}},
        f"{API}/leagues-classic/77/standings/?page_standings=2": {
            "standings": {"has_next": False, "results": second}},
    }
    from backend.league_service import _standings
    with replay(responses):
        _, rows = _standings(77, 55)
    assert len(rows) == 51
    assert rows[-1]["entry"] == 55
