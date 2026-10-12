"""Two-week transfer planning: what to do now, given what you can do next week.

The single-step planner values a banked free transfer with a flat number
(`DecisionPolicy.roll_values`). That number cannot know that three of your
players face hard fixtures in a fortnight. Here the squad may change twice:
now (stage 1, Gameweek 1 onwards) and before next Gameweek (stage 2, Gameweek
2 onwards), with FPL's free-transfer rules between them:

* stage 1 uses `k` transfers; free transfers left carry, plus one, capped at 5;
* stage 2 transfers beyond those cost a hit (plus the hit margin);
* free transfers still unused after stage 2 keep the policy's roll value.

For each `k` the best two-stage plan is solved exactly (one MILP, HiGHS). The
action now is the `k` whose whole two-week plan scores best, so "hold now and
make two moves next week" competes with "move now" on the same scale.

Same projections for both stages: the plan for next week is what looks best
today, not a forecast of next week's news. It is re-planned every week.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

MAX_FREE_TRANSFERS = 5


def carried_free_transfers(free_now: int, used_now: int) -> int:
    """FPL: unused free transfers carry over, plus one new, up to five."""
    return min(MAX_FREE_TRANSFERS, max(0, free_now - used_now) + 1)


def solve_two_stage(problem: Any, *, stage1_count: int, free_transfers: int, policy: Any,
                    max_stage2_transfers: int = 3) -> dict[str, Any] | None:
    """The best plan with exactly `stage1_count` transfers now and up to
    `max_stage2_transfers` next week. `problem` is an action-planner `_Problem`."""
    n, gameweeks = problem.n, problem.g
    if gameweeks < 2:
        return None
    weights = problem.weights
    points = problem.points
    starter_value = problem._starter_value()
    bench = problem.bench
    free_next = carried_free_transfers(free_transfers, stage1_count)
    roll = list(policy.roll_values)

    # Layout: x1 (n) | x2 (n) | in2 (n) | s (n*G) | c (n*G) | h2 | z_1..z_R
    X1, X2, IN2 = 0, n, 2 * n
    S = 3 * n
    C = S + n * gameweeks
    H2 = C + n * gameweeks
    Z = H2 + 1
    size = Z + len(roll)

    def s(i: int, g: int) -> int:
        return S + g * n + i

    def c(i: int, g: int) -> int:
        return C + g * n + i

    objective = np.zeros(size)
    objective[X1:X1 + n] = -(points[:, 0] * bench) * weights[0]
    objective[X2:X2 + n] = -(points[:, 1:] * bench[:, None]) @ weights[1:]
    for g in range(gameweeks):
        objective[s(0, g):s(0, g) + n] = -weights[g] * (starter_value[:, g] - points[:, g] * bench)
        objective[c(0, g):c(0, g) + n] = -weights[g] * points[:, g]
    objective[H2] = policy.hit_cost + policy.hit_margin
    objective[Z:Z + len(roll)] = -np.asarray(roll, dtype=float)
    objective[X1:X1 + n] -= 1e-6 * problem.owned
    objective[X2:X2 + n] -= 1e-6 * problem.owned

    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    lower: list[float] = []
    upper: list[float] = []

    def add(entries: list[tuple[int, float]], low: float, high: float) -> None:
        row = len(lower)
        for col, val in entries:
            rows.append(row)
            cols.append(col)
            vals.append(val)
        lower.append(low)
        upper.append(high)

    from optimizer.action_planner import MAX_PER_CLUB, SQUAD_COUNTS, XI_LIMITS

    for base in (X1, X2):
        add([(base + i, 1.0) for i in range(n)], 15, 15)
        for position, count in SQUAD_COUNTS.items():
            add([(base + i, 1.0) for i in range(n) if problem.positions[i] == position], count, count)
        add([(base + i, float(problem.costs[i])) for i in range(n)], -np.inf, problem.budget + 1e-6)
        for club in sorted(set(problem.clubs)):
            members = [i for i in range(n) if problem.clubs[i] == club]
            owned_here = int(sum(problem.owned[i] for i in members))
            add([(base + i, 1.0) for i in members], 0, max(MAX_PER_CLUB, owned_here))
            if owned_here > MAX_PER_CLUB:
                add([(base + i, 1.0) for i in members if not problem.owned[i]], 0, 0)
    # Stage 1: exactly this many newcomers.
    add([(X1 + i, 1.0) for i in range(n) if not problem.owned[i]], stage1_count, stage1_count)
    # Stage 2: in2 >= x2 - x1 counts next week's transfers.
    for i in range(n):
        add([(IN2 + i, 1.0), (X2 + i, -1.0), (X1 + i, 1.0)], 0, np.inf)
    add([(IN2 + i, 1.0) for i in range(n)], 0, max_stage2_transfers)
    # Hits next week: h2 >= transfers - free; unused free = free - transfers + h2.
    add([(H2, 1.0)] + [(IN2 + i, -1.0) for i in range(n)], -free_next, np.inf)
    add([(H2, 1.0)], 0, policy.max_hits)
    add([(Z + j, 1.0) for j in range(len(roll))] + [(IN2 + i, 1.0) for i in range(n)] + [(H2, -1.0)], -np.inf, free_next)
    # Lineups: Gameweek 1 from the stage-1 squad, later weeks from stage 2.
    for g in range(gameweeks):
        squad = X1 if g == 0 else X2
        add([(s(i, g), 1.0) for i in range(n)], 11, 11)
        for position, (low, high) in XI_LIMITS.items():
            add([(s(i, g), 1.0) for i in range(n) if problem.positions[i] == position], low, high)
        add([(c(i, g), 1.0) for i in range(n)], 1, 1)
        for i in range(n):
            add([(s(i, g), 1.0), (squad + i, -1.0)], -np.inf, 0)
            add([(c(i, g), 1.0), (s(i, g), -1.0)], -np.inf, 0)

    integrality = np.ones(size)
    integrality[IN2:IN2 + n] = 0
    integrality[Z:Z + len(roll)] = 0
    upper_bounds = np.ones(size)
    upper_bounds[H2] = policy.max_hits
    lower_bounds = np.zeros(size)
    matrix = coo_matrix((vals, (rows, cols)), shape=(len(lower), size)).tocsr()
    result = milp(c=objective, integrality=integrality, bounds=Bounds(lower_bounds, upper_bounds),
                  constraints=LinearConstraint(matrix, np.array(lower), np.array(upper)),
                  options={"disp": False, "time_limit": policy.solver_time_limit})
    if not result.success or result.x is None:
        return None
    x = result.x
    squad1 = [int(problem.ids[i]) for i in range(n) if x[X1 + i] >= 0.5]
    squad2 = [int(problem.ids[i]) for i in range(n) if x[X2 + i] >= 0.5]
    stage2_transfers = len(set(squad2) - set(squad1))
    hits2 = max(0, stage2_transfers - free_next)
    lineup = 0.0
    for g in range(gameweeks):
        start = [i for i in range(n) if x[s(i, g)] >= 0.5]
        captain = int(np.argmax([x[c(i, g)] for i in range(n)]))
        squad_mask = np.isin(problem.ids, squad1 if g == 0 else squad2)
        on_bench = squad_mask & ~np.isin(np.arange(n), start)
        lineup += weights[g] * (starter_value[start, g].sum() + points[captain, g]
                                + (points[on_bench, g] * bench[on_bench]).sum())
    unused = max(0, free_next - stage2_transfers)
    end_roll = float(sum(roll[:min(unused, len(roll))]))
    return {
        "stage1_count": stage1_count,
        "squad_now": sorted(squad1),
        "squad_next": sorted(squad2),
        "stage2_transfers": stage2_transfers,
        "free_next": free_next,
        "stage2_hits": hits2,
        "lineup_value": float(lineup),
        "end_roll_value": end_roll,
    }


def plan_two_weeks(problem: Any, *, free_transfers: int, max_transfers: int, policy: Any,
                   unlimited: bool) -> dict[str, Any] | None:
    """Best two-week plan for each number of transfers now (0 … max)."""
    if problem.g < 2 or unlimited:
        return None
    plans: list[dict[str, Any]] = []
    for count in range(0, max(0, max_transfers) + 1):
        plan = solve_two_stage(problem, stage1_count=count, free_transfers=free_transfers, policy=policy)
        if plan is None:
            continue
        paid_now = max(0, count - free_transfers)
        plan["stage1_hits"] = paid_now
        plan["score"] = (plan["lineup_value"]
                         - paid_now * (policy.hit_cost + policy.hit_margin)
                         - plan["stage2_hits"] * (policy.hit_cost + policy.hit_margin)
                         + plan["end_roll_value"])
        plans.append(plan)
    if not plans or plans[0]["stage1_count"] != 0:
        return None
    base = plans[0]["score"]
    for plan in plans:
        plan["score_vs_hold"] = round(plan["score"] - base, 3)
    best = max(plans, key=lambda item: (round(item["score"], 6), -item["stage1_count"]))
    return {"plans": plans, "best_count": best["stage1_count"]}


def describe_moves(problem: Any, before: Sequence[int], after: Sequence[int]) -> list[dict[str, Any]]:
    """Pair players out and in by position, for display."""
    outs = sorted(set(before) - set(after))
    ins = sorted(set(after) - set(before))
    moves = []
    for position in ("GK", "DEF", "MID", "FWD"):
        out_pos = [pid for pid in outs if problem.positions[problem.index_of(pid)] == position]
        in_pos = [pid for pid in ins if problem.positions[problem.index_of(pid)] == position]
        for out_id, in_id in zip(out_pos, in_pos):
            moves.append({
                "player_out_id": out_id, "player_out": str(problem.names[problem.index_of(out_id)]),
                "player_in_id": in_id, "player_in": str(problem.names[problem.index_of(in_id)]),
                "position": position,
            })
    return moves


def summarise(problem: Any, owned: Sequence[int], result: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not result:
        return None
    sequences = []
    for plan in result["plans"]:
        sequences.append({
            "transfers_now": plan["stage1_count"],
            "moves_now": describe_moves(problem, owned, plan["squad_now"]),
            "moves_next": describe_moves(problem, plan["squad_now"], plan["squad_next"]),
            "free_transfers_next": plan["free_next"],
            "hits_now": plan["stage1_hits"],
            "hits_next": plan["stage2_hits"],
            "score_vs_hold": plan["score_vs_hold"],
        })
    return {"best_transfers_now": result["best_count"], "sequences": sequences}
