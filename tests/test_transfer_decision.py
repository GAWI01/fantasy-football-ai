
import pandas as pd
import pytest

from transfer_analysis import analyze_transfer_decision


def predictions():
    return pd.DataFrame([
        # Current squad: 15 players
        {"player_id": 1, "name": "GK1", "position": "GK", "team": "A", "price": 5.0, "predicted_points": 4.0},
        {"player_id": 2, "name": "GK2", "position": "GK", "team": "B", "price": 4.0, "predicted_points": 3.0},
        {"player_id": 3, "name": "D1", "position": "DEF", "team": "A", "price": 5.0, "predicted_points": 5.0},
        {"player_id": 4, "name": "D2", "position": "B", "team": "B", "price": 5.0, "predicted_points": 4.0},
        {"player_id": 5, "name": "D3", "position": "C", "team": "C", "price": 5.0, "predicted_points": 4.0},
        {"player_id": 6, "name": "D4", "position": "D", "team": "D", "price": 5.0, "predicted_points": 3.0},
        {"player_id": 7, "name": "D5", "position": "DEF", "team": "E", "price": 5.0, "predicted_points": 3.0},
        {"player_id": 8, "name": "M1", "position": "MID", "team": "A", "price": 8.0, "predicted_points": 6.0},
        {"player_id": 9, "name": "M2", "position": "MID", "team": "B", "price": 7.0, "predicted_points": 5.0},
        {"player_id": 10, "name": "M3", "position": "MID", "team": "C", "price": 7.0, "predicted_points": 5.0},
        {"player_id": 11, "name": "M4", "position": "MID", "team": "D", "price": 6.0, "predicted_points": 4.0},
        {"player_id": 12, "name": "M5", "position": "MID", "team": "E", "price": 5.0, "predicted_points": 3.0},
        {"player_id": 13, "name": "F1", "position": "FWD", "team": "A", "price": 8.0, "predicted_points": 6.0},
        {"player_id": 14, "name": "F2", "position": "FWD", "team": "B", "price": 7.0, "predicted_points": 5.0},
        {"player_id": 15, "name": "F3", "position": "FWD", "team": "C", "price": 6.0, "predicted_points": 4.0},
        # Transfer target: same position, affordable, clearly better
        {"player_id": 16, "name": "NewMid", "position": "MID", "team": "F", "price": 8.0, "predicted_points": 8.0},
        {"player_id": 17, "name": "AltMid", "position": "MID", "team": "G", "price": 7.0, "predicted_points": 7.0},
    ])


def team():
    picks = [
        {"player_id": i} for i in range(1, 16)
    ]
    return {
        "id": 99,
        "name": "Test FC",
        "bank": 0.0,
        "value": 1000.0,
        "transfers": 1,
        "picks": picks,
    }


def test_decision_recommends_best_feasible_transfer_and_net_gain():
    result = analyze_transfer_decision(
        team(),
        predictions(),
        free_transfers=1,
        transfer_out_id=8,
    )

    assert result["recommended"]["player_out_id"] == 8
    assert result["recommended"]["player_in_id"] == 16
    assert result["gross_gain"] == pytest.approx(2.0)
    assert result["hit_cost"] == pytest.approx(0.0)
    assert result["net_gain"] == pytest.approx(2.0)


def test_extra_transfer_applies_four_point_hit():
    result = analyze_transfer_decision(
        team(),
        predictions(),
        free_transfers=0,
        transfer_out_id=8,
    )

    assert result["hit_cost"] == pytest.approx(4.0)
    assert result["net_gain"] == pytest.approx(-2.0)


def test_recommendation_is_not_allowed_to_exceed_bank():
    result = analyze_transfer_decision(
        team(),
        predictions(),
        free_transfers=1,
        transfer_out_id=8,
        bank=0.0,
    )

    assert result["recommended"]["player_in_id"] == 16


def test_invalid_current_team_is_rejected():
    bad_team = {"id": 99, "picks": [{"player_id": 1}]}

    with pytest.raises(ValueError):
        analyze_transfer_decision(
            bad_team,
            predictions(),
            free_transfers=1,
            transfer_out_id=8,
        )


def test_single_decision_uses_supplied_selling_value_for_affordability():
    manager = team()
    manager["picks"][7]["selling_price"] = 7.4
    result = analyze_transfer_decision(manager, predictions(), transfer_out_id=8)
    assert result["recommended"]["player_in_id"] == 17
    assert result["recommended"]["price"] <= result["recommended"]["selling_price"]
    assert result["recommended"]["selling_price_source"] == "provided_selling_price"


def test_single_decision_labels_market_price_as_an_estimate():
    result = analyze_transfer_decision(team(), predictions(), transfer_out_id=8)
    assert result["budget_is_estimate"] is True
    assert result["recommended"]["selling_price_source"] == "market_price_estimate"
