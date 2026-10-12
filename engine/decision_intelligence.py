from __future__ import annotations
from typing import Any, Mapping
import pandas as pd
from optimizer.chip_optimizer import evaluate_chip_scenarios

from engine.decision_horizon import (
    normalize_horizon_predictions,
    player_horizon_projection,
    evaluate_transfer_horizon,
)
from engine.decision_risk import squad_health, risk_adjusted_points
from engine.decision_strategy import (
    MINUTES_DOUBT_START_PROBABILITY,
    chip_advisor,
    chip_outlook,
    classify_action,
    decision_confidence,
)

# Expected-points gap below which two captain options count as equal.
CAPTAIN_TIE_BAND = 0.3


def _captain_score(row: Mapping[str, Any]) -> float:
    """The armband's expected value: the player's projected points.

    Projected points already include expected minutes and the official
    availability multiplier, so neither is discounted again here (the old
    score penalised a doubtful player two or three times). A captain who does
    not play passes the armband to the vice, which caps the downside further.
    """
    return max(0.0, float(row.get("predicted_points", 0.0) or 0.0))


def _actual_gameweeks(predictions_by_gw: Mapping[int, pd.DataFrame]) -> list[int]:
    events = []
    for horizon_index, frame in sorted(predictions_by_gw.items()):
        if "gameweek" in frame.columns:
            actual = pd.to_numeric(frame["gameweek"], errors="coerce").dropna()
            if not actual.empty:
                events.append(int(actual.iloc[0]))
                continue
        events.append(int(horizon_index))
    return events

def captain_intelligence(starting_xi: pd.DataFrame, top_n: int = 5) -> dict[str, Any]:
    if not isinstance(starting_xi, pd.DataFrame) or len(starting_xi) < 2:
        raise ValueError("starting_xi must contain at least two players")
    rows = []
    for _, row in starting_xi.iterrows():
        record = row.to_dict()
        record["captain_score"] = round(_captain_score(record), 3)
        rows.append(record)
    rows.sort(key=lambda r: (-float(r["captain_score"]), int(r["player_id"])))
    # Projections are not precise to a few tenths of a point. Within that
    # band the armband goes to the surer starter: same expected value, less
    # chance the captaincy falls to the vice.
    def start(r):
        value = r.get("start_probability")
        return float(value) if value is not None and value == value else 1.0
    best = rows[0]
    for row in rows[1:]:
        if float(best["captain_score"]) - float(row["captain_score"]) > CAPTAIN_TIE_BAND:
            break
        if start(row) > start(best) + 0.05:
            best = row
    rows.remove(best)
    rows.insert(0, best)
    def public(r):
        return {
            k: r.get(k) for k in (
                "player_id", "name", "predicted_points", "captain_score",
                "team", "xmins", "start_probability", "availability", "difficulty",
            )
        }
    return {
        "captain": public(rows[0]),
        "vice_captain": public(rows[1]),
        "alternatives": [public(r) for r in rows[2:top_n]],
    }

def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def _moves(item: Mapping[str, Any]) -> list[dict[str, Any]]:
    transfers = item.get("transfers", item.get("recommended_transfers"))
    if not isinstance(transfers, list):
        return []
    return [
        dict(x) for x in transfers
        if isinstance(x, Mapping)
        and x.get("player_out_id") is not None
        and x.get("player_in_id") is not None
    ]


def _with_player_detail(
    moves: list[dict[str, Any]],
    predictions_by_gw: Mapping[int, pd.DataFrame],
    horizon: int,
) -> tuple[list[dict[str, Any]], float]:
    """Attach each moved player's per-Gameweek projection for display.

    The detail explains a decision; it never changes it. The plan's value is
    the canonical lineup gain from the action planner.
    """
    if not moves:
        return [], 1.0
    detail = evaluate_transfer_horizon(moves, predictions_by_gw, horizon)
    rows = []
    for move, extra in zip(moves, detail["transfers"]):
        rows.append({
            **move,
            "in_projection": extra["in_projection"],
            "out_projection": extra["out_projection"],
            "player_horizon_difference": extra["horizon_gain"],
        })
    return rows, detail["coverage"]


