import pytest

import backend.fixture_service as fixture_service


def _bootstrap():
    return {
        "events": [
            {"id": 2, "is_current": True, "finished": False},
            {"id": 3, "is_next": True, "finished": False},
            {"id": 4, "finished": False},
            {"id": 5, "finished": False},
        ],
        "teams": [
            {"id": 1, "name": "Arsenal", "short_name": "ARS"},
            {"id": 2, "name": "Chelsea", "short_name": "CHE"},
            {"id": 3, "name": "Liverpool", "short_name": "LIV"},
        ],
    }


def _fixtures():
    return [
        {
            "id": 301,
            "event": 3,
            "team_h": 1,
            "team_a": 2,
            "team_h_difficulty": 2,
            "team_a_difficulty": 4,
        },
        {
            "id": 302,
            "event": 3,
            "team_h": 3,
            "team_a": 1,
            "team_h_difficulty": 3,
            "team_a_difficulty": 5,
        },
        {
            "id": 401,
            "event": 4,
            "team_h": 2,
            "team_a": 3,
            "team_h_difficulty": 2,
            "team_a_difficulty": 4,
        },
    ]


def test_build_fixture_matrix_covers_double_and_blank_gameweeks():
    result = fixture_service.build_fixture_matrix(
        _bootstrap(),
        _fixtures(),
        start_event=3,
        horizon=3,
    )

    assert result["gameweeks"] == [3, 4, 5]
    arsenal = next(team for team in result["teams"] if team["team_short"] == "ARS")
    assert arsenal["fixtures"][0] == {
        "event": 3,
        "opponents": ["CHE (H)", "LIV (A)"],
        "difficulty": 3.5,
        "fixture_count": 2,
        # No matches played yet: every club is average (1.4 goals a match),
        # so only the venue differs: exp(-1.4 * 0.9) at home, exp(-1.4 * 1.1) away.
        "clean_sheet_chances": [0.284, 0.214],
    }
    assert arsenal["fixtures"][1] == {
        "event": 4,
        "opponents": [],
        "difficulty": None,
        "fixture_count": 0,
        "clean_sheet_chances": [],
    }
    chelsea = next(team for team in result["teams"] if team["team_short"] == "CHE")
    assert chelsea["fixtures"][0]["opponents"] == ["ARS (A)"]
    assert chelsea["fixtures"][0]["difficulty"] == 4.0


def test_get_fixture_matrix_defaults_to_next_gameweek_and_official_paths(monkeypatch):
    requested = []

    def fake_get_json(path, params=None):
        requested.append(path)
        return {"bootstrap-static/": _bootstrap(), "fixtures/": _fixtures()}[path]

    monkeypatch.setattr(fixture_service, "_get_json", fake_get_json)

    result = fixture_service.get_fixture_matrix(horizon=2)

    assert result["start_event"] == 3
    assert result["gameweeks"] == [3, 4]
    assert requested == ["bootstrap-static/", "fixtures/"]


@pytest.mark.parametrize("horizon", [0, 9])
def test_fixture_matrix_rejects_horizon_outside_one_to_eight(horizon):
    with pytest.raises(ValueError, match="between 1 and 8"):
        fixture_service.build_fixture_matrix(
            _bootstrap(), _fixtures(), start_event=3, horizon=horizon
        )


def test_fixture_matrix_rejects_start_beyond_the_season():
    with pytest.raises(ValueError, match="start_event"):
        fixture_service.build_fixture_matrix(
            _bootstrap(), _fixtures(), start_event=39, horizon=3
        )


def _played_world():
    """Two clubs, two finished matches each: A creates 2.0 xG a match, B 1.0;
    A's keeper faced 1.0 xGC a match, B's 2.0."""
    bootstrap = {
        "teams": [{"id": 1, "name": "A", "short_name": "AAA"}, {"id": 2, "name": "B", "short_name": "BBB"}],
        "elements": [
            {"team": 1, "element_type": 4, "expected_goals": "4.0"},
            {"team": 1, "element_type": 1, "expected_goals": "0", "expected_goals_conceded": "2.0"},
            {"team": 2, "element_type": 4, "expected_goals": "2.0"},
            {"team": 2, "element_type": 1, "expected_goals": "0", "expected_goals_conceded": "4.0"},
        ],
    }
    fixtures = [
        {"team_h": 1, "team_a": 2, "finished": True},
        {"team_h": 2, "team_a": 1, "finished": True},
    ]
    return bootstrap, fixtures


def test_team_strengths_pull_early_rates_towards_the_league_average():
    strengths = fixture_service.team_strengths(*_played_world())
    # League average 6.0 xG over 4 club-matches = 1.5; with 4 prior matches
    # A's attack is (4.0 + 4 * 1.5) / (2 + 4).
    assert strengths[1]["league_average"] == pytest.approx(1.5)
    assert strengths[1]["xg_per_match"] == pytest.approx(10 / 6)
    assert strengths[2]["xgc_per_match"] == pytest.approx(10 / 6)
    assert strengths[1]["matches"] == 2


def test_clean_sheet_chance_is_poisson_on_expected_goals_against():
    import math

    strengths = fixture_service.team_strengths(*_played_world())
    # A at home to B: 1.5 x (B attack 8/6 / 1.5) x (A defence 8/6 / 1.5) x 0.9.
    expected = 1.5 * ((8 / 6) / 1.5) * ((8 / 6) / 1.5) * 0.9
    assert fixture_service.clean_sheet_chance(strengths, 1, 2, True) == pytest.approx(math.exp(-expected))
    # The stronger defence at home has the better chance, and home beats away.
    assert fixture_service.clean_sheet_chance(strengths, 1, 2, True) > fixture_service.clean_sheet_chance(strengths, 2, 1, True)
    assert fixture_service.clean_sheet_chance(strengths, 1, 2, True) > fixture_service.clean_sheet_chance(strengths, 1, 2, False)


def test_before_any_match_every_club_is_average():
    bootstrap, _ = _played_world()
    for player in bootstrap["elements"]:
        player["expected_goals"] = player["expected_goals_conceded"] = "0"
    strengths = fixture_service.team_strengths(bootstrap, [])
    assert strengths[1]["xg_per_match"] == pytest.approx(fixture_service.DEFAULT_GOALS_PER_MATCH)
    assert fixture_service.clean_sheet_chance(strengths, 1, 2, True) == pytest.approx(
        fixture_service.clean_sheet_chance(strengths, 2, 1, True))


def test_matrix_cells_carry_one_clean_sheet_chance_per_fixture():
    matrix = fixture_service.build_fixture_matrix(_bootstrap(), _fixtures(), start_event=3, horizon=2)
    arsenal = next(team for team in matrix["teams"] if team["team_short"] == "ARS")
    assert len(arsenal["fixtures"][0]["clean_sheet_chances"]) == 2  # double in GW3
    assert arsenal["fixtures"][1]["clean_sheet_chances"] == []  # blank in GW4
    assert all(0 < chance < 1 for chance in arsenal["fixtures"][0]["clean_sheet_chances"])
