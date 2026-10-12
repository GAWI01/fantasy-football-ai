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
* a doubtful starter (official chance of playing between 0 and 100%) is
  covered by the bench: when he misses, the first substitute comes on. He is
  worth his own expected points plus his chance of missing times the points
  of the squad's best bench player of his kind (outfield or goalkeeper),
  taken from the current squad's best lineup (`_Problem.set_cover`);
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
                 extra_candidates: Sequence[int] = (), selection_bonus: Mapping[int, float] | None = None):
        base = frames[0].drop_duplicates("player_id").set_index("player_id")
        self.policy = policy
        self._selection_bonus = dict(selection_bonus or {})
        self.weights = np.asarray(weights, dtype=float)
        gameweeks = len(frames)
        points = np.zeros((len(base), gameweeks))
        uncertainty = np.zeros((len(base), gameweeks))
        doubt = np.zeros((len(base), gameweeks))
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
            if "availability_multiplier" in values.columns:
                # Only doubtful players: a ruled-out player is benched, not covered.
                chance = pd.to_numeric(values["availability_multiplier"], errors="coerce").fillna(1.0).to_numpy()
                doubt[picked, g] = np.where((chance > 0) & (chance < 1), 1.0 - chance, 0.0)[mask]
        all_ids = np.array([int(pid) for pid in base.index])
        positions = np.array([_normalise_position(p) for p in base["position"]])
        # Plain strings for every club: pandas 3 keeps a missing club as NaN
        # through astype(str), and a float among strings breaks sorting.
        clubs = np.array(["" if pd.isna(club) else str(club) for club in base["team"]], dtype=object)
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
        self.doubt = doubt[keep]
        # Points a doubtful starter's substitute brings, per player and Gameweek
        # (zero until `set_cover` reads them from a lineup).
        self.cover = np.zeros_like(self.points)
        self.names = base["name"].astype(str).to_numpy()[keep]
        self.prices = prices[keep]
        self.owned = np.isin(self.ids, list(owned))
        # A small per-player nudge on selection only (e.g. a likely price rise).
        # It steers the solver between near-equal squads; reported values never include it.
        self.bonus = np.array([float(self._selection_bonus.get(int(pid), 0.0)) for pid in self.ids])
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
        self.size = size
        self._set_objective()
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

    def _starter_value(self) -> np.ndarray:
        """A starter's points per Gameweek, with his substitute's cover."""
        return self.points + self.doubt * self.cover

    def _set_objective(self) -> None:
        n, gameweeks = self.n, self.g
        starter = self._starter_value()
        objective = np.zeros(self.size)
        objective[:n] = -(self.points * self.bench[:, None]) @ self.weights
        for g in range(gameweeks):
            objective[self._s(0, g):self._s(0, g) + n] = -self.weights[g] * (starter[:, g] - self.points[:, g] * self.bench)
            objective[self._c(0, g):self._c(0, g) + n] = -self.weights[g] * self.points[:, g]
        # Deterministic tie-break: among equal plans keep owned players.
        objective[:n] -= 1e-6 * self.owned
        objective[:n] -= self.bonus
        self.objective = objective

    def set_cover(self, solution: "_Solution") -> bool:
        """Read each doubtful starter's substitute from `solution`'s lineups.

        The substitute is the best bench player of the same kind (outfield or
        goalkeeper) in that Gameweek. Every plan is then valued with the cover
        of this lineup, so plans stay on one scale. Returns whether anything
        changed (nothing does when no candidate is doubtful).
        """
        if not self.doubt.any():
            return False
        selected = np.isin(self.ids, solution.ids)
        keeper = self.positions == "GK"
        cover = np.zeros_like(self.points)
        for g, starters in enumerate(solution.starters):
            bench = selected & ~np.isin(self.ids, starters)
            for kind in (keeper, ~keeper):
                pool = bench & kind
                cover[kind, g] = self.points[pool, g].max() if pool.any() else 0.0
        changed = not np.array_equal(cover, self.cover)
        self.cover = cover
        self._set_objective()
        return changed

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
                self._starter_value()[start, g].sum() + self.points[captain, g]
                + (self.points[bench, g] * self.bench[bench]).sum()))
        value = float(np.dot(self.weights, gameweek_values))
        return "optimal", _Solution([int(pid) for pid in self.ids[selected]], starters, captains,
                                    value, gameweek_values)

    def contains(self, player_id: int) -> bool:
        return bool((self.ids == player_id).any())

    def index_of(self, player_id: int) -> int:
        return int(np.where(self.ids == player_id)[0][0])


def _solve_hold(problem: _Problem) -> tuple[str, _Solution | None]:
    """The current squad's best lineup, valued with its own bench as cover."""
    status, hold = problem.solve(newcomers_low=0, newcomers_high=0)
    if hold is not None and problem.set_cover(hold):
        status, hold = problem.solve(newcomers_low=0, newcomers_high=0)
    return status, hold


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

    status, hold = _solve_hold(problem)
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

    # Two-week check (optimizer/two_week.py): the best plan over this week and
    # next, with FPL's free-transfer rules between them. It may only lower the
    # number of transfers made now, e.g. "hold now, two free moves next week"
    # or "do the second move next week instead of a -4 now". It never makes the
    # engine spend earlier: both weeks use today's projections, so waiting for
    # team news has value the model cannot see. The moves for the chosen count
    # are the single-step plan's, so every table stays consistent.
    from optimizer.two_week import plan_two_weeks, summarise
    two_week_raw = plan_two_weeks(problem, free_transfers=free_transfers,
                                  max_transfers=min(max_transfers, free_transfers + policy.max_hits),
                                  policy=policy, unlimited=unlimited)
    two_week = summarise(problem, sorted(owned), two_week_raw)
    if (two_week_raw and two_week_raw["best_count"] in options
            and two_week_raw["best_count"] < best["transfers_used"]
            and not any(value == "time_limit" for value in statuses.values())):
        best = options[two_week_raw["best_count"]]
    ranked = [best] + [item for item in ranked if item is not best]
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
        "two_week": two_week,
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
    status, hold = _solve_hold(problem)
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


