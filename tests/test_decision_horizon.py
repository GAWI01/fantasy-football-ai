import pandas as pd
from engine.decision_horizon import normalize_horizon_predictions, player_horizon_projection
def test_only_requested_horizon_is_loaded():
    p=pd.DataFrame([{"player_id":1,"predicted_points":5}])
    out=normalize_horizon_predictions(p,{2:pd.DataFrame([{"player_id":1,"predicted_points":6}]),4:pd.DataFrame([{"player_id":1,"predicted_points":99}])},3)
    assert sorted(out)==[1,2]
def test_missing_future_data_reports_coverage():
    p=pd.DataFrame([{"player_id":1,"predicted_points":5}])
    out=normalize_horizon_predictions(p,None,3)
    assert player_horizon_projection(1,out,3)["coverage"]<1


def test_projection_preserves_actual_gameweek_method_and_uncertainty():
    p = pd.DataFrame([{
        "player_id": 1,
        "predicted_points": 5,
        "gameweek": 3,
        "projection_method": "native_model",
        "uncertainty": 1.2,
        "fixture_count": 1,
    }])
    future = pd.DataFrame([{
        "player_id": 1,
        "predicted_points": 4,
        "gameweek": 4,
        "projection_method": "fixture_scaled_v1",
        "uncertainty": 1.6,
        "fixture_count": 1,
    }])

    frames = normalize_horizon_predictions(p, {2: future}, 2)
    result = player_horizon_projection(1, frames, 2)

    assert result["gameweeks"][0]["gameweek"] == 3
    assert result["gameweeks"][0]["horizon_index"] == 1
    assert result["gameweeks"][1]["gameweek"] == 4
    assert result["gameweeks"][1]["projection_method"] == "fixture_scaled_v1"
    assert result["gameweeks"][1]["uncertainty"] == 1.6
    assert result["gameweeks"][1]["fixture_count"] == 1


def test_enriched_first_horizon_frame_replaces_plain_prediction_frame():
    plain = pd.DataFrame([{"player_id": 1, "predicted_points": 5}])
    enriched = pd.DataFrame([{
        "player_id": 1,
        "predicted_points": 5,
        "gameweek": 3,
        "projection_method": "native_model",
        "uncertainty": 1.1,
        "fixture_count": 1,
    }])

    frames = normalize_horizon_predictions(plain, {1: enriched}, 1)
    result = player_horizon_projection(1, frames, 1)

    assert result["gameweeks"][0]["gameweek"] == 3
    assert result["gameweeks"][0]["uncertainty"] == 1.1
