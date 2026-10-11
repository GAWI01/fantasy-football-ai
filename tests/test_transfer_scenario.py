import pandas as pd
import pytest

from engine.transfer_analysis import (
    TransferAnalysisError,
    analyze_transfer_scenario,
)


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
                "Defender A",
                "Defender B",
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
                5.0,
                6.0,
                8.0,
            ],
            "predicted_points": [
                5.0,
                3.0,
                5.0,
                8.0,
                10.0,
            ],
        }
    )


def test_transfer_scenario_returns_sell_and_buy():
    result = analyze_transfer_scenario(
        make_team(),
        make_predictions(),
        player_out_id=2,
    )

    assert result["player_out_id"] == 2
    assert result["recommended_player_id"] == 4


def test_transfer_scenario_includes_expected_gain():
    result = analyze_transfer_scenario(
        make_team(),
        make_predictions(),
        player_out_id=2,
    )

    assert result["predicted_gain"] == pytest.approx(5.0)


def test_transfer_scenario_includes_reason():
    result = analyze_transfer_scenario(
        make_team(),
        make_predictions(),
        player_out_id=2,
    )

    assert isinstance(result["reason"], str)
    assert len(result["reason"]) > 0


def test_transfer_scenario_includes_alternatives():
    result = analyze_transfer_scenario(
        make_team(),
        make_predictions(),
        player_out_id=2,
    )

    assert "alternatives" in result
    assert len(result["alternatives"]) >= 1


def test_transfer_scenario_respects_budget():
    result = analyze_transfer_scenario(
        make_team(),
        make_predictions(),
        player_out_id=2,
        budget=5.0,
    )

    assert result["recommended_player_id"] == 3


def test_transfer_scenario_requires_player_out():
    with pytest.raises(TransferAnalysisError):
        analyze_transfer_scenario(
            make_team(),
            make_predictions(),
        )