from backend.league_captain import league_captain, league_mode
from backend.point_ranges import point_range


def test_point_range_grows_with_expected_points():
    low, high = point_range(2.0), point_range(7.0)
    assert low["high"] < high["high"]
    assert high["haul_chance"] > low["haul_chance"]
    assert point_range(None) is None


def test_league_mode():
    assert league_mode(0, 1, 30)["mode"] == "protect"
    assert league_mode(8, 3, 30)["mode"] == "protect"
    # Far behind early: expected points first.
    assert league_mode(129, 7, 32)["mode"] == "balanced"
    # Same gap per week in the run-in: take risks.
    assert league_mode(45, 5, 10)["mode"] == "chase"
    assert league_mode(200, 7, 30)["mode"] == "chase"


def _league(you_total, leader_total, captains, event=28):
    players = [{"player_id": pid, "captains": count, "rival_eo": 100.0 * count * 2 / 6, "you": None} for pid, count in captains.items()]
    return {
        "event": event,
        "analysed_managers": 6,
        "standings": [{"team_id": 1, "total": you_total, "rank": 4, "is_you": True},
                      {"team_id": 2, "total": leader_total, "rank": 1, "is_you": False}],
        "players": players,
    }


CANDIDATES = [{"player_id": 10, "name": "Template", "predicted_points": 6.5},
              {"player_id": 20, "name": "Punt", "predicted_points": 5.6}]


def test_protect_picks_the_player_rivals_captain():
    result = league_captain(CANDIDATES, _league(500, 505, {10: 4, 20: 0}), team_id=1)
    assert result["mode"]["mode"] == "protect"
    assert result["pick"]["name"] == "Template"
    assert result["differential_id"] == 20


def test_chase_takes_a_differential_and_shows_the_cost():
    result = league_captain(CANDIDATES, _league(400, 470, {10: 4, 20: 0}, event=30), team_id=1)
    assert result["mode"]["mode"] == "chase"
    assert result["pick"]["name"] == "Punt"
    assert result["pick"]["cost"] == 0.9


def test_balanced_keeps_expected_points():
    result = league_captain(CANDIDATES, _league(400, 460, {10: 4, 20: 0}, event=8), team_id=1)
    assert result["mode"]["mode"] == "balanced"
    assert result["pick"]["name"] == "Template"


def test_point_range_table_ships_in_the_backend_image():
    from pathlib import Path
    rules = (Path(__file__).resolve().parents[1] / ".dockerignore").read_text().splitlines()
    assert "!backend/data/point_ranges.json" in rules
