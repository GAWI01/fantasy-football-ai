"""The best Free Hit and Wildcard squads."""
from collections import Counter

from optimizer.action_planner import build_chip_squads
from tests.test_decision_scenarios import SQUAD, WEIGHTS, _frame

# A midfielder who is brilliant next week only (say a double Gameweek), and
# one who is steadily good for five weeks. Same price as Mid A.
ONE_WEEK = (201, "One Week", "MID", "C20", 8.0, 9.0)
STEADY = (202, "Steady", "MID", "C21", 8.0, 6.5)


def _frames():
    frames = []
    for week in range(5):
        rows = SQUAD + [STEADY, ONE_WEEK if week == 0 else (*ONE_WEEK[:5], 1.0)]
        frames.append(_frame(rows))
    return frames


def _squads():
    owned = [row[0] for row in SQUAD]
    sale_info = {row[0]: (row[4], "market", False) for row in SQUAD}
    return build_chip_squads(_frames(), owned_ids=owned, sale_info=sale_info, bank=0.0, weights=WEIGHTS)


def test_both_squads_are_legal_and_affordable():
    for chip, squad in _squads().items():
        assert squad["available"], chip
        players = squad["players"]
        assert len(players) == 15
        assert Counter(p["position"] for p in players) == {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
        assert max(Counter(p["team"] for p in players).values()) <= 3
        assert squad["cost"] <= squad["budget"] + 1e-6
        assert len(squad["starting_xi_ids"]) == 11 and len(squad["bench_ids"]) == 4
        assert squad["captain_id"] in squad["starting_xi_ids"]
        assert squad["vice_captain_id"] in squad["starting_xi_ids"] and squad["vice_captain_id"] != squad["captain_id"]
        assert squad["gain"] >= 0


def test_free_hit_plays_for_one_week_and_wildcard_for_five():
    squads = _squads()
    # The Free Hit only cares about next week, so it takes the one-week star...
    assert 201 in squads["free_hit"]["players_in"]
    # ...and captains him; the Wildcard keeps its squad, so it takes the steady one.
    assert squads["free_hit"]["captain_id"] == 201
    assert 202 in squads["wildcard"]["players_in"]
    assert 201 not in squads["wildcard"]["players_in"]
    assert squads["free_hit"]["projected_points"] > squads["free_hit"]["current_projected_points"]


def _wildcard_with(bonus, steady_points=6.5):
    owned = [row[0] for row in SQUAD]
    sale_info = {row[0]: (row[4], "market", False) for row in SQUAD}
    twin = (203, "Twin", "MID", "C22", 8.0, steady_points)
    frames = [_frame(SQUAD + [(*STEADY[:5], steady_points), twin]) for _ in range(5)]
    return build_chip_squads(frames, owned_ids=owned, sale_info=sale_info, bank=0.0,
                             weights=WEIGHTS, wildcard_bonus=bonus)["wildcard"]


def test_a_likely_riser_wins_between_equal_players():
    # Steady and Twin are identical; Twin is likely to rise in price.
    squad = _wildcard_with({203: 0.4})
    assert 203 in squad["players_in"] and 202 not in squad["players_in"]
    # The nudge never shows up in the reported numbers.
    assert squad["gain"] == _wildcard_with(None)["gain"]


def test_the_nudge_never_trades_real_points_for_price():
    # Twin is likely to rise but projects a point less per week: points win.
    owned = [row[0] for row in SQUAD]
    sale_info = {row[0]: (row[4], "market", False) for row in SQUAD}
    frames = [_frame(SQUAD + [STEADY, (203, "Twin", "MID", "C22", 8.0, 5.5)]) for _ in range(5)]
    squad = build_chip_squads(frames, owned_ids=owned, sale_info=sale_info, bank=0.0,
                              weights=WEIGHTS, wildcard_bonus={203: 0.4})["wildcard"]
    assert 202 in squad["players_in"] and 203 not in squad["players_in"]


def test_price_nudges_never_touch_the_free_hit():
    owned = [row[0] for row in SQUAD]
    sale_info = {row[0]: (row[4], "market", False) for row in SQUAD}
    frames = _frames()
    plain = build_chip_squads(frames, owned_ids=owned, sale_info=sale_info, bank=0.0, weights=WEIGHTS)
    nudged = build_chip_squads(frames, owned_ids=owned, sale_info=sale_info, bank=0.0, weights=WEIGHTS,
                               wildcard_bonus={202: 5.0})
    assert nudged["free_hit"]["players"] == plain["free_hit"]["players"]
