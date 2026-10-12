from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd
import numpy as np

from engine.fpl_rules import detect_club_changes, validate_transfer_squad
from optimizer.action_planner import ActionPlanningError, DecisionPolicy, SolverUnavailable, build_chip_squads, evaluate_moves, plan_action


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
    *,
    horizon_predictions: Sequence[pd.DataFrame] | None = None,
    horizon_weights: Sequence[float] | None = None,
    policy: DecisionPolicy | None = None,
    evaluate_wildcard: bool = False,
) -> dict[str, Any]:
    """Choose the best Gameweek action: hold/roll, free transfers or a hit.

    This is the one transfer decision in the product. Every action from
    holding up to `max_transfers` transfers is evaluated by the canonical
    planner (`optimizer.action_planner`): complete squads under budget,
    position and club rules, valued by the starting XI and captain they can
    field in each projected Gameweek, with bench players counting only as
    autosub cover. Holding wins unless a move beats the value of rolling the
    free transfer, and a hit must beat its cost plus a margin.

    `predictions` is the target Gameweek. `horizon_predictions` optionally
    supplies the target and later Gameweeks (index 0 = target), weighted by
    `horizon_weights`.
    """
    if not isinstance(max_transfers, int) or max_transfers < 0:
        raise TransferAnalysisError("max_transfers must be a non-negative integer")
    if not isinstance(free_transfers, int) or free_transfers < 0:
        raise TransferAnalysisError("free_transfers must be a non-negative integer")
    if max_transfers == 0:
        supplied_picks = team.get("picks", []) if isinstance(team, dict) else []
        known_sales = len(supplied_picks) == 15 and all(selling_value(pick, 0.0)[2] for pick in supplied_picks)
        return {
            "action": "HOLD",
            "recommended": None,
            "recommended_transfers": [],
            "transfers_used": 0,
            "free_transfers": free_transfers,
            "hit_cost": 0.0,
            "gross_gain": 0.0,
            "net_gain": 0.0,
            "decision_score": 0.0,
            "alternatives": [],
            "options_by_transfer_count": [],
            "selling_prices_known": known_sales,
            "budget_is_estimate": not known_sales,
            "solver_status": "not_required",
            "optimality_known": True,
        }

    picks = _validate_inputs(team, predictions)
    if len(picks) != 15:
        raise TransferAnalysisError("team must contain exactly 15 picks")

    required = {"player_id", "name", "position", "team", "price", "predicted_points"}

    def prepared(frame: pd.DataFrame, label: str) -> pd.DataFrame:
        missing = required - set(frame.columns)
        if missing:
            raise TransferAnalysisError(f"{label} is missing columns: " + ", ".join(sorted(missing)))
        result = frame.copy()
        result["player_id"] = pd.to_numeric(result["player_id"], errors="coerce")
        result["price"] = pd.to_numeric(result["price"], errors="coerce")
        result["predicted_points"] = pd.to_numeric(result["predicted_points"], errors="coerce")
        result = result.dropna(subset=["player_id", "price", "predicted_points"]).copy()
        result["player_id"] = result["player_id"].astype(int)
        result["position"] = result["position"].astype(str).str.upper().replace({"GKP": "GK"})
        return result

    data = prepared(predictions, "predictions")
    if data["player_id"].duplicated().any():
        raise TransferAnalysisError("predictions must contain unique player IDs")
    frames = [data]
    if horizon_predictions:
        frames = [prepared(frame, "horizon_predictions") for frame in horizon_predictions]
        # The target Gameweek's identity, price and club come from `predictions`.
        frames[0] = data
    weights = list(horizon_weights) if horizon_weights is not None else [1.0] * len(frames)
    if len(weights) != len(frames):
        raise TransferAnalysisError("horizon_weights must match horizon_predictions")

    owned_ids = {int(p["player_id"]) for p in picks}
    owned = data[data["player_id"].isin(owned_ids)].copy()
    if len(owned) != 15:
        missing_ids = owned_ids - set(int(x) for x in owned["player_id"])
        raise TransferAnalysisError(
            "current players missing from predictions: "
            + ", ".join(map(str, sorted(missing_ids)))
        )
    expected_positions = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
    if owned["position"].value_counts().to_dict() != expected_positions:
        raise TransferAnalysisError("team must contain 2 GK, 5 DEF, 5 MID and 3 FWD")

    club_changes = []
    if previous_predictions is not None:
        previous_data = previous_predictions.copy()
        missing_previous = {"player_id", "team"} - set(previous_data.columns)
        if missing_previous:
            raise TransferAnalysisError(
                "previous_predictions is missing columns: "
                + ", ".join(sorted(missing_previous))
            )
        club_changes = detect_club_changes(
            current_squad=[{"player_id": int(player_id)} for player_id in owned_ids],
            previous_predictions=previous_data.to_dict("records"),
            current_predictions=data.to_dict("records"),
        )
    if bank is None:
        bank = float(team.get("bank", 0.0) or 0.0)
    bank = float(bank)
    if bank < 0:
        raise TransferAnalysisError("bank cannot be negative")

    pick_by_id = {int(pick["player_id"]): pick for pick in picks}
    sales = {
        int(row["player_id"]): selling_value(pick_by_id[int(row["player_id"])], float(row["price"]))
        for _, row in owned.iterrows()
    }
    selling_prices_known = all(value[2] for value in sales.values())
    base = {
        "free_transfers": free_transfers,
        "selling_prices_known": selling_prices_known,
        "budget_is_estimate": not selling_prices_known,
    }
    active_policy = policy or DecisionPolicy(hit_cost=float(hit_cost))
    try:
        plan = plan_action(
            frames,
            owned_ids=sorted(owned_ids),
            sale_info=sales,
            bank=bank,
            free_transfers=free_transfers,
            max_transfers=max_transfers,
            weights=weights,
            policy=active_policy,
            evaluate_wildcard=evaluate_wildcard,
        )
    except SolverUnavailable as exc:
        return {
            **base,
            "action": "HOLD",
            "recommended": None,
            "recommended_transfers": [],
            "transfers_used": 0,
            "hit_cost": 0.0,
            "gross_gain": 0.0,
            "net_gain": 0.0,
            "decision_score": 0.0,
            "alternatives": [],
            "options_by_transfer_count": [],
            "solver_status": exc.status,
            "optimality_known": False,
            "alternatives_complete": False,
            "optimization_warning": "Transfer search did not finish; the best plan is unknown.",
        }
    except ActionPlanningError as exc:
        raise TransferAnalysisError(str(exc)) from exc

    chosen = plan["chosen"]
    transfers = chosen["transfers"]

    def public(option: Mapping[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in option.items() if key not in {"squad"}}

    post_transfer_squad = _apply_transfer_plan(owned, data, transfers, club_changes)
    return {
        **base,
        "action": plan["action"],
        "recommended": transfers[0] if len(transfers) == 1 else None,
        "recommended_transfers": transfers,
        "transfers_used": chosen["transfers_used"],
        "hit_cost": chosen["hit_cost"],
        "gross_gain": chosen["gross_gain"],
        "net_gain": chosen["net_gain"],
        "next_gw_gain": chosen["next_gw_gain"],
        "roll_value_forgone": chosen["roll_value_forgone"],
        "risk_margin": chosen["risk_margin"],
        "decision_score": chosen["decision_score"],
        "uncertainty": chosen["uncertainty"],
        "lineup": chosen["lineup"],
        "options_by_transfer_count": [public(option) for option in plan["options_by_transfer_count"]],
        "alternatives": [public(option) for option in plan["alternatives"][:5]],
        "alternatives_complete": True,
        "max_transfers_searched": plan["max_transfers_searched"],
        "budget": plan["budget"],
        "horizon_weights": plan["weights"],
        "policy": plan["policy"],
        "wildcard": plan.get("wildcard"),
        "solver_status": plan["solver_status"],
        "optimality_known": plan["optimality_known"],
        "optimization_warning": None if plan["optimality_known"] else "Part of the transfer search hit its time limit.",
        "gain_basis": "weighted_horizon_lineup",
        "base_projected_points": plan["hold"]["lineup_value"],
        "projected_points_after_transfers": chosen["lineup_value"],
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


def evaluate_transfer_moves(
    team: dict[str, Any],
    predictions: pd.DataFrame,
    *,
    sell: Sequence[int],
    buy: Sequence[int],
    free_transfers: int,
    horizon_predictions: Sequence[pd.DataFrame] | None = None,
    horizon_weights: Sequence[float] | None = None,
    policy: DecisionPolicy | None = None,
) -> dict[str, Any]:
    """Score the manager's own transfers on the same scale as the recommendation."""
    picks = _validate_inputs(team, predictions)
    frames = list(horizon_predictions) if horizon_predictions else [predictions]
    frames = [frame.assign(position=frame["position"].astype(str).str.upper().replace({"GKP": "GK"}))
              for frame in frames]
    weights = list(horizon_weights) if horizon_weights is not None else [1.0] * len(frames)
    prices = dict(zip(pd.to_numeric(frames[0]["player_id"]).astype(int), pd.to_numeric(frames[0]["price"])))
    sales = {int(pick["player_id"]): selling_value(pick, float(prices[int(pick["player_id"])])) for pick in picks}
    try:
        result = evaluate_moves(
            frames, owned_ids=list(sales), sale_info=sales, bank=float(team.get("bank") or 0.0),
            free_transfers=free_transfers, sell=sell, buy=buy, weights=weights, policy=policy)
    except SolverUnavailable as exc:
        raise TransferAnalysisError(str(exc)) from exc
    except ActionPlanningError as exc:
        return {"legal": False, "reason": str(exc)}
    if result["legal"]:
        for key in ("option", "hold"):
            result[key] = {k: v for k, v in result[key].items() if k != "squad"}
    result["selling_prices_known"] = all(value[2] for value in sales.values())
    return result


def chip_squads(
    team: dict[str, Any],
    predictions: pd.DataFrame,
    *,
    horizon_predictions: Sequence[pd.DataFrame] | None = None,
    horizon_weights: Sequence[float] | None = None,
    policy: DecisionPolicy | None = None,
) -> dict[str, Any]:
    """The best Free Hit and Wildcard squads, on the recommendation's inputs."""
    picks = _validate_inputs(team, predictions)
    frames = list(horizon_predictions) if horizon_predictions else [predictions]
    frames = [frame.assign(position=frame["position"].astype(str).str.upper().replace({"GKP": "GK"}))
              for frame in frames]
    weights = list(horizon_weights) if horizon_weights is not None else [1.0] * len(frames)
    prices = dict(zip(pd.to_numeric(frames[0]["player_id"]).astype(int), pd.to_numeric(frames[0]["price"])))
    sales = {int(pick["player_id"]): selling_value(pick, float(prices[int(pick["player_id"])])) for pick in picks}
    try:
        result = build_chip_squads(frames, owned_ids=list(sales), sale_info=sales,
                                   bank=float(team.get("bank") or 0.0), weights=weights, policy=policy)
    except ActionPlanningError as exc:
        raise TransferAnalysisError(str(exc)) from exc
    result["selling_prices_known"] = all(value[2] for value in sales.values())
    return result
