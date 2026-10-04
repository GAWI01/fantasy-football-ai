import pandas as pd

from feature_contract import FEATURE_COLUMNS, feature_metadata
from historical_data.train_model import prepare_data


def row(gw, points, history_mean):
    return {
        **{column: 0.0 for column in FEATURE_COLUMNS},
        "position": "MID", "price": 6, "was_home": gw == 1, "fixture_difficulty": 3,
        "player_id": 1, "GW": gw, "total_points": points,
        "points_avg_5": history_mean, "xP": history_mean,
        **feature_metadata(), "history_cutoff_gw": gw - 1,
    }


def test_prepare_data_targets_current_gameweek_when_features_are_for_that_gameweek():
    result = prepare_data(pd.DataFrame([row(1, 6, 0), row(2, 9, 6)]))

    assert result["GW"].tolist() == [1, 2]
    assert result["target"].tolist() == [6.0, 9.0]
