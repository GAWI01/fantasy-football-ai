"""Serving decisions must reuse identical work without reusing stale horizons."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pandas as pd
import pytest

from backend import main


def test_changed_future_projection_recomputes_served_decision(monkeypatch):
    forecasts = {
        7: pd.DataFrame({"player_id": [1], "predicted_points": [3.0]}),
        8: pd.DataFrame({"player_id": [1], "predicted_points": [4.0]}),
    }
    inputs = {
        "team": {"team_id": 123, "bank": 0, "picks": []},
        "predictions": forecasts[7],
        "manifest": SimpleNamespace(prediction_file="gw7.csv", generated_at="2026-10-12"),
        "bootstrap": {"elements": [], "events": []},
        "transfer_state": {"known": True},
        "chip_state": {},
        "free_transfers": 1,
        "max_transfers": 3,
        "horizon": 2,
        "horizon_predictions": forecasts,
    }
    monkeypatch.setattr(main, "_DECISION_CACHE", main._DecisionCache())
    monkeypatch.setattr(main, "_decision_inputs", lambda *args: inputs)

    def forecast_decision(*args, horizon_predictions, **kwargs):
        return {"transfers": {"projected_points": float(
            horizon_predictions[8]["predicted_points"].sum())}}

    monkeypatch.setattr(main, "build_decision", forecast_decision)
    assert main.get_decision(123)["transfers"]["projected_points"] == 4.0
    forecasts[8] = forecasts[8].assign(predicted_points=9.0)
    assert main.get_decision(123)["transfers"]["projected_points"] == 9.0


def test_concurrent_equivalent_requests_share_one_calculation():
    cache = main._DecisionCache()
    assert hasattr(cache, "get_or_compute"), "Duplicate requests need per-key shared computation"
    entered, release = Event(), Event()
    computations = []

    def calculate():
        computations.append(1)
        entered.set()
        assert release.wait(timeout=5)
        return {"projected_points": 42.0}

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(cache.get_or_compute, "same-plan", calculate)
        assert entered.wait(timeout=5)
        second = pool.submit(cache.get_or_compute, "same-plan", calculate)
        release.set()
        assert first.result(timeout=5) == {"projected_points": 42.0}
        assert second.result(timeout=5) == {"projected_points": 42.0}
    assert len(computations) == 1


def test_failed_shared_calculation_can_be_retried():
    cache = main._DecisionCache()
    assert hasattr(cache, "get_or_compute"), "Failed computations must permit retry"

    def fail():
        raise ValueError("forecast unavailable")

    with pytest.raises(ValueError, match="forecast unavailable"):
        cache.get_or_compute("plan", fail)
    assert cache.get_or_compute("plan", lambda: {"projected_points": 7.0}) == {
        "projected_points": 7.0}


def test_different_keys_do_not_wait_for_an_unrelated_calculation():
    cache = main._DecisionCache()
    assert hasattr(cache, "get_or_compute"), "Sharing one plan must not block other teams"
    entered, release = Event(), Event()

    def slow():
        entered.set()
        assert release.wait(timeout=5)
        return {"team": 1}

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(cache.get_or_compute, "first", slow)
        try:
            assert entered.wait(timeout=5)
            second = pool.submit(cache.get_or_compute, "second", lambda: {"team": 2})
            assert second.result(timeout=2) == {"team": 2}
        finally:
            release.set()
        assert first.result(timeout=5) == {"team": 1}
