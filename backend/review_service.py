from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import json
import re

import pandas as pd


class ReviewDataError(ValueError):
    """Raised when a trustworthy post-Gameweek review cannot be calculated."""


def select_review_prediction_file(
    predictions_dir: Path,
    event: int,
    *,
    deadline_time: str | None,
) -> Path:
    """Select the latest artifact cryptographically out of scope, but time-certified.

    A filename is not evidence that a file existed before the deadline. Each
    eligible CSV therefore needs an immutable publication sidecar created by
    the prediction publisher, and that timestamp must precede the official
    event deadline.
    """
    if not isinstance(event, int) or not 1 <= event <= 38:
        raise ValueError("event must be between 1 and 38")
    try:
        deadline = datetime.fromisoformat(
            str(deadline_time).replace("Z", "+00:00")
        ).astimezone(timezone.utc)
    except (TypeError, ValueError):
        raise ReviewDataError(f"Official deadline is unavailable for GW{event}")

    candidates: list[tuple[int, Path]] = []
    pattern = re.compile(rf"^gw{event}_predictions_v(?P<version>\d+)\.csv$")
    for path in predictions_dir.glob(f"gw{event}_predictions_v*.csv"):
        match = pattern.match(path.name)
        if match:
            candidates.append((int(match.group("version")), path))
    exact = predictions_dir / f"gw{event}_predictions.csv"
    if exact.exists():
        candidates.append((0, exact))

    eligible: list[tuple[datetime, int, Path]] = []
    for version, path in candidates:
        sidecar = path.with_suffix(path.suffix + ".manifest.json")
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            generated_at = datetime.fromisoformat(
                str(payload["generated_at"]).replace("Z", "+00:00")
            )
            if generated_at.tzinfo is None:
                raise ValueError("generated_at must be timezone-aware")
            generated_at = generated_at.astimezone(timezone.utc)
            if (
                int(payload["prediction_event"]) != event
                or str(payload["prediction_file"]) != path.name
                or int(payload["schema_version"]) != 1
                or generated_at > deadline
            ):
                continue
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        eligible.append((generated_at, version, path))

    if eligible:
        return max(eligible, key=lambda item: (item[0], item[1]))[2]
    raise ReviewDataError(f"No certified pre-deadline prediction artifact found for GW{event}")


def _round_points(value: float) -> float:
    return round(float(value), 2)


def _prediction_map(predictions: pd.DataFrame) -> dict[int, float]:
    required = {"player_id", "predicted_points"}
    missing = required - set(predictions.columns)
    if missing:
        raise ReviewDataError(
            "prediction artifact is missing columns: " + ", ".join(sorted(missing))
        )

    normalized = predictions.loc[:, ["player_id", "predicted_points"]].copy()
    normalized["player_id"] = pd.to_numeric(normalized["player_id"], errors="coerce")
    normalized["predicted_points"] = pd.to_numeric(
        normalized["predicted_points"], errors="coerce"
    )
    if normalized.isna().any(axis=None):
        raise ReviewDataError("prediction artifact contains invalid player values")
    normalized["player_id"] = normalized["player_id"].astype(int)
    if normalized["player_id"].duplicated().any():
        raise ReviewDataError("prediction artifact contains duplicate player_id values")
    return {
        int(row.player_id): float(row.predicted_points)
        for row in normalized.itertuples(index=False)
    }


def _optional_xmins_map(predictions: pd.DataFrame) -> dict[int, float]:
    """Return certified pre-deadline xMins where the artifact supplies them.

    Older certified artifacts remain reviewable, but their missing minutes
    forecast is represented explicitly by an empty map rather than inferred.
    """
    if "xmins" not in predictions.columns:
        return {}
    normalized = predictions.loc[:, ["player_id", "xmins"]].copy()
    normalized["player_id"] = pd.to_numeric(normalized["player_id"], errors="coerce")
    normalized["xmins"] = pd.to_numeric(normalized["xmins"], errors="coerce")
    normalized = normalized.dropna(subset=["player_id", "xmins"])
    if (normalized["xmins"] < 0).any():
        raise ReviewDataError("prediction artifact contains invalid xmins values")
    return {
        int(row.player_id): float(row.xmins)
        for row in normalized.itertuples(index=False)
    }


