from __future__ import annotations

from collections import Counter
from typing import Any


MAX_PLAYERS_PER_CLUB = 3


def _club_counts(squad: list[dict[str, Any]]) -> Counter:
    return Counter(
        player.get("team")
        for player in squad
        if player.get("team")
    )


def detect_club_changes(
    current_squad: list[dict[str, Any]],
    previous_predictions: list[dict[str, Any]],
    current_predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Detect real-world club changes for players already owned by the user.

    A player is considered to have changed club when:
    - the player is already in the user's squad
    - the player existed in both previous and current data
    - the player's club differs between the two datasets
    """

    owned_ids = {
        player.get("player_id")
        for player in current_squad
        if isinstance(player, dict)
        and player.get("player_id") is not None
    }

    previous_by_id = {
        player.get("player_id"): player
        for player in previous_predictions
        if isinstance(player, dict)
        and player.get("player_id") is not None
    }

    current_by_id = {
        player.get("player_id"): player
        for player in current_predictions
        if isinstance(player, dict)
        and player.get("player_id") is not None
    }

    changes = []

    for player_id in owned_ids:
        previous = previous_by_id.get(player_id)
        current = current_by_id.get(player_id)

        if previous is None or current is None:
            continue

        old_club = previous.get("team")
        new_club = current.get("team")

        if not old_club or not new_club:
            continue

        if old_club == new_club:
            continue

        changes.append(
            {
                "player_id": player_id,
                "old_club": old_club,
                "new_club": new_club,
            }
        )

    return sorted(
        changes,
        key=lambda change: change["player_id"],
    )


def validate_transfer_squad(
    current_squad: list[dict[str, Any]],
    resulting_squad: list[dict[str, Any]],
    transfer_context: dict[str, Any] | None = None,
) -> bool:
    """
    Validate the club-count rule for a resulting squad.

    Normal transfers may not create more than three players from
    the same club.

    A player who is already owned may change real-world clubs while
    remaining in the user's squad. That existing player does not
    represent a normal transfer into the new club, so the resulting
    squad may contain more than three players from that club.
    """

    counts = _club_counts(resulting_squad)

    if all(count <= MAX_PLAYERS_PER_CLUB for count in counts.values()):
        return True

    context = transfer_context or {}

    if context.get("type") != "club_change":
        return False

    player_id = context.get("player_id")
    old_club = context.get("old_club")
    new_club = context.get("new_club")

    if player_id is None or not old_club or not new_club:
        return False

    if old_club == new_club:
        return False

    current_player = next(
        (
            player
            for player in current_squad
            if player.get("player_id") == player_id
        ),
        None,
    )

    resulting_player = next(
        (
            player
            for player in resulting_squad
            if player.get("player_id") == player_id
        ),
        None,
    )

    if current_player is None or resulting_player is None:
        return False

    if current_player.get("team") != old_club:
        return False

    if resulting_player.get("team") != new_club:
        return False

    return True
