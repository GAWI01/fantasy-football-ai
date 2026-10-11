import pandas as pd
import pytest

from engine.transfer_analysis import (
    TransferAnalysisError,
    _apply_transfer_plan,
    optimize_transfer_plan,
)


def _valid_squad():
    rows = [
        (1, "GK 1", "Man City", "GKP", 5.0, 5.0),
        (2, "GK 2", "Man City", "GKP", 5.0, 5.0),
        (3, "DEF 1", "Man City", "DEF", 10.0, 5.0),
        (6, "DEF 2", "Arsenal", "DEF", 5.0, 2.0),
        (7, "DEF 3", "Liverpool", "DEF", 5.0, 2.0),
        (8, "DEF 4", "Chelsea", "DEF", 5.0, 2.0),
        (9, "DEF 5", "Aston Villa", "DEF", 5.0, 2.0),
        (4, "MID 1", "Everton", "MID", 10.0, 1.0),
        (11, "MID 2", "Arsenal", "MID", 5.0, 2.0),
        (12, "MID 3", "Liverpool", "MID", 5.0, 2.0),
        (13, "MID 4", "Chelsea", "MID", 5.0, 2.0),
        (14, "MID 5", "Newcastle", "MID", 5.0, 2.0),
        (15, "FWD 1", "Arsenal", "FWD", 5.0, 2.0),
        (16, "FWD 2", "Liverpool", "FWD", 5.0, 2.0),
        (17, "FWD 3", "Chelsea", "FWD", 5.0, 2.0),
    ]
    return pd.DataFrame(
        [
            {
                "player_id": player_id,
                "name": name,
                "team": club,
                "position": position,
                "price": price,
                "predicted_points": points,
            }
            for player_id, name, club, position, price, points in rows
        ]
    )


def _team(df):
    return {
        "picks": [{"player_id": int(player_id)} for player_id in df["player_id"]]
    }


def test_optimize_transfer_plan_rejects_fourth_player_from_same_club():
    owned = _valid_squad()
    data = pd.concat(
        [
            owned,
            pd.DataFrame(
                [
                    {
                        "player_id": 5,
                        "name": "City MID",
                        "position": "MID",
                        "team": "Man City",
                        "price": 10.0,
                        "predicted_points": 10.0,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    result = optimize_transfer_plan(
        team=_team(owned),
        predictions=data,
        free_transfers=1,
        max_transfers=1,
        bank=0.0,
    )

    assert result["transfers_used"] == 0
    assert result["recommended_transfers"] == []


def test_apply_transfer_plan_rejects_fourth_player_from_same_club():
    owned = _valid_squad()
    data = pd.concat(
        [
            owned,
            pd.DataFrame(
                [
                    {
                        "player_id": 5,
                        "name": "City MID",
                        "position": "MID",
                        "team": "Man City",
                        "price": 10.0,
                        "predicted_points": 10.0,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    transfers = [
        {
            "player_out_id": 4,
            "player_out": "MID 1",
            "player_in_id": 5,
            "player_in": "City MID",
            "gain": 9.0,
        }
    ]

    with pytest.raises(
        TransferAnalysisError,
        match="max-three-per-club",
    ):
        _apply_transfer_plan(owned, data, transfers)


def test_optimize_transfer_plan_allows_owned_player_club_change():
    previous = _valid_squad()
    current = previous.copy()

    current.loc[current["player_id"] == 4, "team"] = "Man City"

    result = optimize_transfer_plan(
        team=_team(current),
        predictions=current,
        previous_predictions=previous,
        free_transfers=1,
        max_transfers=1,
        bank=0.0,
    )

    assert result["transfers_used"] == 0
    assert result["post_transfer_squad"] is not None

    man_city_count = sum(
        player["team"] == "Man City"
        for player in result["post_transfer_squad"]
    )
    assert man_city_count == 4


def test_optimize_transfer_plan_accepts_previous_predictions():
    predictions = _valid_squad()

    result = optimize_transfer_plan(
        team=_team(predictions),
        predictions=predictions,
        previous_predictions=predictions.copy(),
        free_transfers=1,
        max_transfers=1,
        bank=0.0,
    )

    assert result["post_transfer_squad"] is not None
    assert len(result["post_transfer_squad"]) == 15
