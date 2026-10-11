"""Canonical Gameweek action planner.

The question is not "what is the best transfer?" but "what is the best action
this Gameweek?". Every candidate action (hold/roll, one free transfer, two,
..., a hit) is scored on the same scale and doing nothing is a real option.

Value model (one MILP per transfer count, SciPy/HiGHS):

* a squad is valued by the lineup it can field in every horizon Gameweek:
  the best legal starting XI (1 GK, 3-5 DEF, 2-5 MID, 1-3 FWD) plus the
  captain's second share, chosen per Gameweek;
* bench players count only through autosub coverage: their points carry a
  small weight (`DecisionPolicy.*_bench_weight`) instead of counting as if
  they played. A reserve goalkeeper almost never comes on, so his weight is
  smaller still;
* Gameweeks are weighted (`gw_weights`): later projections are less certain;
* an unused free transfer is worth something next week (`roll_values`), a
  transfer beyond the free ones costs `hit_cost` points plus a risk margin.

The decision score of an action is its weighted lineup gain over holding,
minus hit costs and margin, minus the roll value its free transfers forgo.
All constants are documented assumptions, to be calibrated by backtesting
(`backtesting/decision_backtest.py`); none is fitted to the benchmark teams.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

SQUAD_COUNTS = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
XI_LIMITS = {"GK": (1, 1), "DEF": (3, 5), "MID": (2, 5), "FWD": (1, 3)}
MAX_PER_CLUB = 3
# More free transfers than this means the deadline allows unlimited moves
# (before a manager's first deadline the API reports 20).
UNLIMITED_FREE_TRANSFERS = 15


@dataclass(frozen=True)
class DecisionPolicy:
    # Share of a bench player's points the squad can expect through
    # autosubs. Regular starters miss roughly one match in ten, so an
    # outfield substitute plays about that often; a reserve keeper only
    # plays when the first-choice keeper misses a whole match.
    outfield_bench_weight: float = 0.10
    goalkeeper_bench_weight: float = 0.02
    # Value (weighted horizon points) of the 1st, 2nd, ... free transfer
    # carried into next Gameweek. At most four carry (the cap is five).
    roll_values: tuple[float, ...] = (2.0, 1.5, 1.0, 0.5)
    hit_cost: float = 4.0
    # Extra evidence required per paid transfer. A single swap's weighted
    # horizon projection carries about +/-2.5 points of heuristic uncertainty
    # (backend.planning_service._uncertainty), so a hit must clear its cost
    # by a clear part of that before it is taken.
    hit_margin: float = 2.0
    max_hits: int = 2
    # A Wildcard is one per half-season, so playing it now forgoes the gain
    # a later rebuild would bring. It is recommended only when a free rebuild
    # beats the best normal action by about six points per Gameweek over the
    # weighted horizon (weights sum to ~3.5 Gameweeks).
    wildcard_min_gain: float = 20.0
    # Candidate pool per position (owned players are always included).
    candidates_by_points: Mapping[str, int] = field(
        default_factory=lambda: {"GK": 8, "DEF": 25, "MID": 30, "FWD": 18})
    candidates_by_value: int = 10
    cheapest_candidates: int = 3
    alternatives_per_count: int = 3
    solver_time_limit: float = 5.0

    def roll_value(self, unused_free_transfers: int, free_transfers: int) -> float:
        if free_transfers > UNLIMITED_FREE_TRANSFERS:
            return 0.0
        carried = max(0, min(int(unused_free_transfers), len(self.roll_values)))
        return float(sum(self.roll_values[:carried]))

    def bench_weight(self, position: str) -> float:
        return self.goalkeeper_bench_weight if position == "GK" else self.outfield_bench_weight


DEFAULT_POLICY = DecisionPolicy()


class ActionPlanningError(ValueError):
    """Raised when the action planner cannot evaluate the squad."""


class SolverUnavailable(ActionPlanningError):
    """The solver stopped (e.g. time limit) before proving any plan."""

    def __init__(self, status: str):
        super().__init__(f"the action planner could not finish ({status})")
        self.status = status


@dataclass
class _Solution:
    ids: list[int]
    starters: list[list[int]]
    captains: list[int]
    value: float
    gameweek_values: list[float]


def _normalise_position(value: Any) -> str:
    text = str(value).strip().upper()
    return "GK" if text in {"GK", "GKP"} else text


class _Problem:
    """The candidate pool and constraint matrix shared by every solve."""

    def __init__(self, frames: Sequence[pd.DataFrame], weights: Sequence[float], owned: set[int],
                 sale_values: Mapping[int, float], bank: float, policy: DecisionPolicy,
                 extra_candidates: Sequence[int] = ()):
        base = frames[0].drop_duplicates("player_id").set_index("player_id")
        self.policy = policy
        self.weights = np.asarray(weights, dtype=float)
        gameweeks = len(frames)
        points = np.zeros((len(base), gameweeks))
        uncertainty = np.zeros((len(base), gameweeks))
        index = {int(pid): row for row, pid in enumerate(base.index)}
        for g, frame in enumerate(frames):
            values = frame.drop_duplicates("player_id").set_index("player_id")
            rows = [index.get(int(pid)) for pid in values.index]
            mask = [row is not None for row in rows]
            picked = [row for row in rows if row is not None]
            column = pd.to_numeric(values["predicted_points"], errors="coerce").fillna(0.0).clip(lower=0.0)
            points[picked, g] = column.to_numpy()[mask]
            if "uncertainty" in values.columns:
                band = pd.to_numeric(values["uncertainty"], errors="coerce").fillna(0.0).clip(lower=0.0)
                uncertainty[picked, g] = band.to_numpy()[mask]
        all_ids = np.array([int(pid) for pid in base.index])
        positions = np.array([_normalise_position(p) for p in base["position"]])
        clubs = base["team"].astype(str).to_numpy()
        prices = pd.to_numeric(base["price"], errors="coerce").to_numpy(dtype=float)
        score = points @ self.weights

        keep = np.isin(all_ids, list(owned) + [int(pid) for pid in extra_candidates])
        for position in SQUAD_COUNTS:
            candidates = np.where((positions == position) & ~keep & np.isfinite(prices) & (prices > 0))[0]
            if not len(candidates):
                continue
            by_points = candidates[np.argsort(-score[candidates], kind="stable")]
            keep[by_points[: policy.candidates_by_points.get(position, 20)]] = True
            by_value = candidates[np.argsort(-(score[candidates] / prices[candidates]), kind="stable")]
            keep[by_value[: policy.candidates_by_value]] = True
            cheapest = candidates[np.lexsort((-score[candidates], prices[candidates]))]
            keep[cheapest[: policy.cheapest_candidates]] = True
        self.ids = all_ids[keep]
        self.positions = positions[keep]
        self.clubs = clubs[keep]
        self.points = points[keep]
        self.uncertainty = uncertainty[keep]
        self.names = base["name"].astype(str).to_numpy()[keep]
        self.prices = prices[keep]
        self.owned = np.isin(self.ids, list(owned))
        if self.owned.sum() != len(owned):
            raise ActionPlanningError("current players missing from predictions")
        self.costs = np.array([
            float(sale_values[int(pid)]) if owned_flag else float(price)
            for pid, owned_flag, price in zip(self.ids, self.owned, self.prices)
        ])
        self.budget = float(bank) + float(sum(sale_values[int(pid)] for pid in owned))
        self.bench = np.array([policy.bench_weight(position) for position in self.positions])
        self._build()

    # Variable layout: x (n) | s (n*G) | c (n*G)
    def _build(self) -> None:
        n, gameweeks = len(self.ids), len(self.weights)
        self.n, self.g = n, gameweeks
        size = n * (1 + 2 * gameweeks)
        objective = np.zeros(size)
        objective[:n] = -(self.points * self.bench[:, None]) @ self.weights
        for g in range(gameweeks):
            objective[self._s(0, g):self._s(0, g) + n] = -self.weights[g] * self.points[:, g] * (1 - self.bench)
            objective[self._c(0, g):self._c(0, g) + n] = -self.weights[g] * self.points[:, g]
        # Deterministic tie-break: among equal plans keep owned players.
        objective[:n] -= 1e-6 * self.owned
        self.objective = objective
        rows, cols, vals, lower, upper = [], [], [], [], []

        def add(entries: list[tuple[int, float]], low: float, high: float) -> None:
            row = len(lower)
            for col, val in entries:
                rows.append(row)
                cols.append(col)
                vals.append(val)
            lower.append(low)
            upper.append(high)

        add([(i, 1.0) for i in range(n)], 15, 15)
        for position, count in SQUAD_COUNTS.items():
            add([(i, 1.0) for i in range(n) if self.positions[i] == position], count, count)
        add([(i, float(self.costs[i])) for i in range(n)], -np.inf, self.budget + 1e-6)
        for club in sorted(set(self.clubs)):
            members = [i for i in range(n) if self.clubs[i] == club]
            owned_here = int(sum(self.owned[i] for i in members))
            add([(i, 1.0) for i in members], 0, max(MAX_PER_CLUB, owned_here))
            if owned_here > MAX_PER_CLUB:
                # A club over the limit (an owned player moved clubs) takes no newcomers.
                add([(i, 1.0) for i in members if not self.owned[i]], 0, 0)
        for g in range(gameweeks):
            add([(self._s(i, g), 1.0) for i in range(n)], 11, 11)
            for position, (low, high) in XI_LIMITS.items():
                add([(self._s(i, g), 1.0) for i in range(n) if self.positions[i] == position], low, high)
            add([(self._c(i, g), 1.0) for i in range(n)], 1, 1)
            for i in range(n):
                add([(self._s(i, g), 1.0), (i, -1.0)], -np.inf, 0)
                add([(self._c(i, g), 1.0), (self._s(i, g), -1.0)], -np.inf, 0)
        self.base_rows = (rows, cols, vals, lower, upper)
        self.size = size

    def _s(self, i: int, g: int) -> int:
        return self.n + g * self.n + i

    def _c(self, i: int, g: int) -> int:
        return self.n + self.g * self.n + g * self.n + i

    def solve(self, *, newcomers_low: int, newcomers_high: int,
              banned: Sequence[int] = (), required: Sequence[int] = ()) -> tuple[str, _Solution | None]:
        rows, cols, vals, lower, upper = (list(part) for part in self.base_rows)
        extra = [([(i, 1.0) for i in range(self.n) if not self.owned[i]], newcomers_low, newcomers_high)]
        for entries, low, high in extra:
            row = len(lower)
            for col, val in entries:
                rows.append(row)
                cols.append(col)
                vals.append(val)
            lower.append(low)
            upper.append(high)
        matrix = coo_matrix((vals, (rows, cols)), shape=(len(lower), self.size)).tocsr()
        upper_bounds = np.ones(self.size)
        lower_bounds = np.zeros(self.size)
        for player_id in banned:
            upper_bounds[self.index_of(int(player_id))] = 0.0
        for player_id in required:
            lower_bounds[self.index_of(int(player_id))] = 1.0
        result = milp(
            c=self.objective,
            integrality=np.ones(self.size),
            bounds=Bounds(lower_bounds, upper_bounds),
            constraints=LinearConstraint(matrix, np.array(lower), np.array(upper)),
            options={"disp": False, "time_limit": self.policy.solver_time_limit},
        )
        if not result.success or result.x is None:
            status = {1: "time_limit", 2: "infeasible", 3: "unbounded"}.get(result.status, "solver_error")
            return status, None
        x = result.x
        selected = x[: self.n] >= 0.5
        starters, captains, gameweek_values = [], [], []
        for g in range(self.g):
            start = np.array([x[self._s(i, g)] >= 0.5 for i in range(self.n)])
            captain = int(np.argmax([x[self._c(i, g)] for i in range(self.n)]))
            starters.append([int(self.ids[i]) for i in np.where(start)[0]])
            captains.append(int(self.ids[captain]))
            bench = selected & ~start
            gameweek_values.append(float(
                self.points[start, g].sum() + self.points[captain, g]
                + (self.points[bench, g] * self.bench[bench]).sum()))
        value = float(np.dot(self.weights, gameweek_values))
        return "optimal", _Solution([int(pid) for pid in self.ids[selected]], starters, captains,
                                    value, gameweek_values)

    def contains(self, player_id: int) -> bool:
        return bool((self.ids == player_id).any())

    def index_of(self, player_id: int) -> int:
        return int(np.where(self.ids == player_id)[0][0])


def _transfers(problem: _Problem, solution: _Solution, owned: set[int],
               sale_info: Mapping[int, tuple[float, str, bool]]) -> list[dict[str, Any]]:
    selected = set(solution.ids)
    outs = sorted(owned - selected)
    ins = sorted(selected - owned)
    moves = []
    for position in SQUAD_COUNTS:
        out_pos = [pid for pid in outs if problem.positions[problem.index_of(pid)] == position]
        in_pos = [pid for pid in ins if problem.positions[problem.index_of(pid)] == position]
        for out_id, in_id in zip(out_pos, in_pos, strict=True):
            out_i, in_i = problem.index_of(out_id), problem.index_of(in_id)
            out_horizon = float(problem.points[out_i] @ problem.weights)
            in_horizon = float(problem.points[in_i] @ problem.weights)
            sale, source, _known = sale_info[out_id]
            moves.append({
                "player_out_id": out_id,
                "player_out": str(problem.names[out_i]),
                "player_in_id": in_id,
                "player_in": str(problem.names[in_i]),
                "position": position,
                "price": float(problem.prices[in_i]),
                # Weighted horizon points of each player on his own; the plan's
                # value is the lineup change below, not this difference.
                "predicted_points": round(in_horizon, 3),
                "out_predicted_points": round(out_horizon, 3),
                "next_gw_points_in": round(float(problem.points[in_i, 0]), 3),
                "next_gw_points_out": round(float(problem.points[out_i, 0]), 3),
                "gain": round(in_horizon - out_horizon, 3),
                "selling_price": sale,
                "selling_price_source": source,
            })
    return moves


def _plan_uncertainty(problem: _Problem, moves: list[dict[str, Any]]) -> float | None:
    if not problem.uncertainty.any():
        return None
    total = 0.0
    for move in moves:
        for pid in (move["player_in_id"], move["player_out_id"]):
            band = problem.uncertainty[problem.index_of(pid)] * problem.weights
            total += float(np.square(band).sum())
    return round(math.sqrt(total), 3)


def _option(problem: _Problem, solution: _Solution, hold: _Solution, owned: set[int],
            sale_info: Mapping[int, tuple[float, str, bool]], free_transfers: int,
            policy: DecisionPolicy) -> dict[str, Any]:
    moves = _transfers(problem, solution, owned, sale_info)
    count = len(moves)
    unlimited = free_transfers > UNLIMITED_FREE_TRANSFERS
    paid = 0 if unlimited else max(0, count - free_transfers)
    hit = paid * policy.hit_cost
    roll_lost = (policy.roll_value(free_transfers, free_transfers)
                 - policy.roll_value(max(0, free_transfers - count), free_transfers))
    gross = solution.value - hold.value
    return {
        "transfers": moves,
        "transfers_used": count,
        "paid_transfers": paid,
        "lineup_value": round(solution.value, 3),
        "gross_gain": round(gross, 3),
        "hit_cost": hit,
        "net_gain": round(gross - hit, 3),
        "roll_value_forgone": round(roll_lost, 3),
        "risk_margin": round(paid * policy.hit_margin, 3),
        "decision_score": round(gross - hit - paid * policy.hit_margin - roll_lost, 3),
        "next_gw_gain": round(solution.gameweek_values[0] - hold.gameweek_values[0], 3),
        "uncertainty": _plan_uncertainty(problem, moves),
        "squad": solution.ids,
        "lineup": {"starters": solution.starters[0], "captain": solution.captains[0]},
    }


def _plan_key(option: Mapping[str, Any]) -> frozenset:
    return frozenset((move["player_out_id"], move["player_in_id"]) for move in option["transfers"])


def classify_action(transfers_used: int, hit_cost: float) -> str:
    if transfers_used <= 0:
        return "HOLD"
    if hit_cost > 0:
        return "HIT"
    return "SINGLE_TRANSFER" if transfers_used == 1 else "MULTI_TRANSFER"


def plan_action(
    frames: Sequence[pd.DataFrame],
    *,
    owned_ids: Sequence[int],
    sale_info: Mapping[int, tuple[float, str, bool]],
    bank: float,
    free_transfers: int,
    max_transfers: int,
    weights: Sequence[float] | None = None,
    policy: DecisionPolicy | None = None,
    evaluate_wildcard: bool = False,
) -> dict[str, Any]:
    """Score every action from hold up to `max_transfers` and choose the best."""
    policy = policy or DEFAULT_POLICY
    if not frames:
        raise ActionPlanningError("at least one Gameweek of projections is required")
    weights = list(weights) if weights is not None else [1.0] * len(frames)
    if len(weights) != len(frames):
        raise ActionPlanningError("weights must match the projected Gameweeks")
    owned = {int(pid) for pid in owned_ids}
    problem = _Problem(frames, weights, owned, {pid: info[0] for pid, info in sale_info.items()}, bank, policy)
    unlimited = free_transfers > UNLIMITED_FREE_TRANSFERS
    max_transfers = max(0, min(int(max_transfers), 15))

    status, hold = problem.solve(newcomers_low=0, newcomers_high=0)
    if hold is None:
        if status == "infeasible":
            raise ActionPlanningError("the current squad cannot field a legal lineup")
        raise SolverUnavailable(status)
    options: dict[int, dict[str, Any]] = {0: _option(problem, hold, hold, owned, sale_info, free_transfers, policy)}
    solutions: dict[int, _Solution] = {0: hold}
    statuses = {0: status}
    counts = [max_transfers] if unlimited and max_transfers else range(1, max_transfers + 1)
    for count in counts:
        low = 1 if unlimited else count
        status, solution = problem.solve(newcomers_low=low, newcomers_high=count)
        statuses[count] = status
        if solution is not None:
            option = _option(problem, solution, hold, owned, sale_info, free_transfers, policy)
            options[option["transfers_used"]] = option
            solutions[option["transfers_used"]] = solution

    ranked = sorted(options.values(), key=lambda item: (-item["decision_score"], item["transfers_used"]))
    best = ranked[0]
    best_count = best["transfers_used"]

    # Other plans with the chosen number of transfers: the best plan without
    # each chosen incoming player in turn ("the alternative to Rashford").
    alternatives = [item for item in ranked[1:]]
    if best_count:
        banned: list[int] = []
        incoming = [move["player_in_id"] for move in best["transfers"]]
        for _ in range(policy.alternatives_per_count):
            candidates = [pid for pid in incoming if pid not in banned]
            if not candidates:
                break
            banned.append(candidates[0])
            status, solution = problem.solve(newcomers_low=best_count, newcomers_high=best_count, banned=banned)
            if solution is None:
                break
            option = _option(problem, solution, hold, owned, sale_info, free_transfers, policy)
            alternatives.append(option)
            incoming += [move["player_in_id"] for move in option["transfers"]]
    seen = {_plan_key(best)}
    unique = []
    for item in sorted(alternatives, key=lambda item: (-item["decision_score"], item["transfers_used"])):
        if _plan_key(item) not in seen:
            seen.add(_plan_key(item))
            unique.append(item)
    alternatives = unique

    timed_out = any(value == "time_limit" for value in statuses.values())
    result = {
        "action": classify_action(best_count, best["hit_cost"]),
        "chosen": best,
        "hold": options[0],
        "options_by_transfer_count": [options[count] for count in sorted(options)],
        "alternatives": alternatives,
        "free_transfers": free_transfers,
        "max_transfers_searched": max_transfers,
        "budget": round(problem.budget, 3),
        "weights": [round(float(w), 4) for w in weights],
        "policy": {
            "outfield_bench_weight": policy.outfield_bench_weight,
            "goalkeeper_bench_weight": policy.goalkeeper_bench_weight,
            "roll_values": list(policy.roll_values),
            "hit_cost": policy.hit_cost,
            "hit_margin": policy.hit_margin,
        },
        "solver_status": "time_limit" if timed_out else "optimal",
        "optimality_known": not timed_out,
    }
    if evaluate_wildcard:
        result["wildcard"] = _evaluate_wildcard(problem, hold, best, policy)
    return result


def _evaluate_wildcard(problem: _Problem, hold: _Solution, best: Mapping[str, Any],
                       policy: DecisionPolicy) -> dict[str, Any]:
    """A free rebuild against the best normal action, on the same value scale."""
    status, rebuild = problem.solve(newcomers_low=0, newcomers_high=15)
    if rebuild is None:
        return {"evaluated": False, "status": status}
    rebuild_gain = rebuild.value - hold.value
    advantage = rebuild_gain - float(best["decision_score"])
    return {
        "evaluated": True,
        "rebuild_gain": round(rebuild_gain, 3),
        "best_action_score": round(float(best["decision_score"]), 3),
        "advantage": round(advantage, 3),
        "threshold": policy.wildcard_min_gain,
        "players_changed": len(set(rebuild.ids) - set(hold.ids)),
        "players_in": sorted(set(rebuild.ids) - set(hold.ids)),
        "players_out": sorted(set(hold.ids) - set(rebuild.ids)),
        "recommended": advantage >= policy.wildcard_min_gain,
    }


def evaluate_moves(
    frames: Sequence[pd.DataFrame],
    *,
    owned_ids: Sequence[int],
    sale_info: Mapping[int, tuple[float, str, bool]],
    bank: float,
    free_transfers: int,
    sell: Sequence[int],
    buy: Sequence[int],
    weights: Sequence[float] | None = None,
    policy: DecisionPolicy | None = None,
) -> dict[str, Any]:
    """Score a manager's own transfers on the planner's scale.

    The squad sells exactly `sell` and buys exactly `buy`; everything else
    (best XI, captain, bench per Gameweek) is chosen as for any plan, so the
    result is directly comparable with holding and with the recommendation.
    """
    policy = policy or DEFAULT_POLICY
    weights = list(weights) if weights is not None else [1.0] * len(frames)
    owned = {int(pid) for pid in owned_ids}
    sell, buy = [int(pid) for pid in sell], [int(pid) for pid in buy]
    if not sell or len(sell) != len(buy):
        raise ActionPlanningError("Choose the same number of players to sell and to buy")
    if len(set(sell)) != len(sell) or len(set(buy)) != len(buy):
        raise ActionPlanningError("Each player can only be chosen once")
    if not set(sell) <= owned:
        raise ActionPlanningError("You can only sell players in your squad")
    if set(buy) & owned:
        raise ActionPlanningError("You already own a player you chose to buy")
    missing = [pid for pid in buy if not any((frame["player_id"] == pid).any() for frame in frames[:1])]
    if missing:
        raise ActionPlanningError("A chosen player has no projection for this Gameweek")
    problem = _Problem(frames, weights, owned, {pid: info[0] for pid, info in sale_info.items()}, bank, policy,
                       extra_candidates=buy)
    status, hold = problem.solve(newcomers_low=0, newcomers_high=0)
    if hold is None:
        raise SolverUnavailable(status)
    status, solution = problem.solve(newcomers_low=len(buy), newcomers_high=len(buy),
                                     banned=sell, required=buy)
    if solution is None:
        reasons = []
        sold_value = sum(sale_info[pid][0] for pid in sell)
        bought_value = sum(float(problem.prices[problem.index_of(pid)]) for pid in buy)
        if bought_value > bank + sold_value + 1e-6:
            reasons.append(f"it costs £{bought_value - sold_value - bank:.1f}m more than you can spend")
        positions_out = sorted(problem.positions[problem.index_of(pid)] for pid in sell)
        positions_in = sorted(problem.positions[problem.index_of(pid)] for pid in buy)
        if positions_out != positions_in:
            reasons.append("players must be replaced position for position")
        if not reasons:
            reasons.append("it breaks the three-players-per-club rule")
        return {"legal": False, "reason": "This move is not allowed: " + "; ".join(reasons) + "."}
    option = _option(problem, solution, hold, owned, {**sale_info}, free_transfers, policy)
    return {"legal": True, "option": option, "hold": _option(problem, hold, hold, owned, sale_info, free_transfers, policy)}
