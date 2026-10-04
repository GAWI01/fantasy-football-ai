
import pandas as pd
import pytest

from decision_engine import build_decision


def make_predictions():
    rows = [
        {"player_id": 1, "name": "GK1", "position": "GK", "team": "A", "price": 5.0, "predicted_points": 4.0},
        {"player_id": 2, "name": "GK2", "position": "GK", "team": "B", "price": 4.0, "predicted_points": 3.0},
        {"player_id": 3, "name": "D1", "position": "DEF", "team": "A", "price": 5.0, "predicted_points": 5.0},
        {"player_id": 4, "name": "D2", "position": "DEF", "team": "B", "price": 5.0, "predicted_points": 4.0},
        {"player_id": 5, "name": "D3", "position": "DEF", "team": "C", "price": 5.0, "predicted_points": 4.0},
        {"player_id": 6, "name": "D4", "position": "DEF", "team": "D", "price": 5.0, "predicted_points": 3.0},
        {"player_id": 7, "name": "D5", "position": "DEF", "team": "E", "price": 3.0, "predicted_points": 3.0},
        {"player_id": 8, "name": "M1", "position": "MID", "team": "A", "price": 8.0, "predicted_points": 6.0},
        {"player_id": 9, "name": "M2", "position": "MID", "team": "B", "price": 7.0, "predicted_points": 5.0},
        {"player_id": 10, "name": "M3", "position": "MID", "team": "C", "price": 7.0, "predicted_points": 5.0},
        {"player_id": 11, "name": "M4", "position": "MID", "team": "D", "price": 6.0, "predicted_points": 4.0},
        {"player_id": 12, "name": "M5", "position": "MID", "team": "E", "price": 5.0, "predicted_points": 3.0},
        {"player_id": 13, "name": "F1", "position": "FWD", "team": "F", "price": 8.0, "predicted_points": 6.0},
        {"player_id": 14, "name": "F2", "position": "FWD", "team": "G", "price": 7.0, "predicted_points": 5.0},
        {"player_id": 15, "name": "F3", "position": "FWD", "team": "H", "price": 6.0, "predicted_points": 4.0},
        {"player_id": 16, "name": "EliteMid", "position": "MID", "team": "I", "price": 8.0, "predicted_points": 9.0},
        {"player_id": 17, "name": "AltMid", "position": "MID", "team": "J", "price": 7.0, "predicted_points": 7.0},
    ]
    return pd.DataFrame(rows)


def make_team():
    return {
        "id": 123,
        "name": "Test FC",
        "bank": 0.0,
        "value": 1000.0,
        "picks": [{"player_id": i} for i in range(1, 16)],
    }


def test_build_decision_contains_complete_decision_sections():
    result = build_decision(
        make_team(),
        make_predictions(),
        budget=100.0,
        free_transfers=1,
        max_transfers=1,
    )

    assert set(result) >= {
        "current_team",
        "optimal_squad",
        "starting_xi",
        "bench",
        "captain",
        "vice_captain",
        "transfers",
    }

    assert len(result["optimal_squad"]["players"]) == 15
    assert len(result["starting_xi"]["players"]) == 11
    assert len(result["bench"]["players"]) == 4
    assert result["captain"]["player_id"] != result["vice_captain"]["player_id"]


def test_lineup_and_captains_are_selected_only_from_the_owned_squad():
    result = build_decision(
        make_team(),
        make_predictions(),
        budget=100.0,
        free_transfers=1,
        max_transfers=1,
    )

    owned = set(range(1, 16))
    assert {player["player_id"] for player in result["starting_xi"]["players"]} <= owned
    assert {player["player_id"] for player in result["bench"]["players"]} <= owned
    assert result["captain"]["player_id"] in owned
    assert result["vice_captain"]["player_id"] in owned
    assert 16 not in {player["player_id"] for player in result["starting_xi"]["players"]}


