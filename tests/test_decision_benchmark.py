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

CASES = [(895045, None), (895045, 2), (145931, None), (639449, None), (4182037, None)]


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
    # Before the fix 639449's whole plan was Forster (0 xMins) -> Pickford.
    for summary, _ in results.values():
        assert not summary["sells_bench_gk"], summary


def test_free_transfers_are_not_spent_automatically(results):
    # 145931 has two free transfers; the second does not beat rolling it.
    summary, decision = results[(145931, None)]
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
    summary, decision = results[(4182037, None)]
    signal = decision["intelligence"]["wildcard_signal"]
    assert signal["available"] and signal["evaluated"]
    assert signal["advantage"] < signal["threshold"]
    assert summary["chip"] is None


def test_confidence_is_not_uniformly_high(results):
    assert {summary["confidence"] for summary, _ in results.values()} != {"HIGH"}
