"""Decision labels derived from the canonical action plan.

Nothing here re-ranks transfers: the action planner
(`optimizer.action_planner`) chooses the action. This module turns that
choice into an action label, an honest confidence and evidence-based chip
advice.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from optimizer.action_planner import classify_action  # noqa: F401  (re-exported)

# Confidence is the decision margin measured in units of the projection
# uncertainty of the players the decision moves. The uncertainty bands are a
# transparent heuristic (see backend.planning_service._uncertainty), not a
# calibrated interval, so the label stays coarse.
CONFIDENCE_HIGH_RATIO = 1.0
CONFIDENCE_MEDIUM_RATIO = 0.4
# A plan relying on a player who may not start is never "high" confidence.
MINUTES_DOUBT_START_PROBABILITY = 0.7

# Chip bars for this Gameweek's value of a chip (expected points). They do
# not yet compare against playing the chip in a later Gameweek.
FREE_HIT_MIN_GAIN = 8.0
BENCH_BOOST_MIN_BENCH_POINTS = 12.0
TRIPLE_CAPTAIN_MIN_POINTS = 9.0


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def decision_confidence(
    chosen: Mapping[str, Any] | None,
    runner_up: Mapping[str, Any] | None,
    *,
    minutes_doubts: list[str] | None = None,
) -> dict[str, Any]:
    """How clearly the chosen action beats the best alternative action.

    margin  = decision score of the chosen action - that of the runner-up;
    spread  = projection uncertainty of the players either action moves;
    ratio   = margin / spread.
    Without a runner-up or any uncertainty data the label is UNKNOWN.
    """
    doubts = list(minutes_doubts or [])
    if not chosen or not runner_up:
        return {
            "score": None, "label": "UNKNOWN",
            "basis": "No alternative action could be compared.",
            "components": {"decision_margin": None, "uncertainty": None, "ratio": None},
            "minutes_doubts": doubts,
        }
    margin = float(chosen.get("decision_score", 0.0)) - float(runner_up.get("decision_score", 0.0))
    spreads = [value for value in (chosen.get("uncertainty"), runner_up.get("uncertainty"))
               if isinstance(value, (int, float)) and math.isfinite(value) and value > 0]
    if not spreads:
        return {
            "score": None, "label": "UNKNOWN",
            "basis": "Projection uncertainty is unavailable for the compared players.",
            "components": {"decision_margin": round(margin, 3), "uncertainty": None, "ratio": None},
            "minutes_doubts": doubts,
        }
    spread = max(spreads)
    ratio = margin / spread
    label = "HIGH" if ratio >= CONFIDENCE_HIGH_RATIO else "MEDIUM" if ratio >= CONFIDENCE_MEDIUM_RATIO else "LOW"
    if doubts and label == "HIGH":
        label = "MEDIUM"
    return {
        "score": round(_clip(ratio / (2 * CONFIDENCE_HIGH_RATIO)), 3),
        "label": label,
        "basis": "Margin over the next-best action, in units of the moved players' projection uncertainty.",
        "components": {
            "decision_margin": round(margin, 3),
            "uncertainty": round(spread, 3),
            "ratio": round(ratio, 3),
        },
        "minutes_doubts": doubts,
    }


def chip_advisor(
    *,
    wildcard_available: bool = False,
    free_hit_available: bool = False,
    bench_boost_available: bool = False,
    triple_captain_available: bool = False,
    wildcard_signal: Mapping[str, Any] | None = None,
    scenario_scores: Mapping[str, float] | None = None,
    double_gameweek: bool = False,
    blank_gameweek: bool = False,
) -> dict[str, Any]:
    """Recommend a chip only on evidence, never because it is available.

    * Wildcard: the free rebuild must beat the best normal action by the
      planner's threshold (`wildcard_signal`).
    * Free Hit: a blank Gameweek and a one-week gain of `FREE_HIT_MIN_GAIN`.
    * Bench Boost / Triple Captain: a double Gameweek and enough expected
      bench / captain points this Gameweek.
    """
    scores = dict(scenario_scores or {})
    options: list[tuple[str, float, str]] = []
    signal = dict(wildcard_signal or {})
    if wildcard_available and signal.get("recommended"):
        options.append(("WILDCARD", float(signal.get("advantage", 0.0)),
                        f"A rebuild beats the best normal action by {signal.get('advantage', 0.0):.1f} weighted points."))
    if free_hit_available and blank_gameweek and scores.get("FREE_HIT", 0.0) >= FREE_HIT_MIN_GAIN:
        options.append(("FREE_HIT", scores["FREE_HIT"], f"A one-week team gains {scores['FREE_HIT']:.1f} points in this blank Gameweek."))
    if bench_boost_available and double_gameweek and scores.get("BENCH_BOOST", 0.0) >= BENCH_BOOST_MIN_BENCH_POINTS:
        options.append(("BENCH_BOOST", scores["BENCH_BOOST"], f"Your bench projects {scores['BENCH_BOOST']:.1f} points in this double Gameweek."))
    if triple_captain_available and double_gameweek and scores.get("TRIPLE_CAPTAIN", 0.0) >= TRIPLE_CAPTAIN_MIN_POINTS:
        options.append(("TRIPLE_CAPTAIN", scores["TRIPLE_CAPTAIN"], f"Your captain projects {scores['TRIPLE_CAPTAIN']:.1f} points in this double Gameweek."))
    options.sort(key=lambda item: (-item[1], item[0]))
    return {
        "recommended_chip": options[0][0] if options else None,
        "score": round(options[0][1], 3) if options else 0.0,
        "reason": options[0][2] if options else "No chip clears its evidence bar this Gameweek.",
        "alternatives": [{"chip": chip, "score": round(score, 3), "reason": reason} for chip, score, reason in options[1:]],
        "thresholds": {
            "wildcard_advantage": signal.get("threshold"),
            "free_hit_gain": FREE_HIT_MIN_GAIN,
            "bench_boost_bench_points": BENCH_BOOST_MIN_BENCH_POINTS,
            "triple_captain_points": TRIPLE_CAPTAIN_MIN_POINTS,
        },
    }


CHIP_LABELS = {
    "WILDCARD": "Wildcard",
    "FREE_HIT": "Free Hit",
    "BENCH_BOOST": "Bench Boost",
    "TRIPLE_CAPTAIN": "Triple Captain",
}
# A Free Hit week is one where this many of your starters are missing:
# no match, or projected (almost) nothing because they are ruled out.
FREE_HIT_BLANK_STARTERS = 3
MISSING_STARTER_POINTS = 0.5


def _gameweek_points(item: Mapping[str, Any]) -> float:
    value = item.get("minutes_adjusted_points", item.get("predicted_points"))
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def chip_outlook(
    *,
    state: Mapping[str, Any],
    advisor: Mapping[str, Any],
    wildcard_signal: Mapping[str, Any] | None,
    scenario_scores: Mapping[str, float] | None,
    horizon_team: list[Mapping[str, Any]],
    starter_ids: list[int],
    names: Mapping[int, str] | None = None,
) -> list[dict[str, Any]]:
    """Per chip: is it worth playing now, and which week in view suits it.

    The recommendation itself is the advisor's (`advisor`); this explains it
    and points at the best window inside the projection horizon, judged on
    the current squad: starters missing (Free Hit), bench points
    (Bench Boost) and the best captain's points (Triple Captain).
    """
    names = names or {}
    scores = dict(scenario_scores or {})
    starters = {int(player_id) for player_id in starter_ids}
    weeks: dict[int, dict[str, Any]] = {}
    for player in horizon_team:
        player_id = int(player["player_id"])
        for item in player.get("gameweeks") or []:
            gameweek = int(item["gameweek"])
            week = weeks.setdefault(gameweek, {"bench": 0.0, "blanks": 0, "doubles": 0, "captain": (0.0, None)})
            points = _gameweek_points(item)
            fixtures = int(item.get("fixture_count", 1) if item.get("fixture_count") is not None else 1)
            if fixtures >= 2:
                week["doubles"] += 1
            if player_id in starters:
                if fixtures == 0 or points < MISSING_STARTER_POINTS:
                    week["blanks"] += 1
                if points > week["captain"][0]:
                    week["captain"] = (points, player_id)
            else:
                week["bench"] += points
    ordered = sorted(weeks)
    span = f"GW{ordered[0]}-{ordered[-1]}" if ordered else "the weeks in view"
    recommended = advisor.get("recommended_chip")
    signal = dict(wildcard_signal or {})
    result: list[dict[str, Any]] = []
    for chip, key in (("WILDCARD", "wildcard_available"), ("FREE_HIT", "free_hit_available"),
                      ("BENCH_BOOST", "bench_boost_available"), ("TRIPLE_CAPTAIN", "triple_captain_available")):
        available = bool(state.get(key, False))
        entry: dict[str, Any] = {"chip": chip, "label": CHIP_LABELS[chip], "available": available,
                                 "verdict": None, "this_week": None, "threshold": None, "best_window": None, "summary": None}
        if not available:
            result.append(entry)
            continue
        entry["verdict"] = "USE" if recommended == chip else "SAVE"
        if chip == "WILDCARD":
            advantage, threshold = signal.get("advantage"), signal.get("threshold")
            entry["this_week"] = None if advantage is None else round(float(advantage), 2)
            entry["threshold"] = threshold
            entry["summary"] = (
                f"A rebuild beats your best normal move by {float(advantage):.1f} points (worth it from {float(threshold):.0f})."
                if advantage is not None and threshold is not None
                else "Worth it when a rebuild clearly beats your best normal move."
            )
        elif chip == "FREE_HIT":
            entry["this_week"] = scores.get("FREE_HIT")
            entry["threshold"] = FREE_HIT_MIN_GAIN
            window = max((gw for gw in ordered if weeks[gw]["blanks"] >= FREE_HIT_BLANK_STARTERS),
                         key=lambda gw: (weeks[gw]["blanks"], -gw), default=None)
            if window is not None:
                entry["best_window"] = {"gameweek": window, "value": weeks[window]["blanks"], "unit": "starters missing"}
                entry["summary"] = (f"GW{window}: {weeks[window]['blanks']} of your starters have no match or are ruled out. "
                                    "That is a Free Hit week.")
            else:
                entry["summary"] = (f"Your starters are expected to play in {span}. Keep it for a blank Gameweek "
                                    "or a week when injuries and bans pile up.")
        elif chip == "BENCH_BOOST":
            entry["this_week"] = scores.get("BENCH_BOOST")
            entry["threshold"] = BENCH_BOOST_MIN_BENCH_POINTS
            window = max(ordered, key=lambda gw: (weeks[gw]["bench"], -gw), default=None)
            if window is not None:
                week = weeks[window]
                entry["best_window"] = {"gameweek": window, "value": round(week["bench"], 2), "unit": "bench xP"}
                double = f", {week['doubles']} of your players play twice" if week["doubles"] else ""
                entry["summary"] = (f"Best week in view: GW{window}, your bench projects {week['bench']:.1f} points{double}. "
                                    f"Worth it from {BENCH_BOOST_MIN_BENCH_POINTS:.0f} in a double Gameweek.")
        else:
            entry["this_week"] = scores.get("TRIPLE_CAPTAIN")
            entry["threshold"] = TRIPLE_CAPTAIN_MIN_POINTS
            window = max(ordered, key=lambda gw: (weeks[gw]["captain"][0], -gw), default=None)
            if window is not None:
                points, player_id = weeks[window]["captain"]
                who = names.get(player_id, "your best captain") if player_id is not None else "your best captain"
                entry["best_window"] = {"gameweek": window, "value": round(points, 2), "unit": "captain xP", "player_id": player_id}
                entry["summary"] = (f"Best week in view: GW{window}, {who} projects {points:.1f} points. "
                                    f"Worth it from {TRIPLE_CAPTAIN_MIN_POINTS:.0f} in a double Gameweek.")
        if entry["verdict"] == "USE":
            entry["summary"] = str(advisor.get("reason") or entry["summary"])
        result.append(entry)
    return result
