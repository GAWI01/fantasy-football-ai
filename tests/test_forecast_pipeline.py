"""Live forecasting, validation checks and season fetching on a small synthetic season.

Teams 1-3. GW1: 1 v 2 (team 3 blank). GW2: 1 v 3 and 2 v 1 (team 1 doubles).
GW3: 2 v 3 (team 1 blank).
"""

import json

import numpy as np
import pandas as pd
import pytest

from backend.data_manifest import load_current_manifest
from feature_contract import FEATURE_COLUMNS, feature_matrix, feature_metadata
from historical_data import fetch_season_history, validate_model
from historical_data.build_features import build_feature_frame
from historical_data.current_data import predict_gw

FIXTURES = pd.DataFrame([
    {"id": 11, "event": 1, "team_h": 1, "team_a": 2, "team_h_difficulty": 2, "team_a_difficulty": 4},
    {"id": 21, "event": 2, "team_h": 1, "team_a": 3, "team_h_difficulty": 3, "team_a_difficulty": 3},
    {"id": 22, "event": 2, "team_h": 2, "team_a": 1, "team_h_difficulty": 4, "team_a_difficulty": 2},
    {"id": 31, "event": 3, "team_h": 2, "team_a": 3, "team_h_difficulty": 5, "team_a_difficulty": 1},
])
PLAYERS = pd.DataFrame([
    {"id": 1, "element_type": 3, "team": 1, "now_cost": 80, "web_name": "Mid", "second_name": "Mid",
     "status": "a", "chance_of_playing_next_round": None, "news": ""},
    {"id": 2, "element_type": 2, "team": 2, "now_cost": 50, "web_name": "Def", "second_name": "Def",
     "status": "d", "chance_of_playing_next_round": 50, "news": "Knock"},
    {"id": 3, "element_type": 4, "team": 3, "now_cost": 70, "web_name": "Fwd", "second_name": "Fwd",
     "status": "i", "chance_of_playing_next_round": None, "news": "Injured"},
])
TEAMS = pd.DataFrame([{"id": 1, "name": "Alpha"}, {"id": 2, "name": "Beta"}, {"id": 3, "name": "Gamma"}])


def played(element, position, fixture, gw, home, opponent, points, minutes=90):
    return {"element": element, "position": position, "fixture": fixture, "GW": gw, "round": gw,
            "was_home": home, "opponent_team": opponent, "value": 60, "total_points": points,
            "minutes": minutes, "goals_scored": 0, "assists": 0, "bps": 10, "influence": 10,
            "creativity": 5, "threat": 5, "ict_index": 2}


HISTORY = pd.DataFrame([
    played(1, "MID", 11, 1, True, 2, 6), played(2, "DEF", 11, 1, False, 1, 2),
    played(1, "MID", 21, 2, True, 3, 9), played(1, "MID", 22, 2, False, 2, 1, minutes=30),
    played(2, "DEF", 22, 2, True, 1, 6), played(3, "FWD", 21, 2, False, 1, 5),
])


class FeatureModel:
    """Deterministic stand-in whose output depends on the features."""

    feature_contract_metadata_ = feature_metadata()

    def predict(self, matrix):
        return (matrix["points_avg_5"] + matrix["fixture_difficulty"]).to_numpy(float)


def setup_season(tmp_path, monkeypatch, target, players=PLAYERS):
    current = tmp_path / "current"
    season = tmp_path / "history" / "2026-27"
    current.mkdir()
    season.mkdir(parents=True)
    players.to_csv(current / "players_raw.csv", index=False)
    TEAMS.to_csv(current / "teams_current.csv", index=False)
    pd.DataFrame([{"id": gw, "is_next": gw == target, "finished": gw < target, "data_checked": gw < target,
                   "deadline_time": f"2026-08-{10 + 7 * gw}T10:00:00Z"} for gw in (1, 2, 3)]).to_csv(
        current / "gameweeks_current.csv", index=False)
    HISTORY[HISTORY.GW < target].to_csv(season / "merged_gw.csv", index=False)
    FIXTURES.to_csv(season / "fixtures.csv", index=False)
    monkeypatch.setattr(predict_gw, "CURRENT_DIR", current)
    monkeypatch.setattr(predict_gw, "PLAYERS_PATH", current / "players_raw.csv")
    monkeypatch.setattr(predict_gw, "TEAMS_PATH", current / "teams_current.csv")
    monkeypatch.setattr(predict_gw, "GAMEWEEKS_PATH", current / "gameweeks_current.csv")
    monkeypatch.setattr(predict_gw, "HISTORY_DIR", tmp_path / "history")
    monkeypatch.setattr(predict_gw, "load_prediction_model",
                        lambda *a, **k: (FeatureModel(), {"validation_state": "validated", "model_sha256": "a" * 64}))
    return current


