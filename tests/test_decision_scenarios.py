"""Decision-policy regression scenarios (audit 2026-10-11, scenarios A-G).

Each scenario is a small, hand-checkable world: a 15-player squad, a market
and per-Gameweek projections. They pin the policy, not a model: holding is a
real action, the bench does not score like the XI, free transfers are not
spent automatically, availability is Gameweek-specific and a chip is not
recommended because it exists.
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.planning_service import build_fixture_scaled_horizon
from decision_engine import build_decision
from transfer_analysis import optimize_transfer_plan

WEIGHTS = (1.0, 0.85, 0.7, 0.55, 0.4)
SQUAD = [
    # id, name, position, club, price, points per Gameweek
    (1, "Keeper", "GK", "C1", 5.0, 4.5),
    (2, "Reserve", "GK", "C2", 4.0, 0.1),  # never plays: 0 expected minutes
    (3, "Def A", "DEF", "C3", 5.0, 4.0),
    (4, "Def B", "DEF", "C4", 5.0, 4.0),
    (5, "Def C", "DEF", "C5", 5.0, 4.0),
    (6, "Def D", "DEF", "C6", 4.5, 3.0),
    (7, "Def E", "DEF", "C7", 4.0, 2.0),
    (8, "Mid A", "MID", "C8", 8.0, 5.5),
    (9, "Mid B", "MID", "C9", 7.0, 5.0),
    (10, "Mid C", "MID", "C10", 6.0, 4.5),
    (11, "Mid D", "MID", "C11", 5.5, 4.0),
    (12, "Mid E", "MID", "C12", 4.5, 2.5),
    (13, "Fwd A", "FWD", "C13", 9.0, 6.0),
    (14, "Fwd B", "FWD", "C14", 7.0, 4.5),
    (15, "Fwd C", "FWD", "C15", 6.0, 4.0),
]


def _frame(rows):
    return pd.DataFrame([
        {"player_id": pid, "name": name, "position": pos, "team": club, "price": price,
         "predicted_points": points, "uncertainty": max(0.8, points * 0.2)}
        for pid, name, pos, club, price, points in rows
    ])


def _team(bank=0.0):
    return {"team_id": 1, "name": "Scenario FC", "bank": bank, "picks": [{"player_id": row[0]} for row in SQUAD]}


def _plan(market, *, free_transfers=1, bank=0.0, weeks=5, overrides=None):
    """Plan over `weeks` identical Gameweeks unless `overrides[(pid, week)]` says otherwise."""
    rows = SQUAD + market
    frames = []
    for week in range(weeks):
        week_rows = [
            (pid, name, pos, club, price, (overrides or {}).get((pid, week), points))
            for pid, name, pos, club, price, points in rows
        ]
        frames.append(_frame(week_rows))
    return optimize_transfer_plan(
        _team(bank), frames[0], free_transfers=free_transfers, max_transfers=free_transfers + 2,
        horizon_predictions=frames, horizon_weights=WEIGHTS[:weeks],
    )


def _moves(result):
    return {(m["player_out_id"], m["player_in_id"]) for m in result["recommended_transfers"]}


def test_scenario_a_strong_squad_holds_and_rolls():
    # Every market option is at most a fractional upgrade.
    market = [
        (101, "Alt Mid", "MID", "C16", 4.5, 2.7),
        (102, "Alt Def", "DEF", "C17", 4.0, 2.1),
        (103, "Alt Fwd", "FWD", "C18", 6.0, 4.1),
    ]
    result = _plan(market)
    assert result["action"] == "HOLD"
    assert result["transfers_used"] == 0
    # The best move is still reported, with the reason it was not taken.
    best_move = result["options_by_transfer_count"][1]
    assert 0 < best_move["gross_gain"] < best_move["roll_value_forgone"]


def test_scenario_b_injured_starter_is_replaced():
    market = [(101, "Fit Mid", "MID", "C16", 8.0, 5.0)]
    # Mid A is out for the whole horizon (e.g. left the club).
    injured = {(8, week): 0.0 for week in range(5)}
    result = _plan(market, overrides=injured)
    assert result["action"] == "SINGLE_TRANSFER"
    assert _moves(result) == {(8, 101)}


def test_scenario_c_one_match_suspension_is_not_zero_for_the_horizon():
    teams = pd.DataFrame([{"id": 1, "name": "C8"}, {"id": 2, "name": "Opp"}])
    fixtures = pd.DataFrame([
        {"event": 7 + week, "team_h": 1, "team_a": 2, "team_h_difficulty": 3, "team_a_difficulty": 3,
         "kickoff_time": f"2026-10-{17 + 7 * week:02d}T14:00:00Z" if week < 3
         else f"2026-11-{17 + 7 * week - 31:02d}T14:00:00Z"}
        for week in range(5)
    ])
    suspended = pd.DataFrame([{
        "player_id": 8, "name": "Mid A", "position": "MID", "team": "C8", "price": 8.0,
        "ml_prediction": 5.5, "predicted_points": 0.0, "difficulty": 3, "home": True,
        "xmins_available": 88.0, "start_probability_available": 0.97,
        "status": "s", "chance_of_playing_next_round": 0, "news": "Suspended until 20 Oct",
    }])
    horizon = build_fixture_scaled_horizon(suspended, fixtures, teams, prediction_event=7, horizon=5)
    points = [float(horizon[step].iloc[0]["predicted_points"]) for step in range(1, 6)]
    assert points[0] == 0.0
    assert all(value > 5.0 for value in points[1:])

    # Out for one Gameweek only: a like-for-like replacement is not worth it.
    market = [(101, "Cover Mid", "MID", "C16", 8.0, 5.0)]
    result = _plan(market, overrides={(8, 0): 0.0})
    assert result["action"] == "HOLD"
    # Out for the whole horizon: replace him.
    result = _plan(market, overrides={(8, week): 0.0 for week in range(5)})
    assert _moves(result) == {(8, 101)}


def test_scenario_d_reserve_keeper_upgrade_is_not_valued_as_a_starter():
    market = [
        (101, "Star Keeper", "GK", "C16", 4.0, 6.0),   # better than our starter
        (102, "Spare Keeper", "GK", "C17", 4.0, 4.5),  # a playing reserve
    ]
    result = _plan(market)
    # Star Keeper replaces the starter's role, so the only sensible keeper
    # move sells the 0-minute reserve and benches the old starter: a real
    # gain of ~1.5 a week in the XI, not the 5.9 a bench sum would claim.
    reserve_swap = next(o for o in result["options_by_transfer_count"] if o["transfers_used"] == 1)
    assert reserve_swap["transfers"][0]["player_out_id"] == 2
    assert reserve_swap["transfers"][0]["player_in_id"] == 101
    assert reserve_swap["gross_gain"] < 6.0
    # A playing reserve keeper adds only autosub cover: hold.
    result = _plan([market[1]])
    assert result["action"] == "HOLD"
    assert result["options_by_transfer_count"][1]["gross_gain"] < 0.5


def test_scenario_d_weak_starter_beats_strong_reserve_keeper():
    market = [
        (101, "Spare Keeper", "GK", "C16", 4.0, 5.0),
        (102, "Better Def", "DEF", "C17", 5.0, 5.5),
    ]
    result = _plan(market, free_transfers=1, bank=1.0)
    assert _moves(result) == {(7, 102)}


def test_scenario_e_two_free_transfers_choose_zero_one_or_two():
    strong = (101, "Strong Mid", "MID", "C16", 4.5, 5.0)     # replaces Mid E (2.5)
    second = (102, "Strong Def", "DEF", "C17", 4.0, 4.5)     # replaces Def E (2.0)
    marginal = (103, "Marginal Def", "DEF", "C18", 4.0, 2.3)

    assert _plan([marginal], free_transfers=2)["transfers_used"] == 0
    one = _plan([strong, marginal], free_transfers=2)
    assert one["transfers_used"] == 1 and _moves(one) == {(12, 101)}
    two = _plan([strong, second], free_transfers=2)
    assert two["transfers_used"] == 2 and _moves(two) == {(12, 101), (7, 102)}


def test_scenario_f_three_free_transfers_are_not_all_spent():
    strong = (101, "Strong Mid", "MID", "C16", 4.5, 5.0)
    marginal = [
        (102, "Marginal Def", "DEF", "C17", 4.0, 2.3),
        (103, "Marginal Fwd", "FWD", "C18", 6.0, 4.2),
    ]
    result = _plan([strong, *marginal], free_transfers=3)
    assert result["transfers_used"] == 1
    assert result["free_transfers"] == 3


def test_scenario_f_hits_need_their_cost_plus_margin():
    strong = (101, "Strong Mid", "MID", "C16", 4.5, 5.0)
    decent = (102, "Decent Def", "DEF", "C17", 4.0, 3.0)  # +1.0 a week over Def E
    result = _plan([strong, decent], free_transfers=1)
    assert result["transfers_used"] == 1
    assert result["hit_cost"] == 0.0


def _decision_world():
    rows = SQUAD + [
        (101, "Alt Mid", "MID", "C16", 4.5, 2.6),
        (102, "Alt Def", "DEF", "C17", 4.0, 2.1),
    ]
    frame = _frame(rows).assign(xmins=85.0, start_probability=0.95, availability="AVAILABLE", difficulty=3)
    horizon = {step: frame.assign(gameweek=6 + step) for step in range(1, 6)}
    return frame, horizon


def test_scenario_g_available_wildcard_is_not_recommended_for_a_healthy_squad():
    frame, horizon = _decision_world()
    decision = build_decision(
        _team(), frame, free_transfers=1, max_transfers=3, horizon_predictions=horizon, horizon=5,
        chip_state={"known": True, "wildcard_available": True, "free_hit_available": True,
                    "bench_boost_available": True, "triple_captain_available": True,
                    "free_transfers": 1},
    )
    intelligence = decision["intelligence"]
    assert intelligence["wildcard_signal"]["evaluated"] is True
    assert intelligence["wildcard_signal"]["recommended"] is False
    assert intelligence["chip_advisor"]["recommended_chip"] is None
    assert intelligence["action"] == "HOLD"


def test_decision_response_names_one_canonical_transfer_plan():
    frame, horizon = _decision_world()
    frame.loc[frame.player_id == 101, "predicted_points"] = 6.0
    horizon = {step: frame.assign(gameweek=6 + step) for step in range(1, 6)}
    decision = build_decision(_team(), frame, free_transfers=1, max_transfers=3,
                              horizon_predictions=horizon, horizon=5)
    engine = [(m["player_out_id"], m["player_in_id"]) for m in decision["transfers"]["recommended_transfers"]]
    shown = [(m["player_out_id"], m["player_in_id"]) for m in decision["intelligence"]["transfer_strategy"]["selected_transfers"]]
    assert engine == shown == [(12, 101)]
    assert decision["intelligence"]["action"] == decision["transfers"]["action"] == "SINGLE_TRANSFER"
    strategy = decision["intelligence"]["transfer_strategy"]
    assert strategy["horizon_gain"] == pytest.approx(decision["transfers"]["gross_gain"])
    assert strategy["decision_score"] == pytest.approx(decision["transfers"]["decision_score"])


def test_horizon_gain_is_counted_once_with_hand_computed_values():
    # Holding, Mid E (2.5) is on the bench; the XI's weakest starters are
    # 4.0s. New Mid (4.5) replaces Mid E: +0.5 in the XI (over a 4.0) and the
    # displaced 4.0 joins the bench instead of 2.5: +0.1 x 1.5 = +0.15.
    # +0.65 a week, weighted 1 + .85 + .7 + .55 + .4 = 3.5 -> 2.275.
    market = [(101, "New Mid", "MID", "C16", 4.5, 4.5)]
    result = _plan(market)
    assert result["gross_gain"] == pytest.approx(2.275)
    assert result["next_gw_gain"] == pytest.approx(0.65)
    # Counted once: rolling (2.0) leaves a decision score of 0.275.
    assert result["decision_score"] == pytest.approx(0.275)
    assert result["action"] == "SINGLE_TRANSFER"


def test_unlimited_transfers_before_a_first_deadline_have_no_hits_or_roll_value():
    market = [(101, "New Mid", "MID", "C16", 4.5, 4.5), (102, "New Def", "DEF", "C17", 4.0, 3.5)]
    result = _plan(market, free_transfers=20)
    assert result["hit_cost"] == 0.0
    assert result["transfers_used"] == 2
    assert result["roll_value_forgone"] == 0.0
