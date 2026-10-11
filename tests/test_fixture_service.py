from backend.fixture_service import (
    normalize_fixtures,
)


def test_normalize_fixtures_maps_home_away_and_difficulty():
    fixtures = [
        {
            "id": 100,
            "event": 3,
            "team_h": 1,
            "team_a": 2,
            "team_h_difficulty": 2,
            "team_a_difficulty": 4,
            "kickoff_time": "2026-08-31T15:00:00Z",
            "started": False,
            "finished": False,
        }
    ]
    teams = {
        1: {"name": "Arsenal", "short_name": "ARS"},
        2: {"name": "Liverpool", "short_name": "LIV"},
    }

    home = normalize_fixtures(fixtures, teams, {1})[0]
    away = normalize_fixtures(fixtures, teams, {2})[0]

    assert home["home"] is True
    assert home["opponent_short"] == "LIV"
    assert home["difficulty"] == 2

    assert away["home"] is False
    assert away["opponent_short"] == "ARS"
    assert away["difficulty"] == 4


def test_normalize_fixtures_supports_multiple_selected_clubs():
    fixtures = [
        {
            "id": 101,
            "event": 2,
            "team_h": 14,
            "team_a": 18,
            "team_h_difficulty": 3,
            "team_a_difficulty": 4,
            "kickoff_time": "2026-08-29T11:30:00Z",
            "started": False,
            "finished": False,
        },
        {
            "id": 102,
            "event": 2,
            "team_h": 9,
            "team_a": 3,
            "team_h_difficulty": 3,
            "team_a_difficulty": 3,
            "kickoff_time": "2026-08-29T14:00:00Z",
            "started": False,
            "finished": False,
        },
    ]
    teams = {
        14: {"name": "Liverpool", "short_name": "LIV"},
        18: {"name": "Nott'm Forest", "short_name": "NFO"},
        9: {"name": "Everton", "short_name": "EVE"},
        3: {"name": "Bournemouth", "short_name": "BOU"},
    }

    result = normalize_fixtures(fixtures, teams, {14, 9})

    assert len(result) == 2
    assert result[0]["team_short"] == "LIV"
    assert result[1]["team_short"] == "EVE"
