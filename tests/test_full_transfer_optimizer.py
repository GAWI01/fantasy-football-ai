
import pandas as pd
import pytest
from time import perf_counter

from transfer_analysis import optimize_transfer_plan
from types import SimpleNamespace


def make_predictions():
    rows = [
        # 15 current players
        {"player_id": 1, "name": "GK1", "position": "GK", "team": "A", "price": 5.0, "predicted_points": 4.0},
        {"player_id": 2, "name": "GK2", "position": "GK", "team": "B", "price": 4.0, "predicted_points": 3.0},
        {"player_id": 3, "name": "D1", "position": "DEF", "team": "A", "price": 5.0, "predicted_points": 5.0},
        {"player_id": 4, "name": "D2", "position": "DEF", "team": "B", "price": 5.0, "predicted_points": 4.0},
        {"player_id": 5, "name": "D3", "position": "DEF", "team": "C", "price": 5.0, "predicted_points": 4.0},
        {"player_id": 6, "name": "D4", "position": "DEF", "team": "D", "price": 5.0, "predicted_points": 3.0},
        {"player_id": 7, "name": "D5", "position": "DEF", "team": "E", "price": 5.0, "predicted_points": 3.0},
        {"player_id": 8, "name": "M1", "position": "MID", "team": "A", "price": 8.0, "predicted_points": 5.0},
        {"player_id": 9, "name": "M2", "position": "MID", "team": "B", "price": 7.0, "predicted_points": 5.0},
        {"player_id": 10, "name": "M3", "position": "MID", "team": "C", "price": 7.0, "predicted_points": 5.0},
        {"player_id": 11, "name": "M4", "position": "MID", "team": "D", "price": 6.0, "predicted_points": 4.0},
        {"player_id": 12, "name": "M5", "position": "MID", "team": "E", "price": 5.0, "predicted_points": 3.0},
        {"player_id": 13, "name": "F1", "position": "FWD", "team": "H", "price": 8.0, "predicted_points": 5.0},
        {"player_id": 14, "name": "F2", "position": "FWD", "team": "H", "price": 7.0, "predicted_points": 5.0},
        {"player_id": 15, "name": "F3", "position": "FWD", "price": 6.0, "predicted_points": 4.0},
        # Transfer targets
        {"player_id": 16, "name": "EliteMid", "position": "MID", "team": "F", "price": 8.0, "predicted_points": 9.0},
        {"player_id": 17, "name": "GoodMid", "position": "MID", "team": "G", "price": 7.0, "predicted_points": 7.0},
        {"player_id": 18, "name": "EliteFwd", "position": "FWD", "team": "H", "price": 8.0, "predicted_points": 8.0},
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


def test_best_single_transfer_is_selected():
    result = optimize_transfer_plan(
        make_team(),
        make_predictions(),
        free_transfers=1,
        max_transfers=1,
    )

    assert result["transfers_used"] == 1
    assert result["hit_cost"] == pytest.approx(0.0)
    assert result["recommended"]["player_in_id"] == 16
    assert result["gross_gain"] == pytest.approx(4.0)
    assert result["net_gain"] == pytest.approx(4.0)


def test_hit_is_applied_when_more_transfers_are_requested():
    result = optimize_transfer_plan(
        make_team(),
        make_predictions(),
        free_transfers=0,
        max_transfers=1,
    )

    assert result["hit_cost"] == pytest.approx(4.0)
    assert result["net_gain"] == pytest.approx(0.0)


def test_no_transfer_can_be_better_than_a_negative_move():
    predictions = make_predictions()
    predictions.loc[predictions["player_id"] == 16, "predicted_points"] = 4.5
    predictions.loc[predictions["player_id"] == 17, "predicted_points"] = 4.0
    predictions.loc[predictions["player_id"] == 18, "predicted_points"] = 4.0

    result = optimize_transfer_plan(
        make_team(),
        predictions,
        free_transfers=1,
        max_transfers=1,
    )

    assert result["transfers_used"] == 0
    assert result["net_gain"] == pytest.approx(0.0)


def test_multiple_transfers_are_considered_and_remain_legal():
    result = optimize_transfer_plan(
        make_team(),
        make_predictions(),
        free_transfers=2,
        max_transfers=2,
    )

    assert result["transfers_used"] == 2
    assert len(result["recommended_transfers"]) == 2
    assert len({x["player_in_id"] for x in result["recommended_transfers"]}) == 2
    assert result["net_gain"] > 4.0


def test_affordability_uses_official_selling_price_not_current_market_price():
    predictions = make_predictions()
    predictions.loc[predictions["player_id"] == 16, ["price", "predicted_points"]] = [7.8, 10.0]
    predictions.loc[predictions["player_id"] == 17, ["price", "predicted_points"]] = [7.5, 7.0]
    predictions.loc[predictions["player_id"] == 18, "predicted_points"] = 4.0
    team = make_team()
    team["picks"] = [
        {"player_id": player_id, **({"selling_price": 7.6} if player_id == 8 else {})}
        for player_id in range(1, 16)
    ]

    result = optimize_transfer_plan(
        team,
        predictions,
        free_transfers=1,
        max_transfers=1,
    )

    assert result["recommended"]["player_in_id"] == 17
    assert result["recommended"]["player_out_id"] == 8


def test_two_transfer_full_search_stays_within_interactive_latency_budget():
    predictions = make_predictions().iloc[:15].copy()
    rows = []
    player_id = 100
    for position in ("GK", "DEF", "MID", "FWD"):
        for index in range(12):
            rows.append({
                "player_id": player_id,
                "name": f"{position}{index}",
                "position": position,
                "team": f"X{index}",
                "price": 4.0,
                "predicted_points": 10.0 - index / 10,
            })
            player_id += 1
    predictions = pd.concat([predictions, pd.DataFrame(rows)], ignore_index=True)

    started = perf_counter()
    result = optimize_transfer_plan(
        make_team(),
        predictions,
        free_transfers=2,
        max_transfers=2,
    )
    duration = perf_counter() - started

    assert result["transfers_used"] == 2
    assert result["net_gain"] == pytest.approx(14.0)
    assert duration < 2.0, f"full two-transfer search took {duration:.2f}s"


def test_downgrade_can_fund_an_upgrade_unaffordable_on_its_own():
    predictions = make_predictions().iloc[:15].copy()
    predictions.loc[predictions.player_id == 8, ["price", "predicted_points"]] = [10.0, 8.0]
    predictions.loc[predictions.player_id == 13, ["price", "predicted_points"]] = [5.0, 1.0]
    targets = pd.DataFrame([
        {"player_id": 16, "name": "Funding", "position": "MID", "team": "X", "price": 5.0, "predicted_points": 7.0},
        {"player_id": 17, "name": "Upgrade", "position": "FWD", "team": "Y", "price": 10.0, "predicted_points": 12.0},
    ])
    result = optimize_transfer_plan(make_team(), pd.concat([predictions, targets]), free_transfers=2, max_transfers=2)
    assert {(x["player_out_id"], x["player_in_id"]) for x in result["recommended_transfers"]} == {(8, 16), (13, 17)}
    assert result["net_gain"] == pytest.approx(10.0)


def test_outgoing_from_full_club_frees_slot_for_paired_incoming():
    predictions = make_predictions().iloc[:15].copy()
    predictions.loc[predictions.player_id == 8, "predicted_points"] = 1.0
    targets = pd.DataFrame([
        {"player_id": 16, "name": "Release", "position": "MID", "team": "X", "price": 8.0, "predicted_points": 6.0},
        {"player_id": 17, "name": "ClubUpgrade", "position": "FWD", "team": "A", "price": 8.0, "predicted_points": 10.0},
    ])
    result = optimize_transfer_plan(make_team(), pd.concat([predictions, targets]), free_transfers=2, max_transfers=2)
    assert {(x["player_out_id"], x["player_in_id"]) for x in result["recommended_transfers"]} == {(8, 16), (13, 17)}
    assert result["net_gain"] == pytest.approx(10.0)


def test_market_price_fallback_is_exposed_as_estimated_selling_value():
    result = optimize_transfer_plan(make_team(), make_predictions())
    assert result["selling_prices_known"] is False
    assert result["recommended"]["selling_price_source"] == "market_price_estimate"


def test_five_transfer_search_handles_full_candidate_pool_within_seconds():
    predictions = make_predictions().iloc[:15].copy()
    targets = pd.DataFrame([
        {"player_id": 100 + group * 120 + index, "name": f"{pos}{index}", "position": pos,
         "team": f"T{index % 20}", "price": 4.0, "predicted_points": 20.0 - index / 100}
        for group, pos in enumerate(("GK", "DEF", "MID", "FWD")) for index in range(120)
    ])
    started = perf_counter()
    result = optimize_transfer_plan(make_team(), pd.concat([predictions, targets]), free_transfers=5, max_transfers=5)
    assert result["transfers_used"] == 5
    assert result["net_gain"] > 80
    assert perf_counter() - started < 5.0


def test_marked_market_estimate_does_not_become_a_verified_selling_price():
    team = make_team()
    team["picks"] = [{"player_id": i, "selling_price": 5.0, "selling_price_source": "market_price_estimate"} for i in range(1, 16)]
    result = optimize_transfer_plan(team, make_predictions())
    assert result["selling_prices_known"] is False
    assert result["recommended"]["selling_price_source"] == "market_price_estimate"


def test_solver_timeout_does_not_report_hold_as_a_proven_best_plan(monkeypatch):
    monkeypatch.setattr("transfer_analysis.milp", lambda **kwargs: SimpleNamespace(success=False, status=1, x=None))
    result = optimize_transfer_plan(make_team(), make_predictions())
    assert result["solver_status"] == "time_limit"
    assert result["optimality_known"] is False
    assert result["optimization_warning"]


def test_zero_transfer_request_still_exposes_unknown_selling_values():
    result = optimize_transfer_plan(make_team(), make_predictions(), max_transfers=0)
    assert result["budget_is_estimate"] is True
    assert result["selling_prices_known"] is False


def test_purchase_price_estimate_reserves_only_half_the_price_rise():
    predictions = make_predictions()
    predictions.loc[predictions.player_id == 8, "price"] = 8.7
    predictions.loc[predictions.player_id == 16, "price"] = 8.5
    predictions.loc[predictions.player_id == 17, "price"] = 8.3
    predictions.loc[predictions.player_id == 18, "predicted_points"] = 4.0
    team = make_team()
    team["picks"][7]["purchase_price"] = 8.0
    result = optimize_transfer_plan(team, predictions)
    transfer = result["recommended"]
    assert transfer["player_in_id"] == 17
    assert transfer["selling_price"] == 8.3
    assert transfer["price"] <= transfer["selling_price"] + team["bank"]
    assert transfer["selling_price_source"] == "purchase_price_estimate"
    assert result["budget_is_estimate"] is True


def test_owned_only_pool_does_not_duplicate_the_roll_alternative():
    result = optimize_transfer_plan(make_team(), make_predictions().iloc[:15].copy())
    assert result["transfers_used"] == 0
    assert result["alternatives"] == []
