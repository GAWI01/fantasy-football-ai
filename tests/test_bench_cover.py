"""A doubtful starter is covered by the bench in the action planner."""
import pytest

from optimizer.action_planner import DEFAULT_POLICY, _Problem, _solve_hold, plan_action
from tests.test_decision_scenarios import SQUAD, _frame


def _problem(chance_mid_d):
    frame = _frame(SQUAD)
    frame["availability_multiplier"] = 1.0
    if chance_mid_d is not None:
        # Mid D: 8 points if he plays, 50% chance, so 4.0 expected (as SQUAD has).
        frame.loc[frame["player_id"] == 11, "availability_multiplier"] = chance_mid_d
    else:
        frame = frame.drop(columns="availability_multiplier")
    owned = {row[0] for row in SQUAD}
    sale = {row[0]: row[4] for row in SQUAD}
    return _Problem([frame], [1.0], owned, sale, 0.0, DEFAULT_POLICY)


def test_doubtful_starter_adds_his_chance_of_missing_times_the_best_substitute():
    _, plain = _solve_hold(_problem(None))
    _, covered = _solve_hold(_problem(0.5))

    assert covered.starters == plain.starters
    assert 11 in covered.starters[0]
    # Best outfield bench player: Def D, 3.0 points. Half the time he comes on.
    assert covered.value - plain.value == pytest.approx(0.5 * 3.0)


def test_a_fully_fit_squad_is_valued_as_before():
    _, plain = _solve_hold(_problem(None))
    _, fit = _solve_hold(_problem(1.0))
    assert fit.value == pytest.approx(plain.value)


def _best_single_transfer(with_availability):
    # Mid A: 5.5 when fit, 75% chance this week. A fit 4.4-point midfielder is
    # on offer for the same price.
    market = [(101, "Fit Mid", "MID", "C16", 8.0, 4.4)]
    frame = _frame(SQUAD + market)
    frame.loc[frame["player_id"] == 8, "predicted_points"] = 5.5 * 0.75
    if with_availability:
        frame["availability_multiplier"] = 1.0
        frame.loc[frame["player_id"] == 8, "availability_multiplier"] = 0.75
    owned = [row[0] for row in SQUAD]
    sale_info = {row[0]: (row[4], "market", False) for row in SQUAD}
    plan = plan_action([frame], owned_ids=owned, sale_info=sale_info, bank=0.0,
                       free_transfers=1, max_transfers=1)
    return next(item for item in plan["options_by_transfer_count"] if item["transfers_used"] == 1)


def test_cover_keeps_a_doubtful_starter_instead_of_a_marginal_swap():
    # Without cover, selling Mid A for the fit midfielder looks like +0.275.
    # (It is the only affordable swap, so it is the one-transfer option.)
    plain = _best_single_transfer(False)
    assert [(m["player_out_id"], m["player_in_id"]) for m in plain["transfers"]] == [(8, 101)]
    assert plain["gross_gain"] > 0
    # With a 3-point substitute covering his 25% chance of missing, Mid A is
    # worth 4.125 + 0.75 = 4.875, so the same swap loses points.
    covered = _best_single_transfer(True)
    assert covered["gross_gain"] < 0
