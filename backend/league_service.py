"""Mini-league insight from public FPL data.

What the public API shows: the leagues a manager is in, a league's standings
and every manager's squad for Gameweeks whose deadline has passed. What it
does not show: anyone's squad for the next deadline. Everything here is
therefore based on the latest Gameweek whose deadline has passed, and says so.

Effective ownership (EO) in the league is the share of managers who own a
player, counting a captain twice (three times under Triple Captain) and a
bench player not at all: the points a player moves for the league. Threats
and differentials compare your squad with the rivals' EO (you excluded).
"""
from __future__ import annotations

from typing import Any, Mapping

from .fpl_gateway import FplGatewayError, FplNotFoundError, default_gateway

# Squads are fetched one request per manager; larger leagues would exhaust
# the shared upstream budget, so only the top of a league is analysed.
MAX_LEAGUE_MANAGERS = 30
# Picks for a deadline that has passed no longer change.
PICKS_TTL_SECONDS = 600
STANDINGS_TTL_SECONDS = 120
# A player at least this many league "owners" (EO) worth, that you do not
# own, can cost you ground; one you own below the low bar can gain it.
THREAT_EO = 50.0
DIFFERENTIAL_EO = 25.0


class LeagueServiceError(RuntimeError):
    """League data could not be loaded."""


class LeagueNotFoundError(LeagueServiceError):
    """No league with that ID exists (or the manager is not in it)."""


def _get(path: str, ttl: int) -> Any:
    try:
        return default_gateway.get_json(path, ttl).data
    except FplNotFoundError as exc:
        raise LeagueNotFoundError(str(exc)) from exc
    except FplGatewayError as exc:
        raise LeagueServiceError(str(exc)) from exc


def manager_leagues(team_id: int) -> list[dict[str, Any]]:
    """The manager's private classic leagues (the mini-leagues)."""
    entry = _get(f"entry/{team_id}/", 300)
    leagues = ((entry or {}).get("leagues") or {}).get("classic") or []
    result = []
    for league in leagues:
        if league.get("league_type") != "x":  # system leagues (overall, country, club)
            continue
        result.append({
            "league_id": int(league["id"]),
            "name": str(league.get("name") or f"League {league['id']}"),
            "managers": league.get("rank_count"),
            "rank": league.get("entry_rank"),
            "last_rank": league.get("entry_last_rank"),
            "analysed_managers": min(int(league.get("rank_count") or 0), MAX_LEAGUE_MANAGERS),
        })
    return result


def _deadline_event(bootstrap: Mapping[str, Any]) -> int | None:
    """The latest Gameweek whose deadline has passed (squads are public)."""
    events = bootstrap.get("events") or []
    current = next((e for e in events if e.get("is_current")), None)
    if current:
        return int(current["id"])
    finished = [int(e["id"]) for e in events if e.get("finished")]
    return max(finished) if finished else None


MAX_STANDINGS_PAGES = 20


