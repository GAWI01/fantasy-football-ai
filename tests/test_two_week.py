"""Two-week planning: what to do now, given next week's free transfers."""
from optimizer.action_planner import plan_action
from optimizer.two_week import carried_free_transfers
from tests.test_decision_scenarios import SQUAD, WEIGHTS, _frame

OWNED = [row[0] for row in SQUAD]
SALE = {row[0]: (row[4], "market", False) for row in SQUAD}


def _plan(market, overrides=None, free_transfers=1):
    frames = []
    for week in range(5):
        rows = [(pid, name, pos, club, price, (overrides or {}).get((pid, week), pts))
                for pid, name, pos, club, price, pts in SQUAD + market]
        frames.append(_frame(rows))
    return plan_action(frames, owned_ids=OWNED, sale_info=SALE, bank=0.0, free_transfers=free_transfers,
                       max_transfers=free_transfers + 2, weights=WEIGHTS)


def test_free_transfers_carry_one_new_and_cap_at_five():
    assert carried_free_transfers(1, 0) == 2
    assert carried_free_transfers(1, 1) == 1
    assert carried_free_transfers(1, 2) == 1  # a hit leaves none, plus the new one
    assert carried_free_transfers(5, 0) == 5


def test_hold_now_when_two_starters_turn_bad_next_week():
    # Mid B and Mid C face a hard run from Gameweek 2. Moving one now gains
    # nothing this week; holding gives two free transfers to fix both next week.
    market = [(101, "New Mid1", "MID", "C16", 7.0, 5.0), (102, "New Mid2", "MID", "C17", 6.0, 4.5)]
    bad = {(pid, week): 1.0 for pid in (9, 10) for week in range(1, 5)}
    result = _plan(market, bad)
    assert result["action"] == "HOLD"
    hold = next(item for item in result["two_week"]["sequences"] if item["transfers_now"] == 0)
    assert {move["player_in_id"] for move in hold["moves_next"]} == {101, 102}
    assert hold["hits_next"] == 0


def test_a_second_upgrade_waits_a_week_instead_of_a_hit():
    market = [(101, "Star Mid", "MID", "C16", 7.0, 8.5), (102, "Star Fwd", "FWD", "C17", 7.0, 8.0)]
    result = _plan(market)
    assert result["chosen"]["transfers_used"] == 1
    assert result["chosen"]["hit_cost"] == 0
    sequences = {item["transfers_now"]: item for item in result["two_week"]["sequences"]}
    assert sequences[1]["score_vs_hold"] > sequences[2]["score_vs_hold"]
    assert sequences[1]["moves_next"] and sequences[1]["hits_next"] == 0


def test_a_strong_squad_still_holds():
    market = [(101, "Alt Mid", "MID", "C16", 4.5, 2.7), (102, "Alt Def", "DEF", "C17", 4.0, 2.1)]
    result = _plan(market)
    assert result["action"] == "HOLD"
    assert result["two_week"]["best_transfers_now"] == 0