def test_decision_uses_transfer_optimizer_and_preserves_post_transfer_squad():
    result = build_decision(
        make_team(),
        make_predictions(),
        budget=100.0,
        free_transfers=1,
        max_transfers=1,
    )

    assert result["transfers"]["transfers_used"] == 1
    assert result["transfers"]["recommended"]["player_in_id"] == 16
    assert len(result["transfers"]["post_transfer_squad"]) == 15


def test_decision_is_deterministic():
    first = build_decision(make_team(), make_predictions(), budget=100.0)
    second = build_decision(make_team(), make_predictions(), budget=100.0)

    assert first == second


def test_invalid_squad_is_rejected():
    bad = make_team()
    bad["picks"] = [{"player_id": 1}]

    with pytest.raises(ValueError):
        build_decision(bad, make_predictions())


def test_decision_accepts_public_team_with_missing_bank():
    team = make_team()
    team["bank"] = None
    result = build_decision(
        team,
        make_predictions(),
        budget=100.0,
        free_transfers=1,
        max_transfers=1,
    )
    assert result["current_team"]["bank"] == 0.0
    assert "transfers" in result


def test_decision_preserves_public_team_id():
    team = make_team()
    team.pop("id")
    team["team_id"] = 123

    result = build_decision(team, make_predictions(), budget=100.0)

    assert result["current_team"]["team_id"] == 123


def test_decision_captain_keeps_explanation_fields():
    values = make_predictions()
    values["xmins"] = 90.0
    values["start_probability"] = 1.0
    values["availability"] = "AVAILABLE"
    values["difficulty"] = 3.0

    result = build_decision(make_team(), values, budget=100.0)

    assert result["captain"]["team"]
    assert result["captain"]["xmins"] == 90.0
    assert result["captain"]["start_probability"] == 1.0


def test_chip_budget_preserves_supplied_owned_selling_values():
    team = make_team()
    team["bank"] = 3.0
    team["picks"] = [{"player_id": i, "selling_price": 4.0} for i in range(1, 16)]
    result = build_decision(team, make_predictions(), chip_state={"wildcard_available": True})
    scenarios = result["intelligence"]["chip_scenarios"]
    assert scenarios["budget"] == 63.0
    assert scenarios["selling_prices_known"] is True


def test_chip_captain_matches_the_owned_captain_recommendation():
    values = make_predictions()
    values["start_probability"] = 1.0
    values["availability"] = "AVAILABLE"
    values.loc[values.player_id == 8, ["predicted_points", "start_probability", "availability"]] = [10.0, 0.2, "RISK"]
    values.loc[values.player_id == 9, "predicted_points"] = 8.0
    result = build_decision(make_team(), values, chip_state={"triple_captain_available": True, "double_gameweek": True})
    assert result["captain"]["player_id"] == 9
    assert result["intelligence"]["chip_scenarios"]["scenarios"][0]["score"] == 8.0


def test_chip_gains_use_the_recommended_owned_lineup_not_last_gameweeks_picks():
    values = make_predictions()
    values.loc[values.player_id == 8, "predicted_points"] = 10.0
    team = make_team()
    # The published picks are the previous Gameweek's lineup: M1 benched, F1 captain.
    lineup_order = [1, 3, 4, 5, 6, 7, 9, 10, 13, 14, 15, 8, 11, 12, 2]
    team["picks"] = [{"player_id": player_id, "position": position, "is_captain": player_id == 13}
                     for position, player_id in enumerate(lineup_order, start=1)]
    result = build_decision(team, values, chip_state={"bench_boost_available": True, "triple_captain_available": True, "double_gameweek": True})
    assert result["captain"]["player_id"] == 8
    scenarios = result["intelligence"]["chip_scenarios"]
    # Recommended XI scores 56 with M1 (10) as captain; its bench is 3+3+3+3.
    assert {s["chip"]: s["score"] for s in scenarios["scenarios"]} == {"BENCH_BOOST": 12.0, "TRIPLE_CAPTAIN": 10.0}
    assert scenarios["baseline_value"] == 66.0
    assert scenarios["lineup_source"] == "recommended_owned_lineup"
