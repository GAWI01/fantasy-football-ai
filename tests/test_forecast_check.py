"""Each finished Gameweek's pre-deadline forecast is scored once against final points."""

import json

import pandas as pd
import pytest

from historical_data import forecast_check


def publish(directory, gw, generated_at, points, name=None, provenance=None):
    path = directory / (name or f"gw{gw}_predictions_v13.csv")
    pd.DataFrame({"player_id": list(points), "predicted_points": list(points.values())}).to_csv(path, index=False)
    sidecar = {"prediction_event": gw, "prediction_file": path.name, "generated_at": generated_at,
               "schema_version": 1, "model_provenance": provenance}
    path.with_suffix(".csv.manifest.json").write_text(json.dumps(sidecar), encoding="utf-8")
    return path


HISTORY = pd.DataFrame([
    {"element": 1, "GW": 6, "total_points": 8},
    {"element": 2, "GW": 6, "total_points": 1},
    {"element": 2, "GW": 6, "total_points": 3},  # double Gameweek: both fixtures count
])
GAMEWEEKS = pd.DataFrame([{"id": 6, "deadline_time": "2026-10-10T10:00:00Z"}])


def test_scores_every_player_including_those_who_did_not_play():
    result = forecast_check.score_gameweek(
        pd.DataFrame({"player_id": [1, 2, 3], "predicted_points": [6.0, 3.0, 1.0]}), HISTORY, 6)
    assert result["players"] == 3
    assert result["mean_actual"] == pytest.approx(4.0)       # (8 + 4 + 0) / 3
    assert result["bias"] == pytest.approx((6 + 3 + 1 - 12) / 3, abs=1e-3)
    assert result["top10_actual"] == pytest.approx(4.0)


def test_checks_the_pre_deadline_forecast_once(tmp_path):
    log = tmp_path / "forecast_checks.csv"
    publish(tmp_path, 6, "2026-10-04T11:00:00+00:00", {1: 6.0, 2: 3.0},
            provenance={"model_file": "fpl_model_v4.pkl", "validation_state": "validated"})
    publish(tmp_path, 6, "2026-10-11T09:00:00+00:00", {1: 9.0, 2: 9.0}, name="gw6_predictions_v13_r2.csv")

    first = forecast_check.check_finished_gameweeks("2026-27", HISTORY, GAMEWEEKS, tmp_path, log)
    assert [(r["gameweek"], r["artifact"], r["validation_state"]) for r in first] == [
        (6, "gw6_predictions_v13.csv", "validated")]
    assert forecast_check.check_finished_gameweeks("2026-27", HISTORY, GAMEWEEKS, tmp_path, log) == []
    assert len(pd.read_csv(log)) == 1


def test_a_gameweek_without_a_pre_deadline_forecast_is_skipped(tmp_path):
    publish(tmp_path, 6, "2026-10-11T09:00:00+00:00", {1: 6.0})
    assert forecast_check.check_finished_gameweeks(
        "2026-27", HISTORY, GAMEWEEKS, tmp_path, tmp_path / "log.csv") == []
