import pandas as pd

from engine.transfer_analysis import analyze_transfer_out


def make_team():
    return {
        "name": "Test Team",
        "picks": [
            {"player_id": 1, "position": 1, "multiplier": 1},
            {"player_id": 2, "position": 2, "multiplier": 1},
            {"player_id": 3, "position": 3, "multiplier": 1},
        ],
    }


def make_predictions():
    return pd.DataFrame(
        {
            "player_id": [1, 2, 3],
            "name": ["Player A", "Player B", "Player C"],
            "position": ["GK", "DEF", "MID"],
            "price": [5.0, 5.0, 10.0],
            "predicted_points": [4.0, 3.0, 8.0],
        }
    )


def test_analyze_transfer_out_returns_players():
    result = analyze_transfer_out(
        make_team(),
        make_predictions(),
    )

    assert len(result) == 3
    assert set(result["player_id"]) == {1, 2, 3}


def test_analyze_transfer_out_contains_value_columns():
    result = analyze_transfer_out(
        make_team(),
        make_predictions(),
    )

    assert "points_per_million" in result.columns
    assert "transfer_score" in result.columns
    assert "recommendation" in result.columns


def test_points_per_million_is_calculated():
    result = analyze_transfer_out(
        make_team(),
        make_predictions(),
    )

    player_a = result[
        result["player_id"] == 1
    ].iloc[0]

    assert player_a["points_per_million"] == 0.8


def test_weak_player_gets_higher_transfer_score():
    result = analyze_transfer_out(
        make_team(),
        make_predictions(),
    )

    player_b = result[
        result["player_id"] == 2
    ].iloc[0]

    player_c = result[
        result["player_id"] == 3
    ].iloc[0]

    assert player_b["transfer_score"] > player_c["transfer_score"]


def test_transfer_out_recommendation_exists():
    result = analyze_transfer_out(
        make_team(),
        make_predictions(),
    )

    assert set(result["recommendation"]).issubset(
        {"KEEP", "TRANSFER OUT"}
    )


def test_empty_team_returns_empty_dataframe():
    result = analyze_transfer_out(
        {"name": "Empty Team", "picks": []},
        make_predictions(),
    )

    assert result.empty


def test_missing_prediction_columns_raise_error():
    predictions = pd.DataFrame(
        {
            "player_id": [1],
            "name": ["Player A"],
        }
    )

    try:
        analyze_transfer_out(
            make_team(),
            predictions,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError"
        )