def _option_view(
    option: Mapping[str, Any],
    predictions_by_gw: Mapping[int, pd.DataFrame],
    horizon: int,
    free_transfers: int,
) -> dict[str, Any]:
    moves, coverage = _with_player_detail(_moves(option), predictions_by_gw, horizon)
    count = int(option.get("transfers_used", len(moves)) or 0)
    hit = _number(option.get("hit_cost"))
    net = _number(option.get("net_gain"), _number(option.get("gross_gain")) - hit)
    score = _number(option.get("decision_score"), net)
    return {
        "action": classify_action(count, hit),
        "transfers": moves,
        "transfers_used": count,
        "next_gw_gain": option.get("next_gw_gain"),
        "horizon_gain": round(_number(option.get("gross_gain")), 3),
        "projected_gain": option.get("projected_gain"),
        "projected_net_gain": option.get("projected_net_gain"),
        "hit_cost": round(hit, 3),
        "net_gain": round(net, 3),
        "roll_value_forgone": round(_number(option.get("roll_value_forgone")), 3),
        "risk_margin": round(_number(option.get("risk_margin")), 3),
        "decision_score": round(score, 3),
        # Deprecated aliases kept for older clients.
        "combined_score": round(score, 3),
        "current_net_gain": round(net, 3),
        "uncertainty": option.get("uncertainty"),
        "coverage": coverage,
        "free_transfers_left": max(0, free_transfers - count),
    }


def _names(moves: list[Mapping[str, Any]]) -> str:
    return ", ".join(f"{m.get('player_out', m['player_out_id'])} → {m.get('player_in', m['player_in_id'])}" for m in moves)


def _signed(value: Any) -> str:
    number = _number(value)
    return f"{number:+.1f}"


