"""When to play each chip over the rest of the season, from the fixture list.

The model projects only a few Gameweeks ahead, but the chips that matter most
(Free Hit, Bench Boost, Triple Captain) are about blank and double Gameweeks,
which the official fixture list shows much further out. For every remaining
Gameweek in a chip's period this counts, for the current squad:

* Free Hit: points lost to starters whose club has no match (blank);
* Bench Boost: what the bench scores, doubled for players who play twice;
* Triple Captain: the best captain's extra, doubled when he plays twice.

Each player's strength is the model's points per match for the coming
Gameweek. One chip per Gameweek, so chips are given distinct weeks, most
valuable first. Matches without a date are listed: they usually become
doubles later, so a plan can change when FPL reschedules them.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

LAST_GAMEWEEK = 38
FIRST_HALF_END = 19
CHIP_LABELS = {"FREE_HIT": "Free Hit", "BENCH_BOOST": "Bench Boost", "TRIPLE_CAPTAIN": "Triple Captain", "WILDCARD": "Wildcard"}
FREE_HIT_MIN_BLANK_STARTERS = 3
# Chips unused at the end of their period are lost; this close to the end, name the best week left.
USE_IT_OR_LOSE_IT = 4


def club_fixture_counts(fixtures: Iterable[Mapping[str, Any]]) -> tuple[dict[int, dict[int, int]], list[dict[str, int]]]:
    """Matches per club per Gameweek, and the matches that have no Gameweek yet."""
    counts: dict[int, dict[int, int]] = {}
    unscheduled: list[dict[str, int]] = []
    for fixture in fixtures:
        home, away = fixture.get("team_h"), fixture.get("team_a")
        if home is None or away is None:
            continue
        event = fixture.get("event")
        if event is None:
            if not fixture.get("finished"):
                unscheduled.append({"home": int(home), "away": int(away)})
            continue
        for club in (int(home), int(away)):
            counts.setdefault(int(event), {}).setdefault(club, 0)
            counts[int(event)][club] += 1
    return counts, unscheduled


def _period(state: Mapping[str, Any], start: int) -> tuple[int, int]:
    events = state.get("period_events")
    if isinstance(events, (list, tuple)) and len(events) == 2:
        return max(start, int(events[0])), int(events[1])
    return start, FIRST_HALF_END if start <= FIRST_HALF_END else LAST_GAMEWEEK


def plan_chip_season(
    *,
    fixtures: Sequence[Mapping[str, Any]],
    clubs: Mapping[int, str],
    starters: Sequence[Mapping[str, Any]],
    bench: Sequence[Mapping[str, Any]],
    chip_state: Mapping[str, Any],
    start_event: int,
) -> dict[str, Any]:
    """Best week per chip in this period, and a preview of the next one."""
    counts, unscheduled = club_fixture_counts(fixtures)
    league_size = max(1, len(clubs))

    def weeks(first: int, last: int) -> list[dict[str, Any]]:
        rows = []
        for gameweek in range(first, last + 1):
            if gameweek not in counts:
                continue  # no fixtures listed for this week: unknown, not a blank
            per_club = counts[gameweek]
            def matches(player: Mapping[str, Any]) -> int:
                return per_club.get(int(player["club_id"]), 0)
            blank_starters = [p for p in starters if matches(p) == 0]
            doubles = [p for p in (*starters, *bench) if matches(p) >= 2]
            captain = max(starters, key=lambda p: float(p["strength"]) * matches(p), default=None)
            rows.append({
                "gameweek": gameweek,
                "blank_clubs": sum(1 for club in clubs if per_club.get(club, 0) == 0),
                "double_clubs": sum(1 for club in clubs if per_club.get(club, 0) >= 2),
                "blank_starters": [str(p["name"]) for p in blank_starters],
                "doubles_in_squad": [str(p["name"]) for p in doubles],
                "free_hit": round(sum(float(p["strength"]) for p in blank_starters), 2),
                "bench_boost": round(sum(float(p["strength"]) * matches(p) for p in bench), 2),
                "triple_captain": round(float(captain["strength"]) * matches(captain), 2) if captain else 0.0,
                "captain": str(captain["name"]) if captain else None,
            })
        return rows

    first, last = _period(chip_state, start_event)
    current = weeks(first, last) if first <= last else []
    available = {
        "FREE_HIT": bool(chip_state.get("free_hit_available")),
        "BENCH_BOOST": bool(chip_state.get("bench_boost_available")),
        "TRIPLE_CAPTAIN": bool(chip_state.get("triple_captain_available")),
        "WILDCARD": bool(chip_state.get("wildcard_available")),
    }

    def assign(rows: list[dict[str, Any]], chips: dict[str, bool], period_end: int) -> list[dict[str, Any]]:
        plans: list[dict[str, Any]] = []
        taken: set[int] = set()
        candidates = []
        for chip, key in (("FREE_HIT", "free_hit"), ("BENCH_BOOST", "bench_boost"), ("TRIPLE_CAPTAIN", "triple_captain")):
            if not chips.get(chip):
                continue
            for row in rows:
                value = row[key]
                special = (len(row["blank_starters"]) >= FREE_HIT_MIN_BLANK_STARTERS if chip == "FREE_HIT"
                           else row["double_clubs"] > 0 and bool(row["doubles_in_squad"]))
                candidates.append((special, value, chip, row))
        # Special weeks (blanks for the Free Hit, doubles for the others) first, then value.
        candidates.sort(key=lambda item: (item[0], item[1], -item[3]["gameweek"]), reverse=True)
        for special, value, chip, row in candidates:
            if any(plan["chip"] == chip for plan in plans) or row["gameweek"] in taken:
                continue
            if not special:
                continue  # only real blank or double weeks are proposed; see the fallback below
            taken.add(row["gameweek"])
            plans.append(_explain(chip, row, special, value))
        closing = bool(rows) and period_end - start_event < USE_IT_OR_LOSE_IT
        for chip, has in chips.items():
            if not has or chip == "WILDCARD" or any(plan["chip"] == chip for plan in plans):
                continue
            key = {"FREE_HIT": "free_hit", "BENCH_BOOST": "bench_boost", "TRIPLE_CAPTAIN": "triple_captain"}[chip]
            fallback = max((row for row in rows if row["gameweek"] not in taken), key=lambda row: row[key], default=None) if closing else None
            if fallback is not None:
                taken.add(fallback["gameweek"])
                plans.append({"chip": chip, "label": CHIP_LABELS[chip], "gameweek": fallback["gameweek"], "scheduled": False,
                              "value": round(fallback[key], 2),
                              "reason": f"Use it by GW{period_end} or lose it. No special week is left, and GW{fallback['gameweek']} suits your squad best."})
            else:
                plans.append({"chip": chip, "label": CHIP_LABELS[chip], "gameweek": None, "scheduled": False,
                              "value": 0.0, "reason": _no_week(chip, period_end)})
        if chips.get("WILDCARD"):
            boost = next((plan for plan in plans if plan["chip"] == "BENCH_BOOST" and plan["gameweek"]), None)
            plans.append({"chip": "WILDCARD", "label": CHIP_LABELS["WILDCARD"], "gameweek": None, "scheduled": False, "value": 0.0,
                          "reason": (f"Use it a week or two before your Bench Boost in GW{boost['gameweek']} to build a squad that plays twice."
                                     if boost else "Use it when the rebuild signal in the plan says so; it is not tied to a fixture week.")})
        order = {"FREE_HIT": 0, "BENCH_BOOST": 1, "TRIPLE_CAPTAIN": 2, "WILDCARD": 3}
        return sorted(plans, key=lambda plan: (plan["gameweek"] or 99, order[plan["chip"]]))

    current_plans = assign(current, available, last)
    preview_rows = weeks(FIRST_HALF_END + 1, LAST_GAMEWEEK) if last <= FIRST_HALF_END else []
    preview = assign(preview_rows, {chip: True for chip in available}, LAST_GAMEWEEK) if preview_rows else []
    names = {club: name for club, name in clubs.items()}
    return {
        "period": {"first": first, "last": last},
        "plans": current_plans,
        "next_period": {"first": FIRST_HALF_END + 1, "last": LAST_GAMEWEEK, "plans": preview} if preview_rows else None,
        "timeline": [{key: row[key] for key in ("gameweek", "blank_clubs", "double_clubs", "blank_starters", "doubles_in_squad")}
                     for row in (*current, *preview_rows) if row["blank_clubs"] or row["double_clubs"]],
        "unscheduled": [{"home": names.get(item["home"], str(item["home"])), "away": names.get(item["away"], str(item["away"]))}
                        for item in unscheduled],
        "league_size": league_size,
    }


def _explain(chip: str, row: Mapping[str, Any], special: bool, value: float) -> dict[str, Any]:
    gameweek = row["gameweek"]
    if chip == "FREE_HIT":
        names = ", ".join(row["blank_starters"][:5])
        reason = f"GW{gameweek}: {len(row['blank_starters'])} of your starters have no match ({names})."
    elif chip == "BENCH_BOOST":
        reason = (f"GW{gameweek} is a double Gameweek: {len(row['doubles_in_squad'])} of your players play twice."
                  if special else f"No double Gameweek is scheduled yet; GW{gameweek} has your bench's best fixtures.")
    else:
        reason = (f"GW{gameweek}: {row['captain']} plays twice." if special
                  else f"No double Gameweek is scheduled yet; GW{gameweek} suits {row['captain']} best.")
    return {"chip": chip, "label": CHIP_LABELS[chip], "gameweek": gameweek, "scheduled": special,
            "value": round(value, 2), "reason": reason}


def _no_week(chip: str, period_end: int | None) -> str:
    deadline = f" Use it by GW{period_end} or it is lost." if period_end else ""
    if chip == "FREE_HIT":
        return "No blank Gameweek hits your starters in this period yet. Keep it for one, or for a week when injuries pile up." + deadline
    return ("No double Gameweek is scheduled in this period yet. They usually appear once cup ties are rescheduled, "
            "so keep it until one does." + deadline)
