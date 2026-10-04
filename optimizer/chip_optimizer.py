from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
import pandas as pd

from .squad_optimizer import optimize_squad
from .starting_xi import select_starting_xi
from transfer_analysis import selling_value

CHIPS=("WILDCARD","FREE_HIT","BENCH_BOOST","TRIPLE_CAPTAIN")

@dataclass(frozen=True)
class ChipOptimizationConfig:
    horizon: int = 3
    bench_boost_weight: float = 1.0
    triple_captain_weight: float = 1.0
    wildcard_weight: float = 1.0
    free_hit_weight: float = 1.0
    def __post_init__(self):
        if self.horizon < 1: raise ValueError("horizon must be >= 1")

def _prepared(df: pd.DataFrame) -> pd.DataFrame:
    required={"player_id","predicted_points"}
    missing=required-set(df.columns)
    if missing: raise ValueError("predictions missing columns: "+", ".join(sorted(missing)))
    out=df.copy()
    out["player_id"]=pd.to_numeric(out["player_id"],errors="raise").astype(int)
    out["predicted_points"]=pd.to_numeric(out["predicted_points"],errors="raise").astype(float)
    return out

def _legal_optimal_squad(pool: pd.DataFrame, budget: float) -> pd.DataFrame | None:
    required = {"name", "position", "team", "price"}
    if not required.issubset(pool.columns):
        return None
    try:
        return optimize_squad(pool.copy(), budget=budget)
    except ValueError as exc:
        if "could not find a valid squad" in str(exc):
            return None
        raise


def _owned_lineup(squad: pd.DataFrame, starting_xi_ids: list[int] | None, captain_id: int | None):
    optimal = select_starting_xi(squad)
    ids = set(starting_xi_ids) if starting_xi_ids is not None else {int(p["player_id"]) for p in optimal["starting_xi"]}
    starters = squad[squad["player_id"].isin(ids)].copy()
    positions = starters["position"].astype(str).str.upper().replace({"GKP": "GK"}).value_counts()
    if len(ids) != 11 or len(starters) != 11 or positions.get("GK", 0) != 1 or positions.get("DEF", 0) < 3 or positions.get("FWD", 0) < 1:
        raise ValueError("starting_xi_ids must identify a legal owned starting XI")
    if captain_id is None:
        captain_id = int(starters.sort_values(["predicted_points", "player_id"], ascending=[False, True]).iloc[0]["player_id"])
    if captain_id not in ids:
        raise ValueError("captain_id must belong to the owned starting XI")
    captain_points = float(starters.loc[starters["player_id"] == captain_id, "predicted_points"].iloc[0])
    bench = squad[~squad["player_id"].isin(ids)]
    return float(starters["predicted_points"].sum()) + captain_points, float(bench["predicted_points"].sum()), captain_points


def evaluate_chip_scenarios(
    current_squad: pd.DataFrame,
    predictions: pd.DataFrame,
    *,
    available_chips: Mapping[str, bool] | None = None,
    config: ChipOptimizationConfig | None = None,
    double_gameweek: bool = False,
    blank_gameweek: bool = False,
    bank: float = 0.0,
    starting_xi_ids: list[int] | None = None,
    captain_id: int | None = None,
) -> dict[str, Any]:
    cfg = config or ChipOptimizationConfig()
    squad = _prepared(current_squad)
    pool = _prepared(predictions)
    available = {c: bool(available_chips.get(c, False)) if available_chips is not None else True for c in CHIPS}
    if not any(available.values()):
        baseline = float(squad["predicted_points"].sum())
        if len(squad) == 15 and {"name", "position"}.issubset(squad.columns):
            baseline, _, _ = _owned_lineup(squad, starting_xi_ids, captain_id)
        known_sales = "price" in squad.columns and all(selling_value(row.to_dict(), float(row["price"]))[2] for _, row in squad.iterrows())
        return {"recommended_chip": None, "score": 0.0, "scenarios": [], "baseline_value": round(baseline, 3),
                "selling_prices_known": bool(known_sales), "budget_is_estimate": not known_sales}

    baseline, bench_value, captain_points = _owned_lineup(squad, starting_xi_ids, captain_id)
    bank = float(bank)
    if not pd.notna(bank) or bank < 0:
        raise ValueError("bank must be a non-negative number")
    sales = {int(row["player_id"]): selling_value(row.to_dict(), float(row["price"])) for _, row in squad.iterrows()}
    budget = bank + sum(sale[0] for sale in sales.values())
    selling_prices_known = all(sale[2] for sale in sales.values())
    scenarios = []
    legal_squad = None
    if available["WILDCARD"] or (available["FREE_HIT"] and blank_gameweek):
        # Owned players are retained at no additional cost; the budget form
        # below charges their sale value, and newcomers their purchase price.
        pool = pd.concat([pool[~pool["player_id"].isin(sales)], squad], ignore_index=True)
        pool["price"] = [sales[int(row["player_id"])][0] if int(row["player_id"]) in sales else float(row["price"]) for _, row in pool.iterrows()]
        legal_squad = _legal_optimal_squad(pool, budget)
    if legal_squad is not None:
        xi = select_starting_xi(legal_squad)
        best = float(xi["starting_xi_base_points"]) + float(xi["captain"]["predicted_points"])
        gain = max(0.0, best - baseline)
        if available["WILDCARD"]:
            scenarios.append(("WILDCARD", gain * cfg.wildcard_weight,
                              "Compare legal starting XI and captain points within the manager's budget."))
        if available["FREE_HIT"] and blank_gameweek:
            scenarios.append(("FREE_HIT", gain * cfg.free_hit_weight,
                              "Compare a legal one-week XI and captain against the owned lineup."))
    if available["BENCH_BOOST"] and double_gameweek:
        scenarios.append(("BENCH_BOOST", max(0.0, bench_value) * cfg.bench_boost_weight,
                          "Bench Boost adds the expected points of the four owned bench players."))
    if available["TRIPLE_CAPTAIN"] and double_gameweek:
        scenarios.append(("TRIPLE_CAPTAIN", max(0.0, captain_points) * cfg.triple_captain_weight,
                          "Triple Captain adds one extra multiple to the already doubled owned captain."))
    scenarios.sort(key=lambda x: (-x[1], x[0]))
    output = [{"chip": c, "score": round(max(0.0, s), 3), "reason": r} for c, s, r in scenarios]
    recommendation = output[0] if output and output[0]["score"] > 0 else None
    return {
        "recommended_chip": recommendation["chip"] if recommendation else None,
        "score": recommendation["score"] if recommendation else 0.0,
        "scenarios": output,
        "baseline_value": round(baseline, 3),
        "budget": round(budget, 3),
        "selling_prices_known": selling_prices_known,
        "budget_is_estimate": not selling_prices_known,
        "selling_price_sources": {player_id: sale[1] for player_id, sale in sales.items()},
    }

def chip_advisor_upgrade(current_squad: pd.DataFrame,predictions: pd.DataFrame,**kwargs: Any)->dict[str,Any]:
    return evaluate_chip_scenarios(current_squad,predictions,**kwargs)
