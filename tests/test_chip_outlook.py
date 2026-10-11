from decision_strategy import chip_outlook


def _player(player_id, weeks):
    return {"player_id": player_id, "gameweeks": [
        {"gameweek": gw, "predicted_points": pts, "fixture_count": fixtures} for gw, pts, fixtures in weeks
    ]}


STATE = {"wildcard_available": False, "free_hit_available": True,
         "bench_boost_available": True, "triple_captain_available": True}


def _outlook(horizon_team, starters, advisor=None):
    return {item["chip"]: item for item in chip_outlook(
        state=STATE, advisor=advisor or {"recommended_chip": None}, wildcard_signal=None,
        scenario_scores={}, horizon_team=horizon_team, starter_ids=starters, names={1: "Haaland"})}


def test_free_hit_points_at_the_week_most_starters_are_missing():
    team = [
        _player(1, [(7, 7.0, 1), (8, 0.0, 0), (9, 6.0, 1)]),
        _player(2, [(7, 4.0, 1), (8, 0.0, 0), (9, 4.0, 1)]),
        _player(3, [(7, 4.0, 1), (8, 0.2, 1), (9, 0.0, 0)]),  # ruled out in GW8
        _player(4, [(7, 3.0, 1), (8, 3.0, 1), (9, 3.0, 1)]),  # bench
    ]

    outlook = _outlook(team, [1, 2, 3])

    assert outlook["FREE_HIT"]["verdict"] == "SAVE"
    assert outlook["FREE_HIT"]["best_window"]["gameweek"] == 8
    assert "GW8: 3 of your starters" in outlook["FREE_HIT"]["summary"]
    assert outlook["WILDCARD"]["available"] is False and outlook["WILDCARD"]["verdict"] is None


def test_bench_boost_and_triple_captain_pick_their_best_week():
    team = [
        _player(1, [(7, 7.0, 1), (8, 12.0, 2)]),
        _player(4, [(7, 3.0, 1), (8, 7.0, 2)]),
        _player(5, [(7, 2.0, 1), (8, 6.0, 2)]),
    ]

    outlook = _outlook(team, [1])

    assert outlook["BENCH_BOOST"]["best_window"] == {"gameweek": 8, "value": 13.0, "unit": "bench xP"}
    assert "3 of your players play twice" in outlook["BENCH_BOOST"]["summary"]
    assert outlook["TRIPLE_CAPTAIN"]["best_window"]["gameweek"] == 8
    assert "Haaland projects 12.0" in outlook["TRIPLE_CAPTAIN"]["summary"]


def test_the_advisors_recommendation_is_the_verdict():
    team = [_player(1, [(7, 7.0, 2)]), _player(4, [(7, 13.0, 2)])]

    outlook = _outlook(team, [1], {"recommended_chip": "BENCH_BOOST", "reason": "Your bench projects 13.0 points."})

    assert outlook["BENCH_BOOST"]["verdict"] == "USE"
    assert outlook["BENCH_BOOST"]["summary"] == "Your bench projects 13.0 points."
    assert outlook["FREE_HIT"]["verdict"] == "SAVE"