def _squad_view(problem: _Problem, solution: _Solution, hold: _Solution, owned: set[int],
                sale_values: Mapping[int, float]) -> dict[str, Any]:
    """A chip squad as the app shows it: the first Gameweek's XI on a pitch."""
    starters = set(solution.starters[0])
    captain = solution.captains[0]
    first = {pid: float(problem.points[problem.index_of(pid), 0]) for pid in solution.ids}
    vice = max((pid for pid in starters if pid != captain), key=lambda pid: (first[pid], -pid))
    bench_outfield = sorted((pid for pid in solution.ids if pid not in starters and problem.positions[problem.index_of(pid)] != "GK"),
                            key=lambda pid: (-first[pid], pid))
    bench_keeper = [pid for pid in solution.ids if pid not in starters and problem.positions[problem.index_of(pid)] == "GK"]
    players = []
    for pid in solution.ids:
        i = problem.index_of(pid)
        players.append({
            "player_id": pid,
            "name": str(problem.names[i]),
            "position": str(problem.positions[i]),
            "team": str(problem.clubs[i]),
            # What the squad pays: a kept player's selling price, a newcomer's market price.
            "cost": round(float(sale_values[pid]) if pid in owned else float(problem.prices[i]), 1),
            "price": round(float(problem.prices[i]), 1),
            "predicted_points": round(first[pid], 3),
            "horizon_points": round(float(problem.points[i] @ problem.weights), 3),
            "owned": pid in owned,
            "starter": pid in starters,
        })
    cost = sum(player["cost"] for player in players)
    projected = sum(first[pid] for pid in starters) + first[captain]
    hold_first = sum(float(problem.points[problem.index_of(pid), 0]) for pid in hold.starters[0]) \
        + float(problem.points[problem.index_of(hold.captains[0]), 0])
    return {
        "players": sorted(players, key=lambda player: player["player_id"]),
        "starting_xi_ids": sorted(starters),
        "bench_ids": bench_outfield + bench_keeper,
        "captain_id": captain,
        "vice_captain_id": vice,
        "projected_points": round(projected, 3),
        "current_projected_points": round(hold_first, 3),
        # On the planner's own scale (weighted horizon for a Wildcard, one week for a Free Hit).
        "gain": round(solution.value - hold.value, 3),
        "players_in": sorted(set(solution.ids) - owned),
        "players_out": sorted(owned - set(solution.ids)),
        "cost": round(cost, 1),
        "budget": round(problem.budget, 1),
        "bank_left": round(problem.budget - cost, 1),
    }


def build_chip_squads(
    frames: Sequence[pd.DataFrame],
    *,
    owned_ids: Sequence[int],
    sale_info: Mapping[int, tuple[float, str, bool]],
    bank: float,
    weights: Sequence[float] | None = None,
    policy: DecisionPolicy | None = None,
    wildcard_bonus: Mapping[int, float] | None = None,
) -> dict[str, Any]:
    """The best Free Hit and Wildcard squads within the manager's budget.

    `wildcard_bonus` nudges the Wildcard (only: a Free Hit squad is handed back,
    so its prices never matter) towards or away from given players, e.g. likely
    price risers and fallers. Players it names join the candidate pool.

    Free Hit: any legal 15 for the next Gameweek only (the squad returns
    afterwards), valued like every plan: the best XI and captain, the bench as
    autosub cover. Wildcard: the same rebuild valued over the weighted horizon,
    because the squad is kept. Both spend the bank plus the squad's selling
    value, with owned players kept at their selling price.
    """
    policy = policy or DEFAULT_POLICY
    if not frames:
        raise ActionPlanningError("at least one Gameweek of projections is required")
    weights = list(weights) if weights is not None else [1.0] * len(frames)
    owned = {int(pid) for pid in owned_ids}
    sale_values = {pid: info[0] for pid, info in sale_info.items()}
    result: dict[str, Any] = {}
    for chip, chip_frames, chip_weights in (
        ("free_hit", frames[:1], [1.0]),
        ("wildcard", frames, weights),
    ):
        bonus = dict(wildcard_bonus or {}) if chip == "wildcard" else {}
        known = {int(pid) for pid in frames[0]["player_id"]}
        problem = _Problem(chip_frames, chip_weights, owned, sale_values, bank, policy,
                           extra_candidates=[pid for pid in bonus if pid in known], selection_bonus=bonus)
        status, hold = _solve_hold(problem)
        if hold is None:
            result[chip] = {"available": False, "status": status}
            continue
        status, rebuild = problem.solve(newcomers_low=0, newcomers_high=15)
        if rebuild is None:
            result[chip] = {"available": False, "status": status}
            continue
        result[chip] = {"available": True, "gameweeks": len(chip_frames), **_squad_view(problem, rebuild, hold, owned, sale_values)}
    return result
