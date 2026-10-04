from __future__ import annotations
from typing import Any, Mapping
import pandas as pd
from optimizer.chip_optimizer import evaluate_chip_scenarios

from decision_horizon import (
    normalize_horizon_predictions,
    player_horizon_projection,
    evaluate_transfer_horizon,
)
from decision_risk import player_risk, squad_health, risk_adjusted_points
from decision_strategy import (
    choose_transfer_action,
    confidence_score,
    transfer_pressure,
    chip_advisor,
)

def _captain_score(row: Mapping[str, Any]) -> float:
    points = max(0.0, float(row.get("predicted_points", 0.0) or 0.0))
    start = max(0.0, min(1.0, float(row.get("start_probability", 1.0) or 0.0)))
    availability = str(row.get("availability", "AVAILABLE")).upper()
    availability_factor = {
        "AVAILABLE": 1.0, "NEWS": .92, "MINOR_RISK": .82,
        "RISK": .65, "MAJOR_RISK": .45, "UNAVAILABLE": 0.0,
    }.get(availability, .85)
    difficulty = float(row.get("difficulty", 3.0) or 3.0)
    fixture_factor = max(.85, min(1.10, 1.10 - (difficulty - 1.0) * .05))
    return points * (.55 + .45 * start) * availability_factor * fixture_factor


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
    rows.sort(key=lambda r: (
        -float(r["captain_score"]),
        -float(r.get("predicted_points", 0.0) or 0.0),
        int(r["player_id"]),
    ))
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

def _transfer_plan_from_item(item: Mapping[str, Any]) -> list[dict[str, Any]]:
    transfers = item.get("transfers")
    if not isinstance(transfers, list):
        return []
    return [
        x for x in transfers
        if isinstance(x, Mapping)
        and x.get("player_out_id") is not None
        and x.get("player_in_id") is not None
    ]

def _horizon_candidate(
    transfers: list[dict[str, Any]],
    current_net: float,
    predictions_by_gw: Mapping[int, pd.DataFrame],
    horizon: int,
) -> dict[str, Any]:
    future = evaluate_transfer_horizon(transfers, predictions_by_gw, horizon)
    # Keep the named transfer rows (name, price, position) and add the
    # per-transfer horizon detail to them, rather than replacing them.
    detailed = [{**transfer, **detail} for transfer, detail in zip(transfers, future["transfers"])]
    return {
        **future,
        "transfers": detailed,
        "current_net_gain": current_net,
        "combined_score": current_net + future["horizon_gain"],
    }

def _select_horizon_transfer(
    transfer_result: Mapping[str, Any],
    predictions_by_gw: Mapping[int, pd.DataFrame],
    horizon: int,
) -> dict[str, Any]:
    candidates = []
    best_transfers = _transfer_plan_from_item({
        "transfers": transfer_result.get("recommended_transfers", [])
    })
    if best_transfers:
        current_net = float(transfer_result.get("net_gain", 0.0))
        candidates.append(_horizon_candidate(best_transfers, current_net, predictions_by_gw, horizon))

    for alt in transfer_result.get("alternatives", []) or []:
        transfers = _transfer_plan_from_item(alt)
        if not transfers:
            continue
        current_net = float(alt.get("net_gain", alt.get("gross_gain", 0.0)) or 0.0)
        candidates.append(_horizon_candidate(transfers, current_net, predictions_by_gw, horizon))

    if not candidates:
        return {
            "selected": [],
            "horizon_gain": 0.0,
            "current_net_gain": 0.0,
            "combined_score": 0.0,
            "coverage": 0.0,
            "alternatives": [],
        }

    candidates.sort(key=lambda x: (
        -x["combined_score"],
        -x["current_net_gain"],
        len(x["transfers"]),
        tuple((int(t["player_in_id"]), int(t["player_out_id"])) for t in x["transfers"]),
    ))
    selected = candidates[0]
    return {
        "selected": selected["transfers"],
        "horizon_gain": round(selected["horizon_gain"], 3),
        "current_net_gain": round(selected["current_net_gain"], 3),
        "combined_score": round(selected["combined_score"], 3),
        "coverage": selected["coverage"],
        "alternatives": [
            {
                "transfers": x["transfers"],
                "horizon_gain": round(x["horizon_gain"], 3),
                "current_net_gain": round(x["current_net_gain"], 3),
                "combined_score": round(x["combined_score"], 3),
                "coverage": x["coverage"],
            }
            for x in candidates[1:6]
        ],
    }

