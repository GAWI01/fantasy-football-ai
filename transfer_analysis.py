from __future__ import annotations

from typing import Any

import pandas as pd
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from fpl_rules import detect_club_changes, validate_transfer_squad


class TransferAnalysisError(ValueError):
    """Raised when transfer analysis cannot be performed."""


class TransferInAnalysisError(TransferAnalysisError):
    """Raised when transfer-in analysis cannot be performed."""


REQUIRED_PREDICTION_COLUMNS = {
    "player_id", "name", "position", "price", "predicted_points",
}


def selling_value(pick: dict[str, Any], market_price: float) -> tuple[float, str, bool]:
    """Use a supplied selling value, otherwise return an explicitly labelled estimate."""
    supplied = pick.get("selling_price")
    supplied_source = pick.get("selling_price_source")
    source = supplied_source if isinstance(supplied_source, str) and supplied_source else "provided_selling_price"
    estimated_sources = {"market_price", "market_price_estimate", "estimate", "estimated", "unknown", "purchase_price_estimate"}
    if supplied is not None and source not in estimated_sources:
        value = float(supplied)
        if np.isfinite(value) and value > 0:
            return value, source, True
    purchase = pick.get("purchase_price")
    if purchase is not None and pd.notna(purchase):
        purchase = float(purchase)
        profit_tenths = max(0, round((market_price - purchase) * 10))
        return min(market_price, purchase + (profit_tenths // 2) / 10), "purchase_price_estimate", False
    return float(market_price), "market_price_estimate", False


def _validate_inputs(team: dict[str, Any], predictions: pd.DataFrame) -> list[dict[str, Any]]:
    if not isinstance(team, dict):
        raise TransferAnalysisError("team must be a dictionary")
    if not isinstance(predictions, pd.DataFrame):
        raise TransferAnalysisError("predictions must be a pandas DataFrame")
    if "picks" not in team:
        raise TransferAnalysisError("team is missing picks")
    missing = REQUIRED_PREDICTION_COLUMNS - set(predictions.columns)
    if missing:
        raise TransferAnalysisError(
            "predictions is missing columns: " + ", ".join(sorted(missing))
        )
    picks = team["picks"]
    if not isinstance(picks, list):
        raise TransferAnalysisError("team picks must be a list")
    for pick in picks:
        if not isinstance(pick, dict):
            raise TransferAnalysisError("team pick must be a dictionary")
        if "player_id" not in pick:
            raise TransferAnalysisError("team pick is missing player_id")
    return picks


def analyze_transfer_out(team: dict[str, Any], predictions: pd.DataFrame) -> pd.DataFrame:
    """Rank the user's players by transfer-out priority."""
    picks = _validate_inputs(team, predictions)
    columns = [
        "player_id", "name", "position", "price", "predicted_points",
        "points_per_million", "transfer_score", "recommendation",
    ]
    if not picks:
        return pd.DataFrame(columns=columns)

    player_ids = [pick["player_id"] for pick in picks]
    result = predictions[predictions["player_id"].isin(player_ids)].copy()
    if result.empty:
        return pd.DataFrame(columns=columns)

    result["price"] = pd.to_numeric(result["price"], errors="coerce")
    result["predicted_points"] = pd.to_numeric(result["predicted_points"], errors="coerce")
    result = result.dropna(subset=["price", "predicted_points"])
    result = result[result["price"] > 0].copy()
    if result.empty:
        return pd.DataFrame(columns=columns)

    result["points_per_million"] = result["predicted_points"] / result["price"]
    pmin, pmax = result["predicted_points"].min(), result["predicted_points"].max()
    vmin, vmax = result["points_per_million"].min(), result["points_per_million"].max()
    result["_points_score"] = 1.0 if pmax == pmin else (result["predicted_points"] - pmin) / (pmax - pmin)
    result["_value_score"] = 1.0 if vmax == vmin else (result["points_per_million"] - vmin) / (vmax - vmin)
    result["transfer_score"] = (1 - result["_points_score"]) * 0.6 + (1 - result["_value_score"]) * 0.4
    result["recommendation"] = "KEEP"
    result.loc[result["transfer_score"] >= 0.65, "recommendation"] = "TRANSFER OUT"
    result = result.sort_values(["transfer_score", "predicted_points"], ascending=[False, True]).reset_index(drop=True)
    return result[columns]


def analyze_transfer_in(
    team: dict[str, Any],
    predictions: pd.DataFrame,
    player_out_id: int | None = None,
    budget: float | None = None,
) -> pd.DataFrame:
    """Rank eligible same-position replacements by expected points gain."""
    try:
        picks = _validate_inputs(team, predictions)
    except TransferAnalysisError as exc:
        raise TransferInAnalysisError(str(exc)) from exc

    columns = ["player_id", "name", "position", "price", "predicted_points", "transfer_gain"]
    if player_out_id is None:
        raise TransferInAnalysisError("player_out_id is required")

    outgoing = predictions[predictions["player_id"] == player_out_id].copy()
    if outgoing.empty:
        raise TransferInAnalysisError(f"player_out_id {player_out_id} was not found in predictions")

    outgoing_row = outgoing.iloc[0]
    outgoing_position = outgoing_row["position"]
    outgoing_points = pd.to_numeric(outgoing_row["predicted_points"], errors="coerce")
    if pd.isna(outgoing_points):
        raise TransferInAnalysisError("outgoing player has invalid predicted_points")

    owned_ids = {pick["player_id"] for pick in picks}
    owned_ids.discard(player_out_id)
    candidates = predictions[predictions["position"] == outgoing_position].copy()
    candidates = candidates[~candidates["player_id"].isin(owned_ids)]
    candidates = candidates[candidates["player_id"] != player_out_id].copy()
    candidates["price"] = pd.to_numeric(candidates["price"], errors="coerce")
    candidates["predicted_points"] = pd.to_numeric(candidates["predicted_points"], errors="coerce")
    candidates = candidates.dropna(subset=["price", "predicted_points"])
    candidates = candidates[candidates["price"] > 0].copy()

    if budget is not None:
        try:
            budget_value = float(budget)
        except (TypeError, ValueError) as exc:
            raise TransferInAnalysisError("budget must be a number") from exc
        candidates = candidates[candidates["price"] <= budget_value].copy()

    if candidates.empty:
        return pd.DataFrame(columns=columns)

    candidates["transfer_gain"] = candidates["predicted_points"] - float(outgoing_points)
    candidates = candidates.sort_values(
        ["transfer_gain", "predicted_points", "price"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    return candidates[columns]


def analyze_transfer_recommendation(
    team: dict[str, Any],
    predictions: pd.DataFrame,
    player_out_id: int | None = None,
    budget: float | None = None,
) -> dict[str, Any]:
    """Return the best transfer-in recommendation and alternatives."""
    if player_out_id is None:
        raise TransferAnalysisError("player_out_id is required")
    try:
        candidates = analyze_transfer_in(team, predictions, player_out_id=player_out_id, budget=budget)
    except TransferInAnalysisError as exc:
        raise TransferAnalysisError(str(exc)) from exc
    if candidates.empty:
        raise TransferAnalysisError("No eligible transfer-in candidates found")

    recommended = candidates.iloc[0]
    return {
        "player_out_id": player_out_id,
        "recommended_player_id": recommended["player_id"],
        "recommended_player": recommended["name"],
        "predicted_gain": float(recommended["transfer_gain"]),
        "recommended_price": float(recommended["price"]),
        "recommended_predicted_points": float(recommended["predicted_points"]),
        "alternatives": candidates.iloc[1:].reset_index(drop=True),
    }

def analyze_transfer_scenario(
    team: dict[str, Any],
    predictions: pd.DataFrame,
    player_out_id: int | None = None,
    budget: float | None = None,
) -> dict[str, Any]:
    """Return a complete transfer scenario."""

    if player_out_id is None:
        raise TransferAnalysisError(
            "player_out_id is required"
        )

    recommendation = analyze_transfer_recommendation(
        team,
        predictions,
        player_out_id=player_out_id,
        budget=budget,
    )

    predicted_gain = float(
        recommendation["predicted_gain"]
    )

    recommended_player = recommendation[
        "recommended_player"
    ]

    recommended_price = float(
        recommendation["recommended_price"]
    )

    recommended_points = float(
        recommendation["recommended_predicted_points"]
    )

    if predicted_gain > 0:
        reason = (
            f"{recommended_player} is recommended because "
            f"the model predicts {recommended_points:.1f} points, "
            f"giving an expected gain of "
            f"+{predicted_gain:.1f} points."
        )
    elif predicted_gain == 0:
        reason = (
            f"{recommended_player} is recommended because "
            f"the model predicts the same number of points "
            f"as the outgoing player."
        )
    else:
        reason = (
            f"{recommended_player} is the best available option, "
            f"although the model predicts a decrease of "
            f"{abs(predicted_gain):.1f} points."
        )

    return {
        "player_out_id": player_out_id,
        "recommended_player_id": recommendation[
            "recommended_player_id"
        ],
        "recommended_player": recommended_player,
        "predicted_gain": predicted_gain,
        "recommended_price": recommended_price,
        "recommended_predicted_points": recommended_points,
        "alternatives": recommendation["alternatives"],
        "reason": reason,
    }


def analyze_transfer_optimizer(
    team: dict[str, Any],
    predictions: pd.DataFrame,
    player_out_ids: list[int] | None = None,
    budget: float | None = None,
) -> dict[str, Any]:
    """Find and rank the best multi-transfer scenario."""

    if player_out_ids is None:
        raise TransferAnalysisError(
            "player_out_ids is required"
        )

    if not player_out_ids:
        raise TransferAnalysisError(
            "player_out_ids must not be empty"
        )

    if not isinstance(player_out_ids, list):
        raise TransferAnalysisError(
            "player_out_ids must be a list"
        )

    transfers = []

    for player_out_id in player_out_ids:
        recommendation = analyze_transfer_recommendation(
            team,
            predictions,
            player_out_id=player_out_id,
            budget=budget,
        )

        transfers.append(
            {
                "player_out_id": player_out_id,
                "player_in_id": recommendation[
                    "recommended_player_id"
                ],
                "player_in": recommendation[
                    "recommended_player"
                ],
                "predicted_gain": float(
                    recommendation["predicted_gain"]
                ),
                "price": float(
                    recommendation["recommended_price"]
                ),
                "predicted_points": float(
                    recommendation[
                        "recommended_predicted_points"
                    ]
                ),
            }
        )

    transfers.sort(
        key=lambda item: item["predicted_gain"],
        reverse=True,
    )

    total_gain = sum(
        item["predicted_gain"]
        for item in transfers
    )

    alternatives = []

    for index, transfer in enumerate(transfers):
        alternatives.append(
            {
                "player_out_id": transfer[
                    "player_out_id"
                ],
                "player_in_id": transfer[
                    "player_in_id"
                ],
                "predicted_gain": transfer[
                    "predicted_gain"
                ],
            }
        )

    return {
        "transfer_count": len(transfers),
        "total_predicted_gain": float(total_gain),
        "transfers": transfers,
        "alternatives": alternatives,
    }

def analyze_transfer_decision(
    team: dict[str, Any],
    predictions: pd.DataFrame,
    free_transfers: int = 1,
    transfer_out_id: int | None = None,
    bank: float | None = None,
    hit_cost: float = 4.0,
) -> dict[str, Any]:
    """Evaluate a single transfer as a real squad decision.

    This is intentionally stricter than the legacy candidate-ranking helpers.
    It validates the current 15-man squad, evaluates same-position replacements,
    enforces affordability and the three-per-club rule after the replacement,
    and applies the FPL-style hit cost when free transfers are exhausted.
    """
    if not isinstance(free_transfers, int) or free_transfers < 0:
        raise TransferAnalysisError("free_transfers must be a non-negative integer")
    if hit_cost < 0:
        raise TransferAnalysisError("hit_cost cannot be negative")

    picks = _validate_inputs(team, predictions)
    if len(picks) != 15:
        raise TransferAnalysisError("team must contain exactly 15 picks")

    if transfer_out_id is None:
        raise TransferAnalysisError("transfer_out_id is required")

    if transfer_out_id not in {pick["player_id"] for pick in picks}:
        raise TransferAnalysisError(
            f"transfer_out_id {transfer_out_id} is not in the current team"
        )

    required_prediction_columns = {
        "player_id", "name", "position", "team", "price", "predicted_points"
    }
    missing = required_prediction_columns - set(predictions.columns)
    if missing:
        raise TransferAnalysisError(
            "predictions is missing columns: " + ", ".join(sorted(missing))
        )

    data = predictions.copy()
    data["price"] = pd.to_numeric(data["price"], errors="coerce")
    data["predicted_points"] = pd.to_numeric(
        data["predicted_points"], errors="coerce"
    )
    data = data.dropna(subset=["price", "predicted_points"])

    outgoing_rows = data[data["player_id"] == transfer_out_id]
    if outgoing_rows.empty:
        raise TransferAnalysisError(
            f"transfer_out_id {transfer_out_id} was not found in predictions"
        )

    outgoing = outgoing_rows.iloc[0]
    outgoing_pick = next(pick for pick in picks if pick["player_id"] == transfer_out_id)
    outgoing_price, selling_price_source, selling_price_known = selling_value(outgoing_pick, float(outgoing["price"]))
    outgoing_points = float(outgoing["predicted_points"])
    outgoing_position = str(outgoing["position"]).upper()
    outgoing_team = str(outgoing["team"])


    if bank is None:
        bank = float(team.get("bank", 0.0))
    else:
        try:
            bank = float(bank)
        except (TypeError, ValueError) as exc:
            raise TransferAnalysisError("bank must be a number") from exc

    if bank < 0:
        raise TransferAnalysisError("bank cannot be negative")

    owned_ids = {pick["player_id"] for pick in picks}
    owned_team_counts = {}
    for pick in picks:
        row = data[data["player_id"] == pick["player_id"]]
        if row.empty:
            raise TransferAnalysisError(
                f"current player {pick['player_id']} is missing from predictions"
            )
        club = str(row.iloc[0]["team"])
        owned_team_counts[club] = owned_team_counts.get(club, 0) + 1

    candidates = data[
        (data["position"].astype(str).str.upper() == outgoing_position)
        & (~data["player_id"].isin(owned_ids))
        & (data["player_id"] != transfer_out_id)
    ].copy()

    # Use the supplied selling value where available, and label any estimate.
    max_price = outgoing_price + bank
    candidates = candidates[candidates["price"] <= max_price + 1e-9].copy()

    # Enforce max three players from one club after the swap.
    def is_club_legal(candidate_team: str) -> bool:
        count = owned_team_counts.get(str(candidate_team), 0)
        if str(candidate_team) == outgoing_team:
            count -= 1
        return count < 3

    candidates = candidates[
        candidates["team"].map(is_club_legal)
    ].copy()

    if candidates.empty:
        raise TransferAnalysisError("No feasible transfer candidates found")

    candidates["transfer_gain"] = (
        candidates["predicted_points"] - outgoing_points
    )

    candidates = candidates.sort_values(
        ["transfer_gain", "predicted_points", "price", "player_id"],
        ascending=[False, False, True, True],
        kind="mergesort",
    ).reset_index(drop=True)

    recommended = candidates.iloc[0]
    transfer_count = 1
    transfer_hit_cost = 0.0 if free_transfers >= transfer_count else float(hit_cost)
    gross_gain = float(recommended["transfer_gain"])
    net_gain = gross_gain - transfer_hit_cost

    alternatives = []
    for _, row in candidates.iloc[1:].head(5).iterrows():
        alternatives.append({
            "player_out_id": transfer_out_id,
            "player_in_id": int(row["player_id"]),
            "player_in": row["name"],
            "predicted_gain": float(row["transfer_gain"]),
            "net_gain": float(row["transfer_gain"]) - transfer_hit_cost,
        })

    return {
        "recommended": {
            "player_out_id": transfer_out_id,
            "player_out": outgoing["name"],
            "player_in_id": int(recommended["player_id"]),
            "player_in": recommended["name"],
            "position": recommended["position"],
            "price": float(recommended["price"]),
            "predicted_points": float(recommended["predicted_points"]),
            "selling_price": outgoing_price,
            "selling_price_source": selling_price_source,
        },
        "free_transfers": free_transfers,
        "transfers_used": transfer_count,
        "selling_prices_known": selling_price_known,
        "budget_is_estimate": not selling_price_known,
        "hit_cost": transfer_hit_cost,
        "gross_gain": gross_gain,
        "net_gain": net_gain,
        "alternatives": alternatives,
    }


def _apply_transfer_plan(
    owned: pd.DataFrame,
    data: pd.DataFrame,
    transfers: list[dict[str, Any]],
    club_changes: list[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """Return the complete post-transfer squad for a transfer plan.

    Players already owned by the manager can change real-world clubs without
    counting as a normal transfer into the new club. Explicit ``club_changes``
    may be supplied by the optimizer; direct callers are also supported by
    detecting club changes between ``owned`` and ``data``.
    """
    result = owned.copy()

    for transfer in transfers:
        out_id = int(transfer["player_out_id"])
        in_id = int(transfer["player_in_id"])

        if out_id not in set(result["player_id"].astype(int)):
            raise TransferAnalysisError(
                f"transfer-out player {out_id} is not in the current squad"
            )

        result = result[result["player_id"] != out_id]

        incoming = data[data["player_id"] == in_id]
        if incoming.empty:
            raise TransferAnalysisError(
                f"transfer-in player {in_id} is missing from predictions"
            )
        result = pd.concat([result, incoming.iloc[[0]]], ignore_index=True)

    if len(result) != 15:
        raise TransferAnalysisError("transfer plan did not produce 15 players")

    positions = result["position"].astype(str).str.upper().replace({"GKP": "GK"})
    if positions.value_counts().to_dict() != {
        "GK": 2, "DEF": 5, "MID": 5, "FWD": 3
    }:
        raise TransferAnalysisError("transfer plan produced invalid position counts")

    if result["player_id"].duplicated().any():
        raise TransferAnalysisError("transfer plan contains duplicate players")

    changes = list(club_changes or [])

    # Direct callers may not have run detect_club_changes(). Compare the
    # owned snapshot with current data so an already-owned player who moved
    # clubs is represented correctly before enforcing the three-per-club rule.
    if not changes:
        owned_by_id = owned.set_index("player_id")
        current_by_id = data.set_index("player_id")

        for player_id in owned_by_id.index:
            if player_id not in current_by_id.index:
                continue

            old_club = owned_by_id.loc[player_id, "team"]
            new_club = current_by_id.loc[player_id, "team"]

            if pd.isna(old_club) or pd.isna(new_club):
                continue

            if str(old_club) != str(new_club):
                changes.append({
                    "player_id": int(player_id),
                    "old_club": old_club,
                    "new_club": new_club,
                })

    if changes:
        current_squad_records = owned[["player_id", "team"]].to_dict("records")
        resulting_records = result.to_dict("records")

        for change in changes:
            player_id = int(change["player_id"])

            if not any(
                int(player["player_id"]) == player_id
                for player in current_squad_records
            ):
                continue

            if not any(
                int(player["player_id"]) == player_id
                for player in resulting_records
            ):
                continue

            for player in current_squad_records:
                if int(player["player_id"]) == player_id:
                    player["team"] = change["old_club"]

            if validate_transfer_squad(
                current_squad=current_squad_records,
                resulting_squad=resulting_records,
                transfer_context={
                    "type": "club_change",
                    "player_id": player_id,
                    "old_club": change["old_club"],
                    "new_club": change["new_club"],
                },
            ):
                return result

    # A no-transfer plan can legitimately contain four players from one club
    # when one of the already-owned players has changed real-world clubs.
    # The squad is already owned, so this is not a new transfer into that club.
    if not transfers and result["team"].astype(str).value_counts().max() > 3:
        return result

    if result["team"].astype(str).value_counts().max() > 3:
        raise TransferAnalysisError("transfer plan violates max-three-per-club")

    return result


def optimize_transfer_plan(
    team: dict[str, Any],
    predictions: pd.DataFrame,
    previous_predictions: pd.DataFrame | None = None,
    free_transfers: int = 1,
    max_transfers: int = 1,
    bank: float | None = None,
    hit_cost: float = 4.0,
) -> dict[str, Any]:
    """Find the best feasible one- or multi-transfer plan.

    The existing SciPy MILP backend evaluates complete replacement sets with
    shared budget, position and club constraints. Multi-GW values can be
    supplied through the existing transfer-optimizer wrapper.
    """
    if not isinstance(max_transfers, int) or max_transfers < 0:
        raise TransferAnalysisError("max_transfers must be a non-negative integer")
    if not isinstance(free_transfers, int) or free_transfers < 0:
        raise TransferAnalysisError("free_transfers must be a non-negative integer")
    if max_transfers == 0:
        supplied_picks = team.get("picks", []) if isinstance(team, dict) else []
        known_sales = len(supplied_picks) == 15 and all(selling_value(pick, 0.0)[2] for pick in supplied_picks)
        return {
            "recommended": None,
            "recommended_transfers": [],
            "transfers_used": 0,
            "free_transfers": free_transfers,
            "hit_cost": 0.0,
            "gross_gain": 0.0,
            "net_gain": 0.0,
            "alternatives": [],
            "selling_prices_known": known_sales,
            "budget_is_estimate": not known_sales,
            "solver_status": "not_required",
            "optimality_known": True,
        }

    picks = _validate_inputs(team, predictions)
    if len(picks) != 15:
        raise TransferAnalysisError("team must contain exactly 15 picks")

    data = predictions.copy()
    required = {"player_id", "name", "position", "team", "price", "predicted_points"}
    missing = required - set(data.columns)
    if missing:
        raise TransferAnalysisError(
            "predictions is missing columns: " + ", ".join(sorted(missing))
        )

    data["price"] = pd.to_numeric(data["price"], errors="coerce")
    data["predicted_points"] = pd.to_numeric(data["predicted_points"], errors="coerce")
    data = data.dropna(subset=["price", "predicted_points"]).copy()
    data["position"] = data["position"].astype(str).str.upper().replace({"GKP": "GK"})

    owned_ids = {int(p["player_id"]) for p in picks}
    owned = data[data["player_id"].isin(owned_ids)].copy()
    if len(owned) != 15:
        missing_ids = owned_ids - set(int(x) for x in owned["player_id"])
        raise TransferAnalysisError(
            "current players missing from predictions: "
            + ", ".join(map(str, sorted(missing_ids)))
        )

    club_changes = []
    if previous_predictions is not None:
        previous_data = previous_predictions.copy()

        required_previous = {"player_id", "team"}
        missing_previous = required_previous - set(previous_data.columns)
        if missing_previous:
            raise TransferAnalysisError(
                "previous_predictions is missing columns: "
                + ", ".join(sorted(missing_previous))
            )

        club_changes = detect_club_changes(
            current_squad=[
                {"player_id": int(player_id)}
                for player_id in owned_ids
            ],
            previous_predictions=previous_data.to_dict("records"),
            current_predictions=data.to_dict("records"),
        )
    if bank is None:
        bank = float(team.get("bank", 0.0))
    bank = float(bank)
    if bank < 0:
        raise TransferAnalysisError("bank cannot be negative")

    base_points = float(owned["predicted_points"].sum())
    pick_by_id = {int(pick["player_id"]): pick for pick in picks}
    sales = {
        int(row["player_id"]): selling_value(pick_by_id[int(row["player_id"])], float(row["price"]))
        for _, row in owned.iterrows()
    }
    selling_prices_known = all(value[2] for value in sales.values())
    data = data.sort_values("player_id", kind="stable").reset_index(drop=True)
    if data["player_id"].duplicated().any():
        raise TransferAnalysisError("predictions must contain unique player IDs")
    expected_positions = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
    if owned["position"].value_counts().to_dict() != expected_positions:
        raise TransferAnalysisError("team must contain 2 GK, 5 DEF, 5 MID and 3 FWD")
    n = len(data)
    # Selected owned players cost their sale value: retaining them is not a
    # repurchase. New players cost the current market price. This is equivalent
    # to bank + proceeds from only those players actually sold.
    costs = np.array([
        sales[int(row["player_id"])][0] if int(row["player_id"]) in owned_ids else float(row["price"])
        for _, row in data.iterrows()
    ])
    newcomers = (~data["player_id"].isin(owned_ids)).astype(float).to_numpy()
    points = data["predicted_points"].to_numpy(dtype=float)
    constraints = [
        LinearConstraint(np.r_[np.ones(n), 0.0], 15, 15),
        LinearConstraint(np.r_[costs, 0.0], -np.inf, bank + sum(sale[0] for sale in sales.values())),
        LinearConstraint(np.r_[newcomers, 0.0], 0, min(max_transfers, 15)),
        LinearConstraint(np.r_[newcomers, -1.0], -np.inf, free_transfers),
    ]
    for position, count in expected_positions.items():
        constraints.append(LinearConstraint(np.r_[(data["position"] == position).astype(float), 0.0], count, count))
    for club in data["team"].astype(str).unique():
        constraints.append(LinearConstraint(np.r_[(data["team"].astype(str) == club).astype(float), 0.0], 0, 3))

    # The extra integer variable represents paid transfers. A small secondary
    # preference retains the existing rule that a positive gross gain wins a
    # tie in net gain; transfer count and player IDs make further ties stable.
    objective = np.r_[-points * (1.0 + 1e-7) + newcomers * 1e-9, hit_cost]
    all_plans = []
    solver_status = "optimal"
    optimality_known = False
    alternatives_complete = True
    by_id = data.set_index("player_id")
    # Only six ranked solutions are consumed by callers. Exclusion constraints
    # find those alternatives without enumerating outgoing subsets or products.
    for _ in range(6):
        solution = milp(
            c=objective,
            integrality=np.ones(n + 1),
            bounds=Bounds(np.zeros(n + 1), np.r_[np.ones(n), 15.0]),
            constraints=constraints,
            options={"disp": False, "time_limit": 2.0},
        )
        if not solution.success:
            status = {1: "time_limit", 2: "infeasible", 3: "unbounded"}.get(solution.status, "solver_error")
            alternatives_complete = solution.status == 2
            if not all_plans:
                solver_status = status
                optimality_known = solution.status == 2
            break
        optimality_known = True
        selected_mask = solution.x[:n] >= 0.5
        selected_ids = set(data.loc[selected_mask, "player_id"].astype(int))
        out_ids = owned_ids - selected_ids
        in_ids = selected_ids - owned_ids
        transfers = []
        for position in expected_positions:
            outs = sorted(pid for pid in out_ids if by_id.loc[pid, "position"] == position)
            ins = sorted(pid for pid in in_ids if by_id.loc[pid, "position"] == position)
            for out_id, in_id in zip(outs, ins, strict=True):
                outgoing, incoming = by_id.loc[out_id], by_id.loc[in_id]
                sale, sale_source, _ = sales[out_id]
                transfers.append({
                    "player_out_id": out_id, "player_out": outgoing["name"],
                    "player_in_id": in_id, "player_in": incoming["name"],
                    "position": position, "price": float(incoming["price"]),
                    "predicted_points": float(incoming["predicted_points"]),
                    "gain": float(incoming["predicted_points"] - outgoing["predicted_points"]),
                    "selling_price": sale, "selling_price_source": sale_source,
                })
        gross = float(sum(transfer["gain"] for transfer in transfers))
        cost = float(max(0, len(transfers) - free_transfers) * hit_cost)
        all_plans.append({"count": len(transfers), "transfers": transfers, "gross": gross, "hit_cost": cost, "net": gross - cost})
        constraints.append(LinearConstraint(np.r_[selected_mask.astype(float), 0.0], 0, 14))

    # No feasible positive/neutral move is still a valid "roll" decision.
    roll = {
        "count": 0,
        "transfers": [],
        "gross": 0.0,
        "hit_cost": 0.0,
        "net": 0.0,
    }
    all_plans.append(roll)

    all_plans.sort(
        key=lambda p: (
            p["net"],
            p["gross"],
            -p["count"],
            tuple(
                (x["player_in_id"], x["player_out_id"])
                for x in p["transfers"]
            ),
        ),
        reverse=True,
    )
    best = all_plans[0]

    alternatives = []
    seen = {tuple(sorted((x["player_out_id"], x["player_in_id"]) for x in best["transfers"]))}
    for plan in all_plans[1:]:
        key = tuple(
            sorted((x["player_out_id"], x["player_in_id"]) for x in plan["transfers"])
        )
        if key in seen:
            continue
        seen.add(key)
        alternatives.append({
            "transfers": plan["transfers"],
            "transfers_used": plan["count"],
            "gross_gain": plan["gross"],
            "hit_cost": plan["hit_cost"],
            "net_gain": plan["net"],
        })
        if len(alternatives) >= 5:
            break

    transfers = best["transfers"]
    post_transfer_squad = _apply_transfer_plan(owned, data, transfers, club_changes)
    return {
        "recommended": transfers[0] if len(transfers) == 1 else None,
        "recommended_transfers": transfers,
        "transfers_used": best["count"],
        "free_transfers": free_transfers,
        "selling_prices_known": selling_prices_known,
        "budget_is_estimate": not selling_prices_known,
        "solver_status": solver_status,
        "optimality_known": optimality_known,
        "alternatives_complete": alternatives_complete,
        "optimization_warning": None if optimality_known else "Transfer search did not finish; the best plan is unknown.",
        "hit_cost": best["hit_cost"],
        "gross_gain": best["gross"],
        "net_gain": best["net"],
        "alternatives": alternatives,
        "base_projected_points": base_points,
        "projected_points_after_transfers": base_points + best["gross"],
        "post_transfer_squad": [
            {
                "player_id": int(row["player_id"]),
                "name": row["name"],
                "position": row["position"],
                "team": row["team"],
                "price": float(row["price"]),
                "predicted_points": float(row["predicted_points"]),
            }
            for _, row in post_transfer_squad.sort_values("player_id").iterrows()
        ],
    }
