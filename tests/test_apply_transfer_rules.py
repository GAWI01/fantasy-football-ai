import pandas as pd
import pytest

from engine.transfer_analysis import _apply_transfer_plan, TransferAnalysisError


def _valid_squad() -> pd.DataFrame:
    return pd.DataFrame([
        {"player_id": 1, "name": "City 1", "position": "GKP", "team": "Man City", "price": 5.0, "predicted_points": 5.0},
        {"player_id": 2, "name": "City 2", "position": "GKP", "team": "Man City", "price": 5.0, "predicted_points": 5.0},
        {"player_id": 3, "name": "City DEF", "position": "DEF", "team": "Man City", "price": 10.0, "predicted_points": 5.0},
        {"player_id": 6, "name": "Arsenal DEF 1", "position": "DEF", "team": "Arsenal", "price": 5.0, "predicted_points": 2.0},
        {"player_id": 7, "name": "Liverpool DEF 1", "position": "DEF", "team": "Liverpool", "price": 5.0, "predicted_points": 2.0},
        {"player_id": 8, "name": "Chelsea DEF 1", "position": "DEF", "team": "Chelsea", "price": 5.0, "predicted_points": 2.0},
        {"player_id": 9, "name": "Villa DEF 1", "position": "DEF", "team": "Aston Villa", "price": 5.0, "predicted_points": 2.0},
        {"player_id": 4, "name": "Everton MID", "position": "MID", "team": "Everton", "price": 10.0, "predicted_points": 1.0},
        {"player_id": 11, "name": "Arsenal MID", "position": "MID", "team": "Arsenal", "price": 5.0, "predicted_points": 2.0},
        {"player_id": 12, "name": "Liverpool MID", "position": "MID", "team": "Liverpool", "price": 5.0, "predicted_points": 2.0},
        {"player_id": 13, "name": "Chelsea MID", "position": "MID", "team": "Chelsea", "price": 5.0, "predicted_points": 2.0},
        {"player_id": 14, "name": "Newcastle MID", "position": "MID", "team": "Newcastle", "price": 5.0, "predicted_points": 2.0},
        {"player_id": 15, "name": "Arsenal FWD", "position": "FWD", "team": "Arsenal", "price": 5.0, "predicted_points": 2.0},
        {"player_id": 16, "name": "Liverpool FWD", "position": "FWD", "team": "Liverpool", "price": 5.0, "predicted_points": 2.0},
        {"player_id": 17, "name": "Chelsea FWD", "position": "FWD", "team": "Chelsea", "price": 5.0, "predicted_points": 2.0},
    ])


def test_apply_transfer_plan_rejects_fourth_player_from_same_club():
    owned = _valid_squad()
    data = pd.concat([
        owned,
        pd.DataFrame([{
            "player_id": 5,
            "name": "City MID 1",
            "position": "MID",
            "team": "Man City",
            "price": 10.0,
            "predicted_points": 10.0,
        }]),
    ], ignore_index=True)

    transfers = [{
        "player_out_id": 4,
        "player_out": "Everton MID 1",
        "player_in_id": 5,
        "player_in": "City MID 1",
        "gain": 9.0,
    }]

    with pytest.raises(TransferAnalysisError, match="max-three-per-club"):
        _apply_transfer_plan(owned, data, transfers)


def test_apply_transfer_plan_reflects_existing_player_club_change():
    owned = _valid_squad()
    data = owned.copy()

    data.loc[data["player_id"] == 4, "team"] = "Man City"

    # _apply_transfer_plan receives the current squad representation in
    # `owned`. A pre-existing real-world club change must therefore already
    # be reflected there before applying a transfer plan.
    current_owned = owned.copy()
    current_owned.loc[current_owned["player_id"] == 4, "team"] = "Man City"

    result = _apply_transfer_plan(
        current_owned,
        data,
        [],
    )

    assert len(result) == 15
    assert result["team"].value_counts()["Man City"] == 4