def _player_maps(
    bootstrap: dict[str, Any],
) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
    elements = bootstrap.get("elements")
    teams = bootstrap.get("teams")
    if not isinstance(elements, list) or not isinstance(teams, list):
        raise ReviewDataError("bootstrap player or team data is invalid")
    players = {
        int(item["id"]): item
        for item in elements
        if isinstance(item, dict) and item.get("id") is not None
    }
    team_map = {
        int(item["id"]): item
        for item in teams
        if isinstance(item, dict) and item.get("id") is not None
    }
    return players, team_map


def _live_points(live_payload: dict[str, Any]) -> dict[int, int]:
    elements = live_payload.get("elements")
    if not isinstance(elements, list):
        raise ReviewDataError("event live data is invalid")
    result: dict[int, int] = {}
    for item in elements:
        if not isinstance(item, dict) or item.get("id") is None:
            continue
        stats = item.get("stats") or {}
        result[int(item["id"])] = int(stats.get("total_points", 0) or 0)
    return result


def _live_minutes(live_payload: dict[str, Any]) -> dict[int, int]:
    elements = live_payload.get("elements")
    if not isinstance(elements, list):
        raise ReviewDataError("event live data is invalid")
    result: dict[int, int] = {}
    for item in elements:
        if not isinstance(item, dict) or item.get("id") is None:
            continue
        stats = item.get("stats") or {}
        if stats.get("minutes") is None:
            continue
        try:
            result[int(item["id"])] = int(stats["minutes"])
        except (TypeError, ValueError):
            continue
    return result