def _insights(
    action: str,
    strategy: Mapping[str, Any],
    health: Mapping[str, Any],
    captain: Mapping[str, Any],
    horizon: Mapping[str, Any],
    chips: Mapping[str, Any],
    weeks: int,
    timing_plan: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []
    chosen_moves = strategy.get("selected_transfers") or []
    runner_up = (strategy.get("alternatives") or [None])[0]
    evidence = {
        "next_gw_gain": strategy.get("next_gw_gain"),
        "horizon_gain": strategy.get("horizon_gain"),
        "hit_cost": strategy.get("hit_cost"),
        "net_gain": strategy.get("net_gain"),
        "roll_value_forgone": strategy.get("roll_value_forgone"),
        "decision_score": strategy.get("decision_score"),
    }
    if not chosen_moves:
        if runner_up and runner_up.get("transfers"):
            reason = (
                f"Hold and roll. The best move found ({_names(runner_up['transfers'])}) adds "
                f"{_signed(runner_up.get('horizon_gain'))} weighted points over {weeks} Gameweeks"
                + (f" after a {runner_up['hit_cost']:.0f}-point hit" if runner_up.get("hit_cost") else "")
                + f", which does not beat keeping the free transfer (worth {_number(runner_up.get('roll_value_forgone')):.1f})."
            )
            evidence = {**evidence, "best_move": runner_up["transfers"], "best_move_score": runner_up.get("decision_score")}
            if (timing_plan and timing_plan.get("selection_policy") == "conservative"
                    and timing_plan.get("optimality_known")
                    and timing_plan.get("recommended_transfers_now") == 0
                    and _number(runner_up.get("decision_score")) > 0):
                hold_sequence = next((sequence for sequence in timing_plan.get("sequences", [])
                                      if sequence.get("recommended") and sequence.get("transfers_now") == 0), None)
                if hold_sequence:
                    reason = (
                        f"Hold and roll. The best immediate move ({_names(runner_up['transfers'])}) has a positive "
                        f"weighted decision score ({_signed(runner_up.get('decision_score'))}). "
                        f"The conservative continuation plan prefers waiting, with "
                        f"{hold_sequence['free_transfers_next']} free transfers available next week."
                    )
                    evidence = {**evidence, "selection_policy": "conservative",
                                "baseline": timing_plan.get("baseline"),
                                "free_transfers_next": hold_sequence["free_transfers_next"]}
        else:
            reason = "Hold and roll: no legal move improves the projected lineup."
        insights.append({"type": "TRANSFER", "severity": "INFO", "reason": reason, "evidence": evidence})
    else:
        reason = (
            f"{_names(chosen_moves)}: {_signed(strategy.get('next_gw_gain'))} next Gameweek and "
            f"{_signed(strategy.get('horizon_gain'))} weighted points over {weeks} Gameweeks for your best XI and captain"
        )
        if _number(strategy.get("hit_cost")):
            reason += f", after a {strategy['hit_cost']:.0f}-point hit"
        if _number(strategy.get("roll_value_forgone")):
            reason += f"; worth more than rolling the free transfer ({_number(strategy.get('roll_value_forgone')):.1f})"
        insights.append({"type": "TRANSFER", "severity": "ACTION", "reason": reason + ".", "evidence": evidence})
    if chips.get("recommended_chip"):
        insights.append({"type": "CHIP", "severity": "ACTION", "reason": chips.get("reason", ""),
                         "evidence": {"chip": chips["recommended_chip"], "score": chips.get("score")}})
    if health.get("status") != "HEALTHY":
        insights.append({
            "type": "SQUAD_HEALTH",
            "severity": "WARNING",
            "reason": "Availability or minutes risk is elevated in the current squad.",
            "evidence": {
                "unavailable_count": health.get("unavailable_count", 0),
                "high_risk_count": health.get("high_risk_count", 0),
            },
        })
    pick, vice = captain.get("captain", {}), captain.get("vice_captain", {})
    insights.append({
        "type": "CAPTAIN",
        "severity": "INFO",
        "reason": (
            f"Captain {pick.get('name')} ({_number(pick.get('predicted_points')):.1f} xP); "
            f"vice {vice.get('name')} ({_number(vice.get('predicted_points')):.1f} xP). "
            "Ranked on projected points, adjusted for expected minutes, availability and fixture."
        ),
        "evidence": pick,
    })
    if horizon.get("coverage", 1.0) < 1.0:
        insights.append({
            "type": "DATA_COVERAGE",
            "severity": "WARNING",
            "reason": "The requested multi-Gameweek horizon is only partially populated with prediction data.",
            "evidence": {"coverage": horizon.get("coverage", 0.0)},
        })
    return insights


def _minutes_doubts(moves: list[Mapping[str, Any]], predictions: pd.DataFrame) -> list[str]:
    if "start_probability" not in predictions.columns:
        return []
    starts = dict(zip(pd.to_numeric(predictions["player_id"], errors="coerce"),
                      pd.to_numeric(predictions["start_probability"], errors="coerce")))
    doubts = []
    for move in moves:
        probability = starts.get(int(move["player_in_id"]))
        if probability is not None and probability == probability and probability < MINUTES_DOUBT_START_PROBABILITY:
            doubts.append(f"{move.get('player_in', move['player_in_id'])} starts with {probability:.0%} probability")
    return doubts


def build_intelligence(
    *,
    current_team: Mapping[str, Any],
    predictions: pd.DataFrame,
    starting_xi: pd.DataFrame,
    transfer_result: Mapping[str, Any],
    optimal_squad: pd.DataFrame | None = None,
    horizon_predictions: Mapping[int, pd.DataFrame] | None = None,
    horizon: int = 3,
    chip_state: Mapping[str, Any] | None = None,
    manager_picks: list[dict[str, Any]] | None = None,
    owned_starting_xi: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Explain the canonical decision; never choose a different one.

    `starting_xi` is the lineup the plan recommends (after its transfers);
    the captain is chosen from it. `owned_starting_xi` (default: the same)
    is the owned squad's lineup that chip values are measured against.

    `transfer_result` is the action planner's output (via
    `transfer_analysis.optimize_transfer_plan`). Its chosen action and its
    transfers are reported as-is in `transfer_strategy`, so every part of the
    response names the same move.
    """
    predictions_by_gw = normalize_horizon_predictions(predictions, horizon_predictions, horizon)
    team_players = list(current_team.get("players", []))
    health = squad_health(team_players)
    captain = captain_intelligence(starting_xi)

    horizon_team = [
        player_horizon_projection(int(p["player_id"]), predictions_by_gw, horizon)
        for p in team_players
    ]

    state = dict(chip_state or {
        "known": False,
        "wildcard_available": False,
        "free_hit_available": False,
        "bench_boost_available": False,
        "triple_captain_available": False,
        "used_in_period": [],
    })
    free_transfers = int(transfer_result.get("free_transfers", state.get("free_transfers", 1)) or 0)

    chosen = _option_view({**transfer_result, "transfers": transfer_result.get("recommended_transfers", [])},
                          predictions_by_gw, horizon, free_transfers)
    alternatives = [
        _option_view(option, predictions_by_gw, horizon, free_transfers)
        for option in transfer_result.get("alternatives", []) or []
        if isinstance(option, Mapping)
    ]
    options = [
        _option_view(option, predictions_by_gw, horizon, free_transfers)
        for option in transfer_result.get("options_by_transfer_count", []) or []
        if isinstance(option, Mapping)
    ]
    transfer_action = transfer_result.get("action") or chosen["action"]
    transfer_block = {
        "action": transfer_action,
        "selected_transfers": chosen["transfers"],
        "transfers_used": chosen["transfers_used"],
        "next_gw_gain": chosen["next_gw_gain"],
        "horizon_gain": chosen["horizon_gain"],
        "projected_gain": chosen["projected_gain"],
        "projected_net_gain": chosen["projected_net_gain"],
        "hit_cost": chosen["hit_cost"],
        "net_gain": chosen["net_gain"],
        "roll_value_forgone": chosen["roll_value_forgone"],
        "risk_margin": chosen["risk_margin"],
        "decision_score": chosen["decision_score"],
        "combined_score": chosen["decision_score"],
        "current_net_gain": chosen["net_gain"],
        "gross_gain": chosen["horizon_gain"],
        "uncertainty": chosen["uncertainty"],
        "coverage": chosen["coverage"],
        "alternatives": alternatives,
        "options_by_transfer_count": options,
        "gain_basis": transfer_result.get("gain_basis", "weighted_horizon_lineup"),
        "horizon_weights": transfer_result.get("horizon_weights"),
        "policy": transfer_result.get("policy"),
    }

    confidence = decision_confidence(
        {**chosen, "decision_score": chosen["decision_score"]},
        alternatives[0] if alternatives else None,
        minutes_doubts=_minutes_doubts(chosen["transfers"], predictions),
    )

    wildcard = transfer_result.get("wildcard") if isinstance(transfer_result.get("wildcard"), Mapping) else None
    wildcard_signal = {
        "available": bool(state.get("wildcard_available", False)),
        "evaluated": bool(wildcard and wildcard.get("evaluated")),
        **({key: wildcard.get(key) for key in (
            "rebuild_gain", "best_action_score", "advantage", "threshold", "players_changed", "recommended",
        )} if wildcard else {"recommended": False}),
    }
    wildcard_signal["recommended"] = bool(wildcard_signal["available"] and wildcard_signal.get("recommended"))

    current_frame = pd.DataFrame(team_players)
    # Chip gains are measured against the owned XI and captain this plan
    # recommends, so the chip numbers match the lineup the manager is shown.
    chip_lineup = owned_starting_xi if owned_starting_xi is not None else starting_xi
    chip_xi_ids = [int(player_id) for player_id in chip_lineup["player_id"]]
    chip_captain_id = int(captain_intelligence(chip_lineup)["captain"]["player_id"])
    if manager_picks:
        picks_by_id = {int(pick["player_id"]): pick for pick in manager_picks}
        for field in ("purchase_price", "selling_price", "selling_price_source"):
            supplied = current_frame["player_id"].map(lambda player_id: picks_by_id.get(int(player_id), {}).get(field))
            if supplied.notna().any():
                current_frame[field] = supplied
    chip_scenarios = evaluate_chip_scenarios(
        current_frame,
        predictions,
        available_chips={
            # The Wildcard is evaluated by the action planner over the horizon.
            "WILDCARD": False,
            "FREE_HIT": bool(state.get("free_hit_available", False)),
            "BENCH_BOOST": bool(state.get("bench_boost_available", False)),
            "TRIPLE_CAPTAIN": bool(state.get("triple_captain_available", False)),
        },
        double_gameweek=bool(state.get("double_gameweek", False)),
        blank_gameweek=bool(state.get("blank_gameweek", False)),
        bank=float(current_team.get("bank") or 0.0),
        starting_xi_ids=chip_xi_ids,
        captain_id=chip_captain_id,
    )
    chips = chip_advisor(
        wildcard_available=bool(state.get("wildcard_available", False)),
        free_hit_available=bool(state.get("free_hit_available", False)),
        bench_boost_available=bool(state.get("bench_boost_available", False)),
        triple_captain_available=bool(state.get("triple_captain_available", False)),
        wildcard_signal=wildcard_signal,
        scenario_scores={item["chip"]: float(item["score"]) for item in chip_scenarios.get("scenarios", [])},
        double_gameweek=bool(state.get("double_gameweek", False)),
        blank_gameweek=bool(state.get("blank_gameweek", False)),
    )
    # One recommendation: the scenario table reports values, the advisor decides.
    chip_scenarios["recommended_chip"] = chips["recommended_chip"]
    chip_scenarios["score"] = chips["score"]
    chip_scenarios["lineup_source"] = "recommended_owned_lineup"

    action = chips["recommended_chip"] if chips["recommended_chip"] in {"WILDCARD", "FREE_HIT"} else transfer_action

    risk_details = [
        risk_adjusted_points(player) | {
            "player_id": int(player["player_id"]),
            "name": player.get("name"),
        }
        for player in team_players
    ]
    risk_scores = [x["risk_score"] for x in risk_details]
    risk_summary = {
        "average_risk": round(sum(risk_scores) / len(risk_scores), 3) if risk_scores else 0.0,
        "high_risk_players": sum(1 for x in risk_details if x["risk_score"] >= 0.45),
        "players": sorted(risk_details, key=lambda x: (-x["risk_score"], x["player_id"])),
    }

    team_projection = sum(
        float(x["predicted_points"])
        for x in horizon_team
        if x["gameweeks"]
    )
    coverage = (
        sum(x["coverage"] for x in horizon_team) / len(horizon_team)
        if horizon_team else 0.0
    )

    horizon_block = {
        "horizon": horizon,
        "gameweeks": _actual_gameweeks(predictions_by_gw),
        "coverage": round(coverage, 3),
        "team_projected_points": round(team_projection, 3),
        "captain_projection": player_horizon_projection(
            int(captain["captain"]["player_id"]),
            predictions_by_gw,
            horizon,
        ),
        "team_player_projections": sorted(
            horizon_team,
            key=lambda x: (-x["predicted_points"], x["player_id"]),
        ),
    }

    return {
        "action": action,
        "transfer_action": transfer_action,
        "confidence": confidence,
        "captain_decision": captain,
        "squad_health": health,
        "horizon": horizon_block,
        "transfer_strategy": transfer_block,
        "chip_advisor": chips,
        "chip_outlook": chip_outlook(
            state=state,
            advisor=chips,
            wildcard_signal=wildcard_signal,
            scenario_scores={item["chip"]: float(item["score"]) for item in chip_scenarios.get("scenarios", [])},
            horizon_team=horizon_team,
            starter_ids=chip_xi_ids,
            names={int(p["player_id"]): str(p.get("name") or "") for p in team_players if p.get("player_id") is not None},
        ),
        "chip_state": state,
        "chip_scenarios": chip_scenarios,
        "risk_summary": risk_summary,
        "wildcard_signal": wildcard_signal,
        "insights": _insights(
            action, transfer_block, health, captain, horizon_block, chips, len(predictions_by_gw),
            transfer_result.get("two_week")
        ),
    }
