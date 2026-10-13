from engine.chip_season import club_fixture_counts, plan_chip_season

CLUBS = {1: "Alpha", 2: "Bravo", 3: "Charlie", 4: "Delta"}


def _fixtures():
    rows = []
    # GW8: normal. GW9: Alpha and Bravo double, Charlie and Delta blank... Charlie-Delta unscheduled.
    rows += [{"event": 8, "team_h": 1, "team_a": 2}, {"event": 8, "team_h": 3, "team_a": 4}]
    rows += [{"event": 9, "team_h": 1, "team_a": 2}, {"event": 9, "team_h": 2, "team_a": 1}]
    rows += [{"event": 10, "team_h": 1, "team_a": 3}, {"event": 10, "team_h": 2, "team_a": 4}]
    rows += [{"event": None, "team_h": 3, "team_a": 4, "finished": False}]
    return rows


def _player(name, club, strength):
    return {"name": name, "club_id": club, "strength": strength}


STARTERS = [_player("A1", 1, 6.0), _player("C1", 3, 4.0), _player("C2", 3, 3.5), _player("D1", 4, 3.0), _player("B1", 2, 4.5)]
BENCH = [_player("A2", 1, 2.0), _player("B2", 2, 2.0)]


def test_counts_blanks_doubles_and_unscheduled():
    counts, unscheduled = club_fixture_counts(_fixtures())
    assert counts[9] == {1: 2, 2: 2}
    assert unscheduled == [{"home": 3, "away": 4}]


def test_chips_get_distinct_special_weeks():
    state = {"period_events": [1, 19], "free_hit_available": True, "bench_boost_available": True,
             "triple_captain_available": True, "wildcard_available": False}
    result = plan_chip_season(fixtures=_fixtures(), clubs=CLUBS, starters=STARTERS, bench=BENCH, chip_state=state, start_event=8)
    plans = {plan["chip"]: plan for plan in result["plans"]}
    # GW9: three starters blank (C1, C2, D1) and Alpha/Bravo double.
    assert plans["FREE_HIT"]["gameweek"] == 9 or plans["BENCH_BOOST"]["gameweek"] == 9 or plans["TRIPLE_CAPTAIN"]["gameweek"] == 9
    weeks = [plan["gameweek"] for plan in result["plans"] if plan["gameweek"]]
    assert len(weeks) == len(set(weeks)), "one chip per Gameweek"
    assert result["unscheduled"] == [{"home": "Charlie", "away": "Delta"}]
    # No fixtures listed after GW10 here, so there is nothing to preview.
    assert result["next_period"] is None


def test_free_hit_waits_for_a_real_blank():
    fixtures = [{"event": gw, "team_h": 1, "team_a": 2} for gw in range(8, 12)] + [{"event": gw, "team_h": 3, "team_a": 4} for gw in range(8, 12)]
    state = {"period_events": [1, 19], "free_hit_available": True}
    result = plan_chip_season(fixtures=fixtures, clubs=CLUBS, starters=STARTERS, bench=BENCH, chip_state=state, start_event=8)
    free_hit = next(plan for plan in result["plans"] if plan["chip"] == "FREE_HIT")
    assert free_hit["gameweek"] is None
    assert "No blank Gameweek" in free_hit["reason"]


def test_closing_period_names_the_best_week_left():
    fixtures = [{"event": gw, "team_h": 1, "team_a": 2} for gw in range(17, 20)] + [{"event": gw, "team_h": 3, "team_a": 4} for gw in range(17, 20)]
    state = {"period_events": [1, 19], "bench_boost_available": True}
    result = plan_chip_season(fixtures=fixtures, clubs=CLUBS, starters=STARTERS, bench=BENCH, chip_state=state, start_event=17)
    boost = next(plan for plan in result["plans"] if plan["chip"] == "BENCH_BOOST")
    assert boost["gameweek"] in (17, 18, 19)
    assert "or lose it" in boost["reason"]


def test_no_double_means_no_bench_boost_week_early_on():
    fixtures = [{"event": gw, "team_h": 1, "team_a": 2} for gw in range(8, 20)] + [{"event": gw, "team_h": 3, "team_a": 4} for gw in range(8, 20)]
    state = {"period_events": [1, 19], "bench_boost_available": True}
    result = plan_chip_season(fixtures=fixtures, clubs=CLUBS, starters=STARTERS, bench=BENCH, chip_state=state, start_event=8)
    boost = next(plan for plan in result["plans"] if plan["chip"] == "BENCH_BOOST")
    assert boost["gameweek"] is None
    assert "No double Gameweek" in boost["reason"]