def _wildcard_pressure(
    current_team: list[dict[str, Any]],
    optimal_squad: pd.DataFrame | None,
    predictions_by_gw: Mapping[int, pd.DataFrame],
    horizon: int,
) -> float:
    if optimal_squad is None or optimal_squad.empty:
        return 0.0
    current_ids = {int(p["player_id"]) for p in current_team}
    optimal_ids = {int(x) for x in optimal_squad["player_id"]}
    if not current_ids:
        return 0.0
    turnover = len(current_ids - optimal_ids) / 15.0
    return max(0.0, min(1.0, turnover * 1.5))

def _insights(
    action: str,
    transfer: Mapping[str, Any],
    health: Mapping[str, Any],
    captain: Mapping[str, Any],
    horizon: Mapping[str, Any],
) -> list[dict[str, Any]]:
    insights = []
    if action == "HOLD":
        insights.append({
            "type": "TRANSFER",
            "severity": "INFO",
            "reason": "No transfer clears the tested decision threshold after costs and available evidence.",
            "evidence": {
                "net_gain": transfer.get("net_gain", 0.0),
                "horizon_gain": transfer.get("horizon_gain", 0.0),
            },
        })
    else:
        insights.append({
            "type": "TRANSFER",
            "severity": "ACTION",
            "reason": "The selected transfer plan has the strongest combined current and horizon value among evaluated plans.",
            "evidence": {
                "net_gain": transfer.get("net_gain", 0.0),
                "horizon_gain": transfer.get("horizon_gain", 0.0),
            },
        })
    if health.get("status") != "HEALTHY":
        insights.append({
            "type": "SQUAD_HEALTH",
            "severity": "WARNING",
            "reason": "Availability or rotation risk is elevated in the current squad.",
            "evidence": {
                "unavailable_count": health.get("unavailable_count", 0),
                "high_risk_count": health.get("high_risk_count", 0),
            },
        })
    insights.append({
        "type": "CAPTAIN",
        "severity": "INFO",
        "reason": "Captain ranking combines predicted points with expected minutes, availability and fixture difficulty.",
        "evidence": captain.get("captain", {}),
    })
    if horizon.get("coverage", 1.0) < 1.0:
        insights.append({
            "type": "DATA_COVERAGE",
            "severity": "WARNING",
            "reason": "The requested multi-Gameweek horizon is only partially populated with prediction data.",
            "evidence": {"coverage": horizon.get("coverage", 0.0)},
        })
    return insights

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
) -> dict[str, Any]:
    predictions_by_gw = normalize_horizon_predictions(predictions, horizon_predictions, horizon)
    team_players = list(current_team.get("players", []))
    health = squad_health(team_players)
    captain = captain_intelligence(starting_xi)

    horizon_team = [
        player_horizon_projection(int(p["player_id"]), predictions_by_gw, horizon)
        for p in team_players
    ]
    pressure = []
    for player, projection in zip(team_players, horizon_team):
        pressure.append({
            "player_id": int(player["player_id"]),
            "name": player.get("name"),
            "pressure": round(transfer_pressure(player, projection), 3),
        })
    pressure.sort(key=lambda x: (-x["pressure"], x["player_id"]))
    max_pressure = pressure[0]["pressure"] if pressure else 0.0

    horizon_transfer = _select_horizon_transfer(
        transfer_result, predictions_by_gw, horizon
    )

    transfer_net = float(transfer_result.get("net_gain", 0.0) or 0.0)
    transfer_gross = float(transfer_result.get("gross_gain", 0.0) or 0.0)
    hit_cost = float(transfer_result.get("hit_cost", 0.0) or 0.0)
    transfers_used = int(transfer_result.get("transfers_used", 0) or 0)

    avg_risk = (
        sum(player_risk(p)["score"] for p in team_players) / len(team_players)
        if team_players else 0.0
    )
    confidence = confidence_score(
        decision_margin=min(1.0, abs(transfer_net) / 6.0),
        minutes_certainty=max(0.0, 1.0 - avg_risk),
        fixture_certainty=horizon_transfer.get("coverage", 1.0),
        signal_agreement=1.0 if (
            transfer_net > 0 and horizon_transfer.get("horizon_gain", 0.0) >= 0
        ) or transfer_net <= 0 else 0.5,
    )

    action = choose_transfer_action(
        transfer_net,
        transfer_gross,
        transfers_used,
        horizon_gain=float(horizon_transfer.get("horizon_gain", 0.0)),
        confidence=confidence["score"],
        transfer_pressure=max_pressure,
        hit_cost=hit_cost,
    )

    wildcard_pressure = _wildcard_pressure(
        team_players, optimal_squad, predictions_by_gw, horizon
    )
    state = dict(chip_state or {
        "known": False,
        "wildcard_available": False,
        "free_hit_available": False,
        "bench_boost_available": False,
        "triple_captain_available": False,
        "used_in_period": [],
    })
    chips = chip_advisor(
        free_transfers=int(state.get("free_transfers", 1)),
        net_gain=transfer_net,
        squad_health_status=health["status"],
        wildcard_available=bool(state.get("wildcard_available", False)),
        free_hit_available=bool(state.get("free_hit_available", False)),
        bench_boost_available=bool(state.get("bench_boost_available", False)),
        triple_captain_available=bool(state.get("triple_captain_available", False)),
        double_gameweek=bool(state.get("double_gameweek", False)),
        blank_gameweek=bool(state.get("blank_gameweek", False)),
        wildcard_pressure=wildcard_pressure,
    )

    current_frame = pd.DataFrame(team_players)
    # Chip gains are measured against the owned XI and captain this plan
    # recommends, so the chip numbers match the lineup the manager is shown.
    # The previous Gameweek's published picks are not this Gameweek's choice.
    chip_xi_ids = [int(player_id) for player_id in starting_xi["player_id"]]
    chip_captain_id = int(captain["captain"]["player_id"])
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
            "WILDCARD": bool(state.get("wildcard_available", False)),
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
    chip_scenarios["lineup_source"] = "recommended_owned_lineup"
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
            key=lambda x: (-x["minutes_adjusted_points"], x["player_id"]),
        ),
    }

    transfer_block = {
        "action": action,
        "current_net_gain": round(transfer_net, 3),
        "gross_gain": round(transfer_gross, 3),
        "hit_cost": round(hit_cost, 3),
        "horizon_gain": horizon_transfer["horizon_gain"],
        "combined_score": horizon_transfer["combined_score"],
        "coverage": horizon_transfer["coverage"],
        "selected_transfers": horizon_transfer["selected"],
        "alternatives": horizon_transfer["alternatives"],
        "transfer_pressure": pressure[:5],
    }

    return {
        "action": action,
        "confidence": confidence,
        "captain_decision": captain,
        "squad_health": health,
        "horizon": horizon_block,
        "transfer_strategy": transfer_block,
        "chip_advisor": chips,
        "chip_state": state,
        "chip_scenarios": chip_scenarios,
        "risk_summary": risk_summary,
        "wildcard_pressure": round(wildcard_pressure, 3),
        "insights": _insights(
            action, transfer_block, health, captain, horizon_block
        ),
    }