def test_blank_players_stay_in_the_pool_with_zero_points(tmp_path, monkeypatch):
    current = setup_season(tmp_path, monkeypatch, target=3)
    path = predict_gw.main()
    result = pd.read_csv(path).set_index("player_id")
    assert set(result.index) == {1, 2, 3}
    assert result.loc[1, "fixture_count"] == 0
    assert result.loc[1, "predicted_points"] == 0
    assert result.loc[1, "xmins"] == 0
    assert load_current_manifest(current / "manifest.json").prediction_event == 3


def test_availability_scales_points_and_minutes_but_keeps_the_model_output(tmp_path, monkeypatch):
    setup_season(tmp_path, monkeypatch, target=3)
    result = pd.read_csv(predict_gw.main()).set_index("player_id")
    defender = result.loc[2]
    # GW3 home v team 3 (difficulty 5); completed history 2 and 6 points.
    assert defender["ml_prediction"] == pytest.approx(4 + 5)
    assert defender["predicted_points"] == pytest.approx(0.5 * defender["ml_prediction"])
    assert defender["xmins"] == pytest.approx(0.5 * defender["xmins_available"])
    assert defender["availability"] == "RISK"
    injured = result.loc[3]
    assert injured["ml_prediction"] > 0
    assert injured["predicted_points"] == 0
    assert injured["availability"] == "UNAVAILABLE"


def test_double_gameweek_sums_both_fixtures(tmp_path, monkeypatch):
    setup_season(tmp_path, monkeypatch, target=2)
    result = pd.read_csv(predict_gw.main()).set_index("player_id")
    midfielder = result.loc[1]
    assert midfielder["fixture_count"] == 2
    # History mean 6; difficulties 3 (home v 3) and 2 (away at 2).
    assert midfielder["ml_prediction"] == pytest.approx((6 + 3) + (6 + 2))
    assert midfielder["opponent"] == "Gamma / Beta"
    assert pd.isna(midfielder["home"])
    assert midfielder["xmins_available"] == pytest.approx(2 * 90)


def test_forecast_waits_for_final_scores_in_earlier_gameweeks(tmp_path, monkeypatch):
    current = setup_season(tmp_path, monkeypatch, target=3)
    gameweeks = pd.read_csv(current / "gameweeks_current.csv")
    gameweeks.loc[gameweeks.id == 2, "data_checked"] = False
    gameweeks.to_csv(current / "gameweeks_current.csv", index=False)
    with pytest.raises(predict_gw.HistoryIncompleteError, match="GW2"):
        predict_gw.main()


def test_schedule_digest_does_not_depend_on_the_platform_line_ending(monkeypatch):
    import hashlib
    import os

    expected = hashlib.sha256(b"id,team_h,team_a\n31,2,3\n").hexdigest()
    for line_end in ("\n", "\r\n"):
        monkeypatch.setattr(os, "linesep", line_end)
        assert predict_gw.target_schedule_digest(FIXTURES, 3) == expected


def _rewrite_served_schedule_digest(current, digest):
    """Simulate metadata written on another platform (manifest and sidecar agree)."""
    manifest = json.loads((current / "manifest.json").read_text(encoding="utf-8"))
    manifest["model_provenance"]["target_schedule_sha256"] = digest
    for name in ("manifest.json", f"{manifest['prediction_file']}.manifest.json"):
        (current / name).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def test_a_forecast_published_on_windows_is_recognised_on_linux(tmp_path, monkeypatch):
    current = setup_season(tmp_path, monkeypatch, target=3)
    first = predict_gw.main()
    # Before the fix the digest followed os.linesep; GW6 v12 carries the CRLF form.
    _rewrite_served_schedule_digest(current, predict_gw._schedule_digest(FIXTURES, 3, "\r\n"))
    assert predict_gw.main() == first
    assert sorted(path.name for path in current.glob("gw3_predictions_*.csv")) == [first.name]


def test_identical_content_is_never_republished(tmp_path, monkeypatch):
    current = setup_season(tmp_path, monkeypatch, target=3)
    first = predict_gw.main()
    _rewrite_served_schedule_digest(current, "0" * 64)
    assert predict_gw.main() == first
    assert sorted(path.name for path in current.glob("gw3_predictions_*.csv")) == [first.name]


def test_season_comes_from_source_gameweeks_not_the_generation_date(tmp_path, monkeypatch):
    current = setup_season(tmp_path, monkeypatch, target=3)
    predict_gw.main()
    assert load_current_manifest(current / "manifest.json").season == "2026-27"