def _player_label(
    player_id: int,
    players: dict[int, dict[str, Any]],
    teams: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    player = players.get(player_id)
    if not player:
        raise ReviewDataError(f"bootstrap is missing player {player_id}")
    team = teams.get(int(player.get("team", 0)), {})
    return {
        "player_id": player_id,
        "name": str(player.get("web_name") or player.get("second_name") or "Unknown"),
        "team_short": str(team.get("short_name") or "UNK"),
        "position": {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}.get(
            int(player.get("element_type", 0)), "UNK"
        ),
    }


def _outcome(actual_vs_projected: float) -> str:
    if actual_vs_projected >= 5:
        return "ABOVE_EXPECTATION"
    if actual_vs_projected <= -5:
        return "BELOW_EXPECTATION"
    return "IN_LINE"


def build_post_gameweek_review(
    *,
    team_id: int,
    event: int,
    picks_payload: dict[str, Any],
    transfers: list[dict[str, Any]],
    bootstrap: dict[str, Any],
    live_payload: dict[str, Any],
    predictions: pd.DataFrame,
    prediction_version: str,
) -> dict[str, Any]:
    """Compare a manager's official result with a pre-existing model artifact."""
    if not isinstance(team_id, int) or team_id <= 0:
        raise ValueError("team_id must be a positive integer")
    if not isinstance(event, int) or not 1 <= event <= 38:
        raise ValueError("event must be between 1 and 38")

    picks = picks_payload.get("picks")
    entry_history = picks_payload.get("entry_history")
    if not isinstance(picks, list) or not picks:
        raise ReviewDataError("manager picks are unavailable")
    if not isinstance(entry_history, dict):
        raise ReviewDataError("manager entry history is unavailable")
    if int(entry_history.get("event", event)) != event:
        raise ReviewDataError("manager entry history does not match the requested event")

    prediction_by_id = _prediction_map(predictions)
    xmins_by_id = _optional_xmins_map(predictions)
    players, teams = _player_maps(bootstrap)
    actual_by_id = _live_points(live_payload)
    actual_minutes_by_id = _live_minutes(live_payload)

    selected_ids = [int(pick.get("element", 0)) for pick in picks if isinstance(pick, dict)]
    missing_predictions = sorted(
        player_id for player_id in selected_ids if player_id not in prediction_by_id
    )
    if missing_predictions:
        raise ReviewDataError(
            "missing predictions for selected players: "
            + ", ".join(str(player_id) for player_id in missing_predictions)
        )
    missing_live = sorted(player_id for player_id in selected_ids if player_id not in actual_by_id)
    if missing_live:
        raise ReviewDataError(
            "missing official event points for selected players: "
            + ", ".join(str(player_id) for player_id in missing_live)
        )

    # Public picks carry realized multipliers (including vice-captain fallback).
    # Reconstruct the selected XI for the projection instead of using hindsight.
    selected_slots = {int(pick["element"]): int(pick.get("position", 0) or 0) for pick in picks}
    for substitution in picks_payload.get("automatic_subs") or []:
        player_out = int(substitution.get("element_out", 0))
        player_in = int(substitution.get("element_in", 0))
        if selected_slots.get(player_out, 0) > 11 and 0 < selected_slots.get(player_in, 0) <= 11:
            selected_slots[player_out], selected_slots[player_in] = selected_slots[player_in], selected_slots[player_out]
    captain_multiplier = 3 if picks_payload.get("active_chip") == "3xc" else 2
    bench_boost = picks_payload.get("active_chip") == "bboost"
    pick_rows: list[dict[str, Any]] = []
    projected_total = 0.0
    for pick in picks:
        if not isinstance(pick, dict):
            continue
        player_id = int(pick["element"])
        multiplier = int(pick.get("multiplier", 0) or 0)
        predicted = prediction_by_id[player_id]
        actual = actual_by_id[player_id]
        selected_slot = selected_slots[player_id]
        projected_multiplier = 1 if bench_boost or 0 < selected_slot <= 11 else 0
        if pick.get("is_captain") and projected_multiplier:
            projected_multiplier = captain_multiplier
        projected_contribution = predicted * projected_multiplier
        actual_contribution = actual * multiplier
        projected_total += projected_contribution
        label = _player_label(player_id, players, teams)
        pick_rows.append(
            {
                **label,
                "slot": selected_slot,
                "multiplier": multiplier,
                "projected_multiplier": projected_multiplier,
                "is_captain": bool(pick.get("is_captain")),
                "is_vice_captain": bool(pick.get("is_vice_captain")),
                "predicted_points": _round_points(predicted),
                "actual_points": actual,
                "projected_contribution": _round_points(projected_contribution),
                "actual_contribution": actual_contribution,
                "residual": _round_points(actual - predicted),
            }
        )

    official_points = int(entry_history.get("points", 0) or 0)
    hit_cost = int(entry_history.get("event_transfers_cost", 0) or 0)
    projected_total = _round_points(projected_total)
    delta = _round_points(official_points - projected_total)

    captain_pick = next((row for row in pick_rows if row["is_captain"]), None)
    captain = None
    if captain_pick:
        captain = {
            "player_id": captain_pick["player_id"],
            "name": captain_pick["name"],
            "multiplier": captain_pick["multiplier"],
            "projected_points": captain_pick["predicted_points"],
            "actual_points": captain_pick["actual_points"],
            "projected_contribution": captain_pick["projected_contribution"],
            "actual_contribution": captain_pick["actual_contribution"],
            "contribution_delta": _round_points(
                captain_pick["actual_contribution"]
                - captain_pick["projected_contribution"]
            ),
        }

    bench_rows = [row for row in pick_rows if row["slot"] > 11]
    transfer_rows: list[dict[str, Any]] = []
    for transfer in transfers:
        if not isinstance(transfer, dict) or int(transfer.get("event", 0) or 0) != event:
            continue
        player_in_id = int(transfer.get("element_in", 0) or 0)
        player_out_id = int(transfer.get("element_out", 0) or 0)
        if player_in_id not in prediction_by_id or player_out_id not in prediction_by_id:
            raise ReviewDataError("prediction artifact does not cover a Gameweek transfer")
        if player_in_id not in actual_by_id or player_out_id not in actual_by_id:
            raise ReviewDataError("official event data does not cover a Gameweek transfer")
        in_label = _player_label(player_in_id, players, teams)
        out_label = _player_label(player_out_id, players, teams)
        transfer_rows.append(
            {
                "player_in": {
                    "player_id": player_in_id,
                    "name": in_label["name"],
                },
                "player_out": {
                    "player_id": player_out_id,
                    "name": out_label["name"],
                },
                "projected_delta": _round_points(
                    prediction_by_id[player_in_id] - prediction_by_id[player_out_id]
                ),
                "actual_delta": actual_by_id[player_in_id] - actual_by_id[player_out_id],
            }
        )

    largest_miss = min(pick_rows, key=lambda row: (row["residual"], row["player_id"]))

    xmins_rows = []
    for row in pick_rows:
        player_id = row["player_id"]
        if player_id not in xmins_by_id or player_id not in actual_minutes_by_id:
            continue
        predicted_xmins = _round_points(xmins_by_id[player_id])
        actual_minutes = actual_minutes_by_id[player_id]
        xmins_rows.append({
            "player_id": player_id,
            "name": row["name"],
            "predicted_xmins": predicted_xmins,
            "actual_minutes": actual_minutes,
            "residual": _round_points(actual_minutes - predicted_xmins),
        })
    largest_xmins_miss = (
        max(xmins_rows, key=lambda row: (abs(row["residual"]), -row["player_id"]))
        if xmins_rows
        else None
    )

    projected_transfer_value = _round_points(
        sum(row["projected_delta"] for row in transfer_rows) - hit_cost
    )
    starting_rows = [row for row in pick_rows if row["slot"] <= 11]
    best_owned_projection = max(
        (row["predicted_points"] for row in starting_rows),
        default=0.0,
    )
    captain_opportunity_cost = _round_points(
        max(0.0, best_owned_projection - captain_pick["predicted_points"])
        if captain_pick
        else 0.0
    )
    projected_decision_value = _round_points(
        projected_transfer_value - captain_opportunity_cost
    )
    if projected_decision_value >= 0:
        decision_quality_label = "SOUND"
    elif projected_decision_value >= -2:
        decision_quality_label = "MARGINAL"
    else:
        decision_quality_label = "QUESTIONABLE"

    next_signals: list[dict[str, Any]] = []
    if largest_xmins_miss and abs(largest_xmins_miss["residual"]) >= 30:
        next_signals.append({
            "type": "MINUTES_REVIEW",
            "severity": "WATCH",
            "title": f"Recheck {largest_xmins_miss['name']}'s minutes",
            "message": "The largest xMins miss should be reassessed against current availability, role and congestion before the next deadline.",
            "evidence": {
                "predicted_xmins": largest_xmins_miss["predicted_xmins"],
                "actual_minutes": largest_xmins_miss["actual_minutes"],
            },
        })
    if captain_opportunity_cost >= 1:
        next_signals.append({
            "type": "CAPTAIN_REVIEW",
            "severity": "WATCH",
            "title": "Reopen the captain comparison",
            "message": "The selected captain trailed the best owned pre-deadline projection; compare minutes security and upside again next Gameweek.",
            "evidence": {"projected_opportunity_cost": captain_opportunity_cost},
        })
    if transfer_rows and projected_transfer_value < 0:
        next_signals.append({
            "type": "TRANSFER_DISCIPLINE",
            "severity": "ACTION",
            "title": "Raise the transfer threshold",
            "message": "The move was negative expected value after its official points cost, regardless of the eventual match outcome.",
            "evidence": {"projected_transfer_value": projected_transfer_value},
        })

    return {
        "available": True,
        "team_id": team_id,
        "event": event,
        "prediction_version": prediction_version,
        "summary": {
            "projected_points": projected_total,
            "official_points": official_points,
            "hit_cost": hit_cost,
            "net_points_after_hits": official_points - hit_cost,
            "actual_vs_projected": delta,
            "outcome": _outcome(delta),
        },
        "captain": captain,
        "bench": {
            "official_points": int(entry_history.get("points_on_bench", 0) or 0),
            "projected_points": _round_points(
                sum(row["predicted_points"] for row in bench_rows)
            ),
            "player_count": len(bench_rows),
        },
        "transfers": transfer_rows,
        "picks": pick_rows,
        "largest_model_miss": {
            "player_id": largest_miss["player_id"],
            "name": largest_miss["name"],
            "predicted_points": largest_miss["predicted_points"],
            "actual_points": largest_miss["actual_points"],
            "residual": largest_miss["residual"],
        },
        "largest_xmins_miss": largest_xmins_miss,
        "decision_quality": {
            "label": decision_quality_label,
            "projected_decision_value": projected_decision_value,
            "projected_transfer_value": projected_transfer_value,
            "captain_opportunity_cost": captain_opportunity_cost,
            "basis": "pre_deadline_projection",
        },
        "next_signals": next_signals,
    }
