import pandas as pd

from backtesting.production_parity import (
    reconstruct_production_target,
    validate_historical_prediction_rows,
)
from engine.feature_contract import FEATURE_COLUMNS


def make_frame():
    row = {column: 0.0 for column in FEATURE_COLUMNS}
    row["position"] = "MID"
    row["opponent_team"] = 5
    row["was_home"] = True
    return pd.DataFrame(
        [
            {"player_id": 1, "GW": 3, "total_points": 7, **row},
            {"player_id": 1, "GW": 4, "total_points": 2, **row},
        ]
    )


def test_historical_row_is_prediction_gw():
    result = validate_historical_prediction_rows(make_frame())
    assert result.target_column == "total_points"
    assert result.fixture_columns == ("opponent_team", "was_home")
    assert result.valid_rows == 2


def test_reconstruct_production_target_does_not_shift_to_next_gw():
    result = reconstruct_production_target(make_frame())
    assert result["GW"].tolist() == [3, 4]
    assert result["target"].tolist() == [7.0, 2.0]
