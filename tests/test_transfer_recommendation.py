import pandas as pd

from engine.transfer_analysis import analyze_transfer_recommendation


def make_team():
    return {
        "name": "Test Team",
        "picks": [
            {
                "player_id": 1,
                "position": 1,
                "multiplier": 1,
            },
            {
                "player_id": 2,
                "position": 2,
                "multiplier": 1,
            },
        ],
    }


def make_predictions():
    return pd.DataFrame(
        {
            "player_id": [1, 2, 3, 4, 5],
            "name": [
                "Keeper",
                "Defender Out",
                "Defender Best",
                "Defender Value",
                "Midfielder",
            ],
            "position": [
                "GK",
                "DEF",
                "DEF",
                "DEF",
                "MID",
            ],
            "price": [
                5.0,
                5.0,
                6.0,
                5.0,
                8.0,
            ],
            "predicted_points": [
                5.0,
                4.0,
                8.0,
                6.0,
                10.0,
            ],
        }
    )


def test_transfer_recommendation_returns_best_replacement():
    result = analyze_transfer_recommendation(
        make_team(),
        make_predictions(),
        player_out_id=2,
    )

    assert result["player_out_id"] == 2
    assert result["recommended_player_id"] == 3


def test_transfer_recommendation_includes_gain():
    result = analyze_transfer_recommendation(
        make_team(),
        make_predictions(),
        player_out_id=2,
    )

    assert result["predicted_gain"] == 4.0


def test_transfer_recommendation_includes_alternatives():
    result = analyze_transfer_recommendation(
        make_team(),
        make_predictions(),
        player_out_id=2,
    )

    assert result["alternatives"]["player_id"].tolist() == [4]


def test_transfer_recommendation_respects_budget():
    result = analyze_transfer_recommendation(
        make_team(),
        make_predictions(),
        player_out_id=2,
        budget=5.0,
    )

    assert result["recommended_player_id"] == 4
    assert result["predicted_gain"] == 2.0


def test_transfer_recommendation_requires_player_out():
    try:
        analyze_transfer_recommendation(
            make_team(),
            make_predictions(),
        )
    except Exception:
        return

    assert False, "Expected an error when player_out_id is missing"