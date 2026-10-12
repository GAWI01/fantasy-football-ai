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


def _rental_frames():
    market = [(101, "One week", "MID", "C16", 4.5, 0.0),
              (102, "Long run", "MID", "C17", 4.5, 8.0)]
    return [_frame([(pid, name, pos, club, price, 12.0 if pid == 101 and week == 0 else pts)
                    for pid, name, pos, club, price, pts in SQUAD + market])
            for week in range(5)]


def test_presented_follow_up_starts_from_recommended_current_squad():
    result = plan_action(_rental_frames(), owned_ids=OWNED, sale_info=SALE, bank=0.0,
                         free_transfers=1, max_transfers=1, weights=WEIGHTS)
    chosen = result["chosen"]
    sequence = next(item for item in result["two_week"]["sequences"]
                    if item["transfers_now"] == chosen["transfers_used"])
    assert {(m["player_out_id"], m["player_in_id"]) for m in sequence["moves_now"]} == {
        (m["player_out_id"], m["player_in_id"]) for m in chosen["transfers"]}
    assert all(move["player_out_id"] in chosen["squad"] for move in sequence["moves_next"])
    assert sequence["recommended"] is True
    assert result["two_week"]["recommended_transfers_now"] == chosen["transfers_used"]


def test_projected_points_are_unweighted_and_keep_distinct_gameweeks():
    import pytest
    from optimizer.action_planner import evaluate_moves
    frames = _rental_frames()
    result = evaluate_moves(frames, owned_ids=OWNED, sale_info=SALE, bank=0.0,
                            free_transfers=0, sell=[12], buy=[101], weights=WEIGHTS)
    # Independently evaluate this exact squad in each individual Gameweek.
    gains = [evaluate_moves([frame], owned_ids=OWNED, sale_info=SALE, bank=0.0,
                            free_transfers=0, sell=[12], buy=[101])["option"]["gross_gain"]
             for frame in frames]
    option = result["option"]
    assert gains[0] != gains[1]
    assert option["gross_gain"] == pytest.approx(sum(w * gain for w, gain in zip(WEIGHTS, gains)))
    assert option["projected_gain"] == pytest.approx(sum(gains))
    assert option["projected_net_gain"] == pytest.approx(sum(gains) - 4)


def test_two_stage_search_failure_is_reported_and_cannot_change_action(monkeypatch):
    from types import SimpleNamespace
    import optimizer.two_week as two_week
    monkeypatch.setattr(two_week, "milp", lambda **kwargs: SimpleNamespace(success=False, x=None, status=1))
    result = plan_action(_rental_frames(), owned_ids=OWNED, sale_info=SALE, bank=0.0,
                         free_transfers=1, max_transfers=1, weights=WEIGHTS)
    assert result["chosen"]["transfers_used"] == 1
    assert result["optimality_known"] is False
    assert result["two_week"]["optimality_known"] is False
    assert result["two_week"]["solver_status"] == "time_limit"
    assert result["two_week"]["sequences"] == []


def test_stage2_repurchase_uses_market_price_after_owned_player_was_sold():
    from optimizer.action_planner import DecisionPolicy, _Problem
    from optimizer.two_week import solve_two_stage
    rows = [(pid, name, pos, club, 5.0, 30.0 if pos == "MID" else pts) for pid, name, pos, club, _, pts in SQUAD]
    market = [(101, "Rental", "MID", "C16", 5.0, 0.0),
              (102, "Future keeper", "GK", "C17", 6.0, 0.0)]
    frames = [_frame([(pid, name, pos, club, price,
                       (100.0 if week == 0 else 0.0) if pid == 101 else
                       (0.0 if week == 0 else 100.0) if pid == 12 else
                       (0.0 if week == 0 else 200.0) if pid == 102 else pts)
                      for pid, name, pos, club, price, pts in rows + market]) for week in range(2)]
    sales = {pid: 3.0 if pid == 12 else 5.0 for pid in OWNED}
    policy = DecisionPolicy()
    # With £2m bank the initial rental is affordable, but selling it next
    # week and buying back the old player costs market price, not £3m.
    problem = _Problem(frames, [1.0, 1.0], set(OWNED), sales, 2.0, policy)
    plan = solve_two_stage(problem, stage1_count=1, free_transfers=1, policy=policy,
                           max_stage2_transfers=2)
    now, later = set(plan["squad_now"]), set(plan["squad_next"])
    prices = dict(zip(problem.ids, problem.prices))
    bank_now = 2.0 + sum(sales[pid] for pid in set(OWNED) - now) - sum(prices[pid] for pid in now - set(OWNED))
    bank_next = bank_now + sum(sales[pid] if pid in OWNED else prices[pid] for pid in now - later) - sum(prices[pid] for pid in later - now)
    assert bank_next >= -1e-6


