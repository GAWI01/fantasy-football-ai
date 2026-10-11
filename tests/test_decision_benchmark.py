"""Real-team decision benchmark (recorded official data, pinned GW6 forecast).

Replays FPL responses recorded for the 2026-10-11 audit teams just before
the GW6 deadline (benchmark/). Invariants, not exact transfers, are pinned:
the decision rules must hold for real squads.
"""
import os

import pytest
from fastapi.testclient import TestClient

from benchmark.harness import load_snapshot, pinned_data, replay
from benchmark.run import summarise

os.environ.setdefault("FPL_AI_UPSTREAM_MAX_PER_MINUTE", "1000")

CASES = [(9100001, None), (9100001, 2), (9100006, None), (9100011, None), (9100002, None)]


@pytest.fixture(scope="module")
def results():
    from backend.main import app

    rows = {}
    with pinned_data("gw6"), replay(load_snapshot("gw6_pre_deadline"), pre_deadline_event=6):
        client = TestClient(app)
        for team, ft in CASES:
            query = "" if ft is None else f"?free_transfers={ft}"
            payload = client.get(f"/api/v1/dashboard/{team}{query}").json()
            rows[(team, ft)] = (summarise(payload), payload["data"]["decision"])
    return rows


def test_every_response_names_one_canonical_plan(results):
    for summary, _ in results.values():
        assert summary["consistent"], summary


def test_no_plan_spends_a_transfer_on_a_bench_goalkeeper(results):
    # Before the fix 9100011's whole plan was Forster (0 xMins) -> Pickford.
    for summary, _ in results.values():
        assert not summary["sells_bench_gk"], summary


def test_free_transfers_are_not_spent_automatically(results):
    # 9100006 has two free transfers; the second does not beat rolling it.
    summary, decision = results[(9100006, None)]
    assert summary["free_transfers"] == 2
    assert summary["action"] == "SINGLE_TRANSFER"
    options = {o["transfers_used"]: o for o in decision["transfers"]["options_by_transfer_count"]}
    assert options[2]["decision_score"] < options[1]["decision_score"]


def test_action_label_matches_the_transfer_count(results):
    for summary, decision in results.values():
        count, hit = len(summary["engine_transfers"]), summary["hit_cost"]
        expected = "HOLD" if count == 0 else "HIT" if hit else "SINGLE_TRANSFER" if count == 1 else "MULTI_TRANSFER"
        assert decision["intelligence"]["transfer_action"] == expected


def test_an_available_wildcard_needs_evidence(results):
    summary, decision = results[(9100002, None)]
    signal = decision["intelligence"]["wildcard_signal"]
    assert signal["available"] and signal["evaluated"]
    assert signal["advantage"] < signal["threshold"]
    assert summary["chip"] is None


def test_confidence_is_not_uniformly_high(results):
    assert {summary["confidence"] for summary, _ in results.values()} != {"HIGH"}


def test_captain_and_lineup_never_include_a_player_the_plan_sells(results):
    # Before Phase 2, 9100011 was told to sell B.Fernandes and captain him.
    for summary, _ in results.values():
        assert not summary["captain_is_sold"], summary
        assert not summary["lineup_has_sold_player"], summary


def test_an_unchanged_decision_is_served_from_cache(monkeypatch):
    from backend import main

    calls = []
    original = main.build_decision
    monkeypatch.setattr(main, "build_decision", lambda *a, **k: calls.append(1) or original(*a, **k))
    main._DECISION_CACHE.clear()
    with pinned_data("gw6"), replay(load_snapshot("gw6_pre_deadline"), pre_deadline_event=6):
        client = TestClient(main.app)
        first = client.get("/api/v1/dashboard/9100003").json()["data"]["decision"]
        second = client.get("/api/v1/dashboard/9100003").json()["data"]["decision"]
        changed = client.get("/api/v1/dashboard/9100003?free_transfers=2").json()["data"]["decision"]
    assert len(calls) == 2  # the free-transfer override is a different input
    assert first["transfers"]["recommended_transfers"] == second["transfers"]["recommended_transfers"]
    assert changed["transfers"]["free_transfers"] == 2


def test_own_transfer_is_scored_on_the_recommendation_scale():
    from backend.main import app

    with pinned_data("gw6"), replay(load_snapshot("gw6_pre_deadline"), pre_deadline_event=6):
        client = TestClient(app)
        recommended = client.get("/api/v1/dashboard/9100001").json()["data"]["decision"]["transfers"]
        move = recommended["recommended_transfers"][0]
        same = client.get(f"/api/v1/evaluate/9100001?sell={move['player_out_id']}&buy={move['player_in_id']}").json()["data"]
        bad = client.get("/api/v1/evaluate/9100001?sell=411&buy=249").json()["data"]
        illegal = client.get("/api/v1/evaluate/9100001?sell=411&buy=429").json()["data"]
        malformed = client.get("/api/v1/evaluate/9100001?sell=abc&buy=1")
    # The recommended move evaluated by hand scores exactly like the recommendation.
    assert same["legal"] and same["option"]["decision_score"] == pytest.approx(recommended["decision_score"])
    assert bad["legal"] and bad["option"]["decision_score"] < 0
    assert not illegal["legal"] and "position for position" in illegal["reason"]
    assert malformed.status_code == 400
