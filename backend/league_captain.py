"""Captain choice against a mini-league.

Rivals' squads do not change what a captain is worth on average: captaining a
player adds his points once more whoever else owns him. What league ownership
changes is the *risk*. Captain a player most rivals also captain and his haul
or blank moves everyone together (safe). Captain one nobody else does and his
result swings you against the whole league (differential). So the pick stays
on expected points unless your league position says risk is worth paying for,
and the cost in expected points is always shown.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.point_ranges import point_range

LAST_GAMEWEEK = 38
SAFE_SHARE = 0.4          # at least this share of rivals captain him
DIFFERENTIAL_SHARE = 0.15  # at most this share of rivals captain him
SAFE_WINDOW = 1.0          # a safe pick may give up this many expected points
CHASE_WINDOW = 1.5         # a differential may give up this many when chasing
PROTECT_GAP = 10           # within this many points of the top: protect
CHASE_PER_GAMEWEEK = 3.0   # behind by this much per Gameweek left, in the run-in: chase
CHASE_RUN_IN = 19          # the run-in: at most this many Gameweeks left
DESPERATE_PER_GAMEWEEK = 6.0  # behind by this much per Gameweek left: chase at any time


def league_mode(gap_to_leader: int, rank: int | None, gameweeks_left: int) -> dict[str, Any]:
    """How much risk the league position calls for."""
    if rank == 1 or gap_to_leader <= PROTECT_GAP:
        return {"mode": "protect", "text": "You are at or near the top, so it pays to match your rivals and avoid risk."}
    per_week = gap_to_leader / max(1, gameweeks_left)
    # Early on, expected points win over a season; risk only pays once time runs short.
    if per_week >= DESPERATE_PER_GAMEWEEK or (per_week >= CHASE_PER_GAMEWEEK and gameweeks_left <= CHASE_RUN_IN):
        return {"mode": "chase", "text": f"You are {gap_to_leader} points behind with {gameweeks_left} Gameweeks left, so a differential can be worth the risk."}
    return {"mode": "balanced", "text": f"You are {gap_to_leader} points behind with {gameweeks_left} Gameweeks left: plenty of time, so expected points come first."}


def league_captain(
    candidates: Sequence[Mapping[str, Any]],
    league: Mapping[str, Any],
    team_id: int,
) -> dict[str, Any]:
    """Score captain candidates against one league built by `build_league`."""
    standings = league.get("standings") or []
    me = next((row for row in standings if row.get("is_you")), None)
    leader_total = max((int(row.get("total") or 0) for row in standings), default=0)
    my_total = int((me or {}).get("total") or 0)
    gap_to_leader = max(0, leader_total - my_total)
    event = league.get("event") or 0
    gameweeks_left = max(1, LAST_GAMEWEEK - int(event))
    mode = league_mode(gap_to_leader, (me or {}).get("rank"), gameweeks_left)

    ownership = {int(player["player_id"]): player for player in league.get("players") or []}
    analysed = int(league.get("analysed_managers") or 0)
    i_was_counted = any(player.get("you") is not None for player in ownership.values())
    rivals = max(0, analysed - (1 if i_was_counted else 0))

    rows = []
    for candidate in candidates:
        pid = int(candidate["player_id"])
        expected = float(candidate.get("predicted_points") or 0.0)
        owned = ownership.get(pid, {})
        captains = int(owned.get("captains") or 0) - (1 if owned.get("you") == "CAPTAIN" else 0)
        share = captains / rivals if rivals else 0.0
        rival_eo = float(owned.get("rival_eo") or 0.0) / 100.0
        spread = point_range(expected) or {}
        exposure = 2.0 - rival_eo  # captain counts twice for you, rival_eo times for the average rival
        rows.append({
            "player_id": pid,
            "name": str(candidate.get("name") or pid),
            "expected": round(expected, 2),
            "range": spread,
            "rival_captain_share": round(share, 3),
            "rival_eo": round(rival_eo, 3),
            "kind": "safe" if share >= SAFE_SHARE else "differential" if share <= DIFFERENTIAL_SHARE else "split",
            # Against the average rival, if he hauls (90th percentile) or blanks (10th).
            "swing_high": round(float(spread.get("high", 0.0)) * exposure, 1),
            "swing_low": round(float(spread.get("low", 0.0)) * exposure, 1),
        })
    rows.sort(key=lambda row: -row["expected"])
    if not rows:
        return {"mode": mode, "candidates": [], "pick": None, "rivals": rivals}
    best = rows[0]
    safe = max((row for row in rows if best["expected"] - row["expected"] <= SAFE_WINDOW),
               key=lambda row: (row["rival_captain_share"], row["expected"]))
    differential = next((row for row in rows if row["kind"] == "differential"
                         and best["expected"] - row["expected"] <= CHASE_WINDOW
                         and row["range"].get("haul_chance", 0) >= 0.08), None)
    if mode["mode"] == "protect":
        pick, reason = safe, "matches your rivals"
    elif mode["mode"] == "chase" and differential is not None:
        pick, reason = differential, "few rivals captain him, so a haul gains you ground"
    else:
        pick, reason = best, "the highest expected points"
    return {
        "mode": mode,
        "rivals": rivals,
        "gap_to_leader": gap_to_leader,
        "gameweeks_left": gameweeks_left,
        "candidates": rows,
        "best_id": best["player_id"],
        "safe_id": safe["player_id"],
        "differential_id": differential["player_id"] if differential else None,
        "pick": {"player_id": pick["player_id"], "name": pick["name"], "reason": reason,
                 "cost": round(best["expected"] - pick["expected"], 2)},
        "basis": league.get("basis"),
    }
