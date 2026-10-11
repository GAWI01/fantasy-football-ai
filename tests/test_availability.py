from datetime import datetime, timezone

from backend.availability import gameweek_multipliers, official_multiplier, parse_return_date

REFERENCE = datetime(2026, 10, 17, 10, tzinfo=timezone.utc)


def _kickoffs(*days):
    return [datetime(2026, 10, day, 14, tzinfo=timezone.utc) if day <= 31
            else datetime(2026, 11, day - 31, 14, tzinfo=timezone.utc) for day in days]


def test_official_rule_for_the_target_gameweek_is_unchanged():
    assert official_multiplier("a", None) == 1.0
    assert official_multiplier("d", 75) == 0.75
    assert official_multiplier("i", None) == 0.0
    assert official_multiplier("s", 0) == 0.0
    assert official_multiplier("u", None) == 0.0


def test_return_date_parses_official_news_formats_in_the_nearest_year():
    assert parse_return_date("Suspended until 25 Oct", REFERENCE) == datetime(2026, 10, 25, tzinfo=timezone.utc)
    assert parse_return_date("Hamstring injury - Expected back 24 Oct", REFERENCE).day == 24
    assert parse_return_date("Knee injury - Expected back 05 Jan", REFERENCE).year == 2027
    assert parse_return_date("Knee injury - Unknown return date", REFERENCE) is None
    assert parse_return_date("", REFERENCE) is None


def test_multipliers_follow_the_return_date_per_gameweek():
    kickoffs = _kickoffs(18, 25, 32, 39, 46)
    assert gameweek_multipliers("s", 0, "Suspended until 25 Oct", kickoffs, reference=REFERENCE) == [0.0, 1.0, 1.0, 1.0, 1.0]
    assert gameweek_multipliers("i", 0, "Calf injury - Expected back 30 Oct", kickoffs, reference=REFERENCE) == [0.0, 0.0, 0.75, 1.0, 1.0]


def test_available_and_departed_players():
    kickoffs = _kickoffs(18, 25, 32)
    assert gameweek_multipliers("a", None, "", kickoffs, reference=REFERENCE) == [1.0, 1.0, 1.0]
    assert gameweek_multipliers("u", 0, "Has joined Al Hilal permanently", kickoffs, reference=REFERENCE) == [0.0, 0.0, 0.0]