def _standings(league_id: int, team_id: int | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The first standings page (50 managers), plus the manager's own row when
    they rank further down: FPL pages the table, so follow it to find them."""
    payload = _get(f"leagues-classic/{league_id}/standings/", STANDINGS_TTL_SECONDS)
    league = payload.get("league") or {}
    standings = payload.get("standings") or {}
    rows = list(standings.get("results") or [])
    if team_id is None or any(int(r["entry"]) == team_id for r in rows):
        return league, rows
    page, has_next = 1, bool(standings.get("has_next"))
    while has_next and page < MAX_STANDINGS_PAGES:
        page += 1
        more = (_get(f"leagues-classic/{league_id}/standings/?page_standings={page}",
                     STANDINGS_TTL_SECONDS).get("standings") or {})
        own = next((r for r in more.get("results") or [] if int(r["entry"]) == team_id), None)
        if own is not None:
            return league, rows + [own]
        has_next = bool(more.get("has_next"))
    return league, rows


def _picks(team_id: int, event: int) -> dict[str, Any] | None:
    try:
        return _get(f"entry/{team_id}/event/{event}/picks/", PICKS_TTL_SECONDS)
    except LeagueNotFoundError:
        return None  # joined after that deadline


def _multipliers(picks_payload: Mapping[str, Any]) -> dict[int, int]:
    return {int(p["element"]): int(p.get("multiplier", 0) or 0) for p in picks_payload.get("picks") or []}


def build_league(
    team_id: int,
    league_id: int,
    *,
    bootstrap: Mapping[str, Any],
    projections: Mapping[int, float] | None = None,
) -> dict[str, Any]:
    """Standings, gaps and league effective ownership for one mini-league."""
    league, rows = _standings(league_id, team_id)
    if not rows:
        raise LeagueNotFoundError(f"League {league_id} has no standings")
    event = _deadline_event(bootstrap)
    elements = {int(e["id"]): e for e in bootstrap.get("elements") or []}
    clubs = {int(t["id"]): t for t in bootstrap.get("teams") or []}
    rows = sorted(rows, key=lambda r: int(r.get("rank") or 10**9))
    analysed = rows[:MAX_LEAGUE_MANAGERS]
    if all(int(r["entry"]) != team_id for r in analysed):
        own = next((r for r in rows if int(r["entry"]) == team_id), None)
        if own is None:
            raise LeagueNotFoundError(f"Team {team_id} is not in league {league_id}")
        analysed = analysed[:-1] + [own]
    me = next(r for r in rows if int(r["entry"]) == team_id)

    squads: dict[int, dict[int, int]] = {}
    chips: dict[int, str | None] = {}
    if event is not None:
        for row in analysed:
            payload = _picks(int(row["entry"]), event)
            if payload is not None:
                squads[int(row["entry"])] = _multipliers(payload)
                chips[int(row["entry"])] = payload.get("active_chip")

    standings = []
    for row in rows:
        entry = int(row["entry"])
        standings.append({
            "team_id": entry,
            # Team names only: managers' personal names are not republished.
            "team_name": str(row.get("entry_name") or ""),
            "rank": row.get("rank"),
            "last_rank": row.get("last_rank"),
            "event_points": row.get("event_total"),
            "total": row.get("total"),
            "gap_to_you": int(row.get("total") or 0) - int(me.get("total") or 0),
            "active_chip": chips.get(entry),
            "is_you": entry == team_id,
        })

    counted = len(squads)
    ownership: dict[int, dict[str, float]] = {}
    for squad in squads.values():
        for player, multiplier in squad.items():
            stats = ownership.setdefault(player, {"owners": 0, "starters": 0, "captains": 0, "weight": 0})
            stats["owners"] += 1
            stats["starters"] += 1 if multiplier > 0 else 0
            stats["captains"] += 1 if multiplier > 1 else 0
            stats["weight"] += multiplier
    mine = squads.get(team_id, {})
    rivals = max(0, counted - (1 if team_id in squads else 0))
    players = []
    for player, stats in ownership.items():
        element = elements.get(player, {})
        eo = 100.0 * stats["weight"] / counted if counted else 0.0
        my_multiplier = mine.get(player)
        # Threats and differentials are judged against the rivals only.
        rival_weight = stats["weight"] - (my_multiplier or 0)
        rival_eo = 100.0 * rival_weight / rivals if rivals else 0.0
        if my_multiplier is None:
            role = "THREAT" if rival_eo >= THREAT_EO else None
        else:
            role = "DIFFERENTIAL" if my_multiplier > 0 and rival_eo < DIFFERENTIAL_EO else None
        players.append({
            "player_id": player,
            "name": str(element.get("web_name") or f"Player {player}"),
            "team_short": str(clubs.get(int(element.get("team") or 0), {}).get("short_name") or ""),
            "position": {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}.get(int(element.get("element_type") or 0)),
            "owners": int(stats["owners"]),
            "captains": int(stats["captains"]),
            "ownership": round(100.0 * stats["owners"] / counted, 1) if counted else 0.0,
            "eo": round(eo, 1),
            "rival_eo": round(rival_eo, 1),
            "you": None if my_multiplier is None else ("CAPTAIN" if my_multiplier > 1 else "STARTER" if my_multiplier else "BENCH"),
            "role": role,
            "next_gw_points": round(float(projections[player]), 2) if projections and player in projections else None,
        })
    players.sort(key=lambda p: (-p["eo"], -p["owners"], p["name"]))
    return {
        "league_id": league_id,
        "name": str(league.get("name") or f"League {league_id}"),
        "event": event,
        "managers": len(rows),
        "analysed_managers": counted,
        "max_analysed_managers": MAX_LEAGUE_MANAGERS,
        "standings": standings,
        "players": players,
        "thresholds": {"threat_eo": THREAT_EO, "differential_eo": DIFFERENTIAL_EO},
        "basis": (
            f"Squads from GW{event}, the latest deadline that has passed: FPL does not publish "
            "anyone's squad for the next deadline." if event else "No Gameweek deadline has passed yet."
        ),
    }


def compare_rival(
    team_id: int,
    rival_id: int,
    *,
    bootstrap: Mapping[str, Any],
    projections: Mapping[int, float] | None = None,
) -> dict[str, Any]:
    """Shared and unique players of two managers (latest public squads)."""
    event = _deadline_event(bootstrap)
    if event is None:
        raise LeagueServiceError("No Gameweek deadline has passed yet")
    mine_payload, rival_payload = _picks(team_id, event), _picks(rival_id, event)
    if mine_payload is None or rival_payload is None:
        raise LeagueNotFoundError("A squad is not available for this Gameweek")
    mine, rival = _multipliers(mine_payload), _multipliers(rival_payload)
    elements = {int(e["id"]): e for e in bootstrap.get("elements") or []}
    clubs = {int(t["id"]): t for t in bootstrap.get("teams") or []}

    def player(pid: int, multiplier: int | None) -> dict[str, Any]:
        element = elements.get(pid, {})
        return {
            "player_id": pid,
            "name": str(element.get("web_name") or f"Player {pid}"),
            "team_short": str(clubs.get(int(element.get("team") or 0), {}).get("short_name") or ""),
            "position": {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}.get(int(element.get("element_type") or 0)),
            "role": None if multiplier is None else ("CAPTAIN" if multiplier > 1 else "STARTER" if multiplier else "BENCH"),
            "next_gw_points": round(float(projections[pid]), 2) if projections and pid in projections else None,
        }

    def summed(ids: list[int], squad: Mapping[int, int]) -> float | None:
        if not projections:
            return None
        return round(sum(float(projections.get(pid, 0.0)) for pid in ids if squad.get(pid, 0) > 0), 2)

    only_mine = sorted(set(mine) - set(rival))
    only_rival = sorted(set(rival) - set(mine))
    shared = sorted(set(mine) & set(rival))
    captain_mine = next((pid for pid, m in mine.items() if m > 1), None)
    captain_rival = next((pid for pid, m in rival.items() if m > 1), None)
    return {
        "event": event,
        "team_id": team_id,
        "rival_id": rival_id,
        "only_you": [player(pid, mine[pid]) for pid in only_mine],
        "only_rival": [player(pid, rival[pid]) for pid in only_rival],
        "shared": [player(pid, mine[pid]) | {"rival_role": player(pid, rival[pid])["role"]} for pid in shared],
        "same_captain": captain_mine is not None and captain_mine == captain_rival,
        # Next-GW model points of the unique players each side starts:
        # where the head-to-head is decided if both squads stayed the same.
        "unique_next_gw_points": {"you": summed(only_mine, mine), "rival": summed(only_rival, rival)},
        "basis": f"Both squads as picked for GW{event}; next-deadline transfers are not public.",
    }
