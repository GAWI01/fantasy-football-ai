"""Planning the next Gameweek while the current one is live (audit P0-1)."""
import json

import pandas as pd

from backend import main
from backend.data_manifest import load_current_manifest


def _publish(directory, event, generated_at, points, *, pointer=False, provenance=None):
    name = f"gw{event}_predictions_v13.csv"
    pd.DataFrame({"player_id": [1, 2], "predicted_points": points}).to_csv(directory / name, index=False)
    payload = {"season": "2026-27", "prediction_event": event, "prediction_file": name,
               "generated_at": generated_at, "player_count": 2, "schema_version": 1}
    if provenance is not None:
        payload["model_provenance"] = provenance
    (directory / f"{name}.manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    if pointer:
        (directory / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def test_live_expectations_use_the_live_gameweeks_pre_deadline_forecast(tmp_path, monkeypatch):
    # GW6 is live; the provisional GW7 forecast is already the served artifact.
    _publish(tmp_path, 6, "2026-10-04T19:00:00+00:00", [4.5, 2.0])
    _publish(tmp_path, 7, "2026-10-11T14:00:00+00:00", [6.0, 3.0], pointer=True,
             provenance={"forecast_stage": "provisional", "history_cutoff_gw": 5})
    monkeypatch.setattr(main, "PREDICTIONS_DIR", tmp_path)
    monkeypatch.setattr(main, "get_bootstrap_data", lambda: {"events": [
        {"id": 6, "deadline_time": "2026-10-10T10:00:00Z"},
        {"id": 7, "deadline_time": "2026-10-17T10:00:00Z"},
    ]})
    assert main._live_event_expectations(6) == {1: 4.5, 2: 2.0}


def test_forecasts_published_after_the_deadline_never_become_live_expectations(tmp_path, monkeypatch):
    _publish(tmp_path, 6, "2026-10-10T12:00:00+00:00", [9.0, 9.0], pointer=True)
    monkeypatch.setattr(main, "PREDICTIONS_DIR", tmp_path)
    monkeypatch.setattr(main, "get_bootstrap_data", lambda: {"events": [{"id": 6, "deadline_time": "2026-10-10T10:00:00Z"}]})
    assert main._live_event_expectations(6) is None


def test_forecast_stage_is_reported_and_legacy_manifests_are_final(tmp_path):
    _publish(tmp_path, 7, "2026-10-11T14:00:00+00:00", [6.0, 3.0], pointer=True,
             provenance={"forecast_stage": "provisional", "history_cutoff_gw": 5})
    assert main._forecast_stage(load_current_manifest(tmp_path / "manifest.json")) == {
        "forecast_stage": "provisional", "history_cutoff_gw": 5}
    _publish(tmp_path, 7, "2026-10-11T14:00:00+00:00", [6.0, 3.0], pointer=True)
    assert main._forecast_stage(load_current_manifest(tmp_path / "manifest.json")) == {
        "forecast_stage": "final", "history_cutoff_gw": 6}