def test_sequence_point_gains_and_score_components_use_hold_then_optimize_baseline():
    import pytest
    from optimizer.action_planner import DecisionPolicy, _Problem
    frames = _rental_frames()
    result = plan_action(frames, owned_ids=OWNED, sale_info=SALE, bank=0.0,
                         free_transfers=0, max_transfers=2, weights=WEIGHTS)
    view = result["two_week"]
    assert view["horizon"] == len(frames)
    assert view["weights"] == list(WEIGHTS)
    assert view["baseline"] == "hold_now_then_optimize"
    assert view["selection_policy"] == "conservative"
    problem = _Problem(frames, WEIGHTS, set(OWNED), {pid: info[0] for pid, info in SALE.items()}, 0.0, DecisionPolicy())
    sequence_values = []
    for sequence in view["sequences"]:
        now = set(OWNED)
        for move in sequence["moves_now"]:
            now.remove(move["player_out_id"])
            now.add(move["player_in_id"])
        later = set(now)
        for move in sequence["moves_next"]:
            later.remove(move["player_out_id"])
            later.add(move["player_in_id"])
        values = []
        for week in range(len(frames)):
            squad = now if week == 0 else later
            count = len(squad - set(OWNED))
            status, solved = problem.solve(newcomers_low=count, newcomers_high=count, required=list(squad))
            assert status == "optimal"
            values.append(solved.gameweek_values[week])
        sequence_values.append(values)
    baseline = view["sequences"][0]
    assert baseline["moves_next"]  # Baseline is allowed to improve next week.
    for sequence, values in zip(view["sequences"], sequence_values):
        unweighted = sum(values) - sum(sequence_values[0])
        weighted = sum(w * (v - b) for w, v, b in zip(WEIGHTS, values, sequence_values[0]))
        hits = sequence["hits_now"] + sequence["hits_next"]
        assert sequence["projected_gain"] == pytest.approx(unweighted, abs=0.001)
        assert sequence["hit_cost"] == 4 * hits
        assert sequence["risk_margin"] == 2 * hits
        assert sequence["projected_net_gain"] == pytest.approx(unweighted - sequence["hit_cost"] + baseline["hit_cost"], abs=0.001)
        assert sequence["weighted_gain_vs_hold"] == pytest.approx(weighted, abs=0.001)
        expected_score = (weighted - sequence["hit_cost"] + baseline["hit_cost"]
                          - sequence["risk_margin"] + baseline["risk_margin"]
                          + sequence["roll_value"] - baseline["roll_value"])
        assert sequence["score_vs_hold"] == pytest.approx(expected_score, abs=0.001)


def test_alternative_search_timeout_is_not_reported_complete(monkeypatch):
    from optimizer.action_planner import _Problem
    original = _Problem.solve

    def solve(self, **kwargs):
        if kwargs.get("banned"):
            return "time_limit", None
        return original(self, **kwargs)

    monkeypatch.setattr(_Problem, "solve", solve)
    result = plan_action(_rental_frames(), owned_ids=OWNED, sale_info=SALE, bank=0.0,
                         free_transfers=1, max_transfers=1, weights=WEIGHTS)
    assert result["chosen"]["transfers_used"] == 1
    assert result["optimality_known"] is True
    assert result["alternatives_complete"] is False


def test_solver_errors_are_not_reported_as_optimal(monkeypatch):
    from optimizer.action_planner import _Problem
    original = _Problem.solve

    def solve(self, **kwargs):
        if kwargs["newcomers_high"] > 0:
            return "solver_error", None
        return original(self, **kwargs)

    monkeypatch.setattr(_Problem, "solve", solve)
    result = plan_action(_rental_frames(), owned_ids=OWNED, sale_info=SALE, bank=0.0,
                         free_transfers=1, max_transfers=1, weights=WEIGHTS)
    assert result["optimality_known"] is False
    assert result["alternatives_complete"] is False
    assert result["solver_status"] == "solver_error"


def test_engine_preserves_projected_point_fields_for_chosen_and_alternatives():
    from engine.transfer_analysis import optimize_transfer_plan
    from tests.test_decision_scenarios import _team
    frames = _rental_frames()
    result = optimize_transfer_plan(_team(), frames[0], free_transfers=1, max_transfers=1,
                                    horizon_predictions=frames, horizon_weights=WEIGHTS)
    chosen = next(option for option in result["options_by_transfer_count"]
                  if option["transfers_used"] == result["transfers_used"])
    assert result["projected_gain"] == chosen["projected_gain"]
    assert result["projected_net_gain"] == chosen["projected_net_gain"]
    assert result["projected_gain"] != result["gross_gain"]
    assert all("projected_net_gain" in option for option in result["alternatives"])


def test_missing_two_stage_baseline_never_claims_optimal_or_complete(monkeypatch):
    from types import SimpleNamespace
    import optimizer.two_week as two_week
    monkeypatch.setattr(two_week, "milp", lambda **kwargs: SimpleNamespace(success=False, x=None, status=2))
    result = plan_action(_rental_frames(), owned_ids=OWNED, sale_info=SALE, bank=0.0,
                         free_transfers=1, max_transfers=1, weights=WEIGHTS)
    assert result["two_week"]["solver_status"] == "infeasible"
    assert result["two_week"]["optimality_known"] is False
    assert result["optimality_known"] is False
    assert result["alternatives_complete"] is False
