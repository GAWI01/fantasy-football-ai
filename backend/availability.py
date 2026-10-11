"""Gameweek-specific availability from official FPL player status and news.

Official FPL data describes availability for the *next* round only
(`chance_of_playing_next_round`) plus a free-text news line that often carries
a return date ("Suspended until 25 Oct", "Hamstring injury - Expected back
24 Oct"). A planning horizon must not copy next round's availability onto
every later Gameweek: a one-match ban or a short knock removes one Gameweek,
not five.

`gameweek_multipliers` returns one multiplier per horizon Gameweek:

* the first (target) Gameweek uses the official next-round rule unchanged;
* later Gameweeks use the news return date when one is published, otherwise
  a documented recovery assumption per status.

The recovery assumptions are heuristics, not validated probabilities: past
availability flags are not archived, so they cannot be backtested yet.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Sequence

# Official status codes: a available, d doubtful, i injured, s suspended,
# u unavailable (left the club / long-term), n not eligible (e.g. loanee
# against his parent club) - which affects a single fixture.
UNAVAILABLE_FOR_HORIZON = {"u"}

# Without a published return date. Index 0 is the Gameweek after the target.
# Injured: back gradually; suspended: a one-match ban is the common case.
INJURED_RECOVERY = (0.25, 0.5, 0.75, 1.0)
SUSPENDED_RECOVERY = (1.0,)
# Doubtful players with a published chance usually resolve within a week.
DOUBTFUL_NEXT_WEEK_SHARE = 0.5
# The first Gameweek back from injury carries reduced minutes.
FIRST_WEEK_BACK_FROM_INJURY = 0.75

_MONTHS = {name: index for index, name in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}
_RETURN_DATE = re.compile(
    r"(?:until|expected back|back on|return(?:s|ing)? on)\s+(\d{1,2})\s+([A-Za-z]{3})", re.IGNORECASE)


def _chance(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def official_multiplier(status: Any, chance: Any) -> float:
    """The next-round rule the API has always applied to the target Gameweek."""
    code = str(status or "a").strip().lower()
    chance_value = _chance(chance)
    if code in {"s", "u", "n"} or chance_value == 0 or (code == "i" and chance_value is None):
        return 0.0
    if chance_value is None:
        return 1.0
    return min(1.0, max(0.0, chance_value / 100.0))


def parse_return_date(news: Any, reference: datetime) -> datetime | None:
    """The return date in an official news line, in the year nearest `reference`."""
    match = _RETURN_DATE.search(str(news or ""))
    if not match:
        return None
    day, month = int(match.group(1)), _MONTHS.get(match.group(2).lower())
    if month is None:
        return None
    reference = reference.astimezone(timezone.utc)
    candidates = []
    for year in (reference.year - 1, reference.year, reference.year + 1):
        try:
            candidates.append(datetime(year, month, day, tzinfo=timezone.utc))
        except ValueError:
            continue
    if not candidates:
        return None
    return min(candidates, key=lambda moment: abs((moment - reference).total_seconds()))


def gameweek_multipliers(
    status: Any,
    chance: Any,
    news: Any,
    kickoffs: Sequence[datetime | None],
    *,
    reference: datetime,
) -> list[float]:
    """Availability multiplier for each horizon Gameweek (index 0 = target).

    `kickoffs` holds, per horizon Gameweek, the player's club's first kickoff
    in that Gameweek (None for a blank or unknown kickoff).
    """
    horizon = len(kickoffs)
    if horizon == 0:
        return []
    code = str(status or "a").strip().lower()
    first = official_multiplier(status, chance)
    if code in UNAVAILABLE_FOR_HORIZON:
        return [0.0] * horizon
    if code == "a" or first >= 1.0:
        return [first] + [1.0] * (horizon - 1)

    later: list[float] = []
    returns = parse_return_date(news, reference)
    if returns is not None and code in {"i", "s", "d"}:
        back = False
        for kickoff in kickoffs[1:]:
            # A blank (no kickoff) scores nothing either way; it neither
            # delays nor counts as the first week back.
            if kickoff is None or kickoff < returns:
                later.append(1.0 if back else 0.0)
            elif not back:
                back = True
                later.append(FIRST_WEEK_BACK_FROM_INJURY if code == "i" else 1.0)
            else:
                later.append(1.0)
        return [first] + later

    if code == "d":
        chance_value = first
        step = chance_value + (1.0 - chance_value) * DOUBTFUL_NEXT_WEEK_SHARE
        later = [step] + [1.0] * (horizon - 2)
    elif code == "s":
        later = list(SUSPENDED_RECOVERY)
    elif code == "n":
        later = [1.0]
    else:  # injured, or doubtful flagged with an unknown return
        recovery = INJURED_RECOVERY
        if code == "i" and first > 0:
            # An injured flag with a published chance recovers like a doubt.
            recovery = (first + (1.0 - first) * DOUBTFUL_NEXT_WEEK_SHARE, 1.0)
        later = list(recovery)
    later = (later + [later[-1] if later else 1.0] * horizon)[: horizon - 1]
    return [first] + later
