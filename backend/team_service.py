from __future__ import annotations

from typing import Any

from .fpl_gateway import FplGatewayError, default_gateway


FPL_TEAM_URL = "https://fantasy.premierleague.com/api/entry/{team_id}/"
FPL_PICKS_URL = (
    "https://fantasy.premierleague.com/api/entry/"
    "{team_id}/event/{event}/picks/"
)
FPL_BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
class TeamServiceError(Exception):
    """Raised when a public FPL team cannot be loaded or normalized."""


def _require_mapping(payload: Any, field_name: str) -> dict:
    if not isinstance(payload, dict):
        raise TeamServiceError(f"{field_name} must be a JSON object")
    return payload


def _get_json(url: str) -> dict:
    ttl_seconds = 300 if url == FPL_BOOTSTRAP_URL else 60
    try:
        payload = default_gateway.get_json(url, ttl_seconds).data
    except FplGatewayError as exc:
        raise TeamServiceError(str(exc)) from exc

    return _require_mapping(payload, "response")


def _normalize_picks(picks: Any) -> list[dict]:
    if not isinstance(picks, list):
        raise TeamServiceError("picks must be a list")

    normalized_picks = []

    for index, pick in enumerate(picks):
        if not isinstance(pick, dict):
            raise TeamServiceError(
                f"pick at index {index} must be a JSON object"
            )

        if "element" not in pick:
            raise TeamServiceError(
                f"pick at index {index} is missing element"
            )

        if "position" not in pick:
            raise TeamServiceError(
                f"pick at index {index} is missing position"
            )

        normalized_pick = {
            "player_id": pick["element"],
            "position": pick["position"],
        }

        if "multiplier" in pick:
            normalized_pick["multiplier"] = pick["multiplier"]

        if "is_captain" in pick:
            normalized_pick["is_captain"] = bool(pick["is_captain"])

        if "is_vice_captain" in pick:
            normalized_pick["is_vice_captain"] = bool(
                pick["is_vice_captain"]
            )

        for price_field in ("purchase_price", "selling_price"):
            if pick.get(price_field) is not None:
                try:
                    normalized_pick[price_field] = float(pick[price_field]) / 10
                except (TypeError, ValueError) as exc:
                    raise TeamServiceError(
                        f"pick at index {index} has invalid {price_field}"
                    ) from exc

        normalized_picks.append(normalized_pick)

    return normalized_picks


def normalize_team_response(
    team_id: int,
    payload: dict,
    picks_payload: dict | None = None,
) -> dict:
    """Normalize current/legacy FPL team responses into one contract.

    The public entry endpoint contains manager summary fields, while the
    current Gameweek Picks endpoint carries the live squad snapshot in
    ``entry_history`` (bank, value, transfers and GW/rank data). Prefer the
    entry endpoint when it has a field, and use entry_history as the fallback.
    """
    if not isinstance(team_id, int) or team_id <= 0:
        raise TeamServiceError("Team ID must be a positive integer")

    payload = _require_mapping(payload, "response")

    if "entry" in payload:
        entry = _require_mapping(payload["entry"], "entry")
    else:
        entry = payload

    if "id" not in entry:
        raise TeamServiceError("entry is missing id")

    if "name" not in entry:
        raise TeamServiceError("entry is missing name")

    if picks_payload is not None:
        picks_source = picks_payload.get("picks")
        history = picks_payload.get("entry_history") or {}
    else:
        picks_source = payload.get("picks")
        history = payload.get("entry_history") or {}

    if picks_source is None:
        raise TeamServiceError("FPL response is missing picks")

    if not isinstance(history, dict):
        history = {}

    def first_present(*values):
        for value in values:
            if value is not None:
                return value
        return None

    def money_in_millions(*values):
        value = first_present(*values)
        if value is None:
            return None
        try:
            return float(value) / 10
        except (TypeError, ValueError) as exc:
            raise TeamServiceError("FPL financial value must be numeric") from exc

    manager_name = str(entry.get("player_last_name") or "").strip() or None

    return {
        "team_id": team_id,
        "name": entry["name"],
        "manager_name": manager_name,
        "bank": money_in_millions(
            entry.get("bank"),
            history.get("bank"),
        ),
        "started_event": entry.get("started_event"),
        "event": first_present(
            entry.get("event"),
            entry.get("current_event"),
            history.get("event"),
        ),
        "transfers": first_present(
            entry.get("transfers"),
            history.get("event_transfers"),
        ),
        "overall_rank": first_present(
            entry.get("summary_overall_rank"),
            history.get("overall_rank"),
        ),
        "event_points": first_present(
            entry.get("summary_event_points"),
            history.get("points"),
        ),
        "event_rank": first_present(
            entry.get("summary_event_rank"),
            history.get("rank"),
        ),
        "total_points": first_present(
            entry.get("summary_total_points"),
            history.get("total_points"),
        ),
        "value": money_in_millions(
            entry.get("value"),
            history.get("value"),
        ),
        "picks": _normalize_picks(picks_source),
    }


def _get_current_event(entry: dict) -> int:
    event = entry.get("current_event", entry.get("event"))

    if isinstance(event, int) and event > 0:
        return event

    bootstrap = _get_json(FPL_BOOTSTRAP_URL)
    events = bootstrap.get("events")

    if not isinstance(events, list):
        raise TeamServiceError(
            "FPL bootstrap response is missing events"
        )

    for gameweek in events:
        if isinstance(gameweek, dict) and gameweek.get("is_current"):
            event_id = gameweek.get("id")
            if isinstance(event_id, int) and event_id > 0:
                return event_id

    raise TeamServiceError("Could not determine current gameweek")


def fetch_public_team(team_id: int) -> dict:
    """Fetch and normalize a public FPL team."""

    if not isinstance(team_id, int) or team_id <= 0:
        raise TeamServiceError("Team ID must be a positive integer")

    entry_payload = _get_json(
        FPL_TEAM_URL.format(team_id=team_id)
    )

    # The entry endpoint should either contain picks (legacy/internal shape)
    # or provide enough information to determine the current event. If the
    # response is malformed in the same way used by the normalization tests,
    # surface the missing picks contract before attempting unrelated bootstrap
    # metadata.
    if "picks" not in entry_payload:
        if "entry" in entry_payload:
            entry = _require_mapping(entry_payload["entry"], "entry")
            if "picks" not in entry_payload:
                raise TeamServiceError("FPL response is missing picks")

        event = _get_current_event(entry_payload)
        picks_payload = _get_json(
            FPL_PICKS_URL.format(
                team_id=team_id,
                event=event,
            )
        )
        try:
            return normalize_team_response(
                team_id,
                entry_payload,
                picks_payload=picks_payload,
            )
        except TeamServiceError:
            raise
        except Exception as exc:
            raise TeamServiceError(
                f"Invalid FPL response: {exc}"
            ) from exc

    return normalize_team_response(team_id, entry_payload)