def test_a_gameweek_is_published_once_and_again_only_when_its_fixtures_change(tmp_path, monkeypatch):
    current = setup_season(tmp_path, monkeypatch, target=3)
    first = predict_gw.main()
    original = first.read_bytes()
    # Prices move daily; the API reapplies them, so no new artifact is made.
    moved = PLAYERS.copy()
    moved.loc[moved.id == 2, "now_cost"] = 55
    moved.to_csv(current / "players_raw.csv", index=False)
    assert predict_gw.main() == first
    # A rescheduled fixture changes the target Gameweek: a new revision, old bytes kept.
    fixtures = FIXTURES.copy()
    fixtures.loc[fixtures.id == 31, "event"] = 4
    fixtures.to_csv(tmp_path / "history" / "2026-27" / "fixtures.csv", index=False)
    second = predict_gw.main()
    assert first.read_bytes() == original
    assert second.name == "gw3_predictions_v12_r2.csv"
    assert pd.read_csv(second)["predicted_points"].eq(0).all()
    assert load_current_manifest(current / "manifest.json").prediction_file == second.name
    assert predict_gw.main() == second


def test_live_path_reproduces_historical_rows_and_predictions():
    frame = build_feature_frame(HISTORY, FIXTURES)
    result = validate_model.parity_check(FeatureModel(), HISTORY, FIXTURES, frame)
    assert result["passed"], result
    assert result["gameweeks"] == [1, 2]


def test_features_for_a_gameweek_ignore_its_own_and_later_outcomes():
    frame = build_feature_frame(HISTORY, FIXTURES)
    result = validate_model.causality_check(HISTORY, FIXTURES, frame)
    assert result["passed"], result


def test_score_reports_fixture_error_and_player_ranking():
    rows = pd.DataFrame({"GW": [1, 1, 1], "player_id": [1, 2, 3], "total_points": [6, 2, 0]})
    metrics = validate_model.score(rows, np.array([5.0, 3.0, 0.0]))
    assert metrics["mae"] == pytest.approx(2 / 3)
    assert metrics["spearman_by_gw"] == pytest.approx(1.0)


def test_season_fetch_keeps_only_final_gameweeks_and_display_names():
    bootstrap = {
        "events": [{"id": 1, "finished": True, "data_checked": True, "deadline_time": "2026-08-21T17:30:00Z"},
                   {"id": 2, "finished": True, "data_checked": False, "deadline_time": "2026-08-28T17:30:00Z"}],
        "teams": [{"id": 1, "name": "Alpha"}],
        "elements": [{"id": 7, "web_name": "Surname", "first_name": "Private", "second_name": "Surname",
                      "element_type": 1, "team": 1}],
    }
    summaries = {7: {"history": [{"element": 7, "fixture": 11, "round": 1, "total_points": 3, "minutes": 90},
                                 {"element": 7, "fixture": 21, "round": 2, "total_points": 9, "minutes": 90}]}}
    events = fetch_season_history.completed_events(bootstrap)
    rows = fetch_season_history.history_rows(bootstrap, summaries, events)
    assert events == [1]
    assert rows["GW"].tolist() == [1]
    assert rows.loc[0, "name"] == "Surname"
    assert rows.loc[0, "position"] == "GK"
    assert "Private" not in rows.to_csv()
    assert fetch_season_history.season_label(bootstrap) == "2026-27"


def test_api_applies_latest_official_availability_to_v12_forecasts():
    import backend.main as main

    predictions = pd.DataFrame([{
        "player_id": 2, "name": "Def", "position": "DEF", "team": "Beta", "price": 5.0,
        "predicted_points": 4.5, "ml_prediction": 9.0, "xmins": 45.0, "xmins_available": 90.0,
        "start_probability": 0.5, "start_probability_available": 1.0,
    }])
    bootstrap = {"elements": [{"id": 2, "web_name": "Def", "now_cost": 50, "element_type": 2, "team": 2,
                               "status": "d", "chance_of_playing_next_round": 75}],
                 "teams": [{"id": 2, "name": "Beta"}]}
    row = main._apply_official_player_state(predictions, bootstrap).iloc[0]
    assert row["predicted_points"] == pytest.approx(6.75)
    assert row["xmins"] == pytest.approx(67.5)
    assert row["start_probability"] == pytest.approx(0.75)
    bootstrap["elements"][0].update(status="a", chance_of_playing_next_round=None)
    assert main._apply_official_player_state(predictions, bootstrap).iloc[0]["predicted_points"] == 9.0


def test_model_input_matrix_follows_the_contract_for_live_rows():
    from historical_data.forecast import live_feature_rows

    fixture_rows, blank_rows = live_feature_rows(HISTORY[HISTORY.GW < 3], PLAYERS, FIXTURES, 3)
    assert sorted(fixture_rows["player_id"]) == [2, 3]
    assert blank_rows["player_id"].tolist() == [1]
    assert tuple(feature_matrix(fixture_rows).columns) == FEATURE_COLUMNS
