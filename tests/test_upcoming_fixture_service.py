
from backend import fixture_service


def test_upcoming_fixtures_are_chronological_across_multiple_gameweeks(monkeypatch):
    bootstrap = {
        "events": [
            {"id": 2, "is_current": True, "is_next": False, "finished": False},
            {"id": 3, "is_current": False, "is_next": True, "finished": False},
            {"id": 4, "is_current": False, "is_next": False, "finished": False},
        ],
        "teams": [
            {"id": 1, "name": "Chelsea", "short_name": "CHE"},
            {"id": 2, "name": "Brighton", "short_name": "BHA"},
            {"id": 3, "name": "Arsenal", "short_name": "ARS"},
        ],
        "elements": [{"id": 101, "web_name": "Player", "team": 1, "element_type": 3}],
    }
    picks={"picks":[{"element":101}]}
    fixtures=[
        {"id":302,"event":3,"team_h":2,"team_a":1,"team_h_difficulty":2,"team_a_difficulty":3,"kickoff_time":"2026-09-06T15:00:00Z","started":False,"finished":False},
        {"id":401,"event":4,"team_h":1,"team_a":3,"team_h_difficulty":2,"team_a_difficulty":4,"kickoff_time":"2026-09-12T12:30:00Z","started":False,"finished":False},
        {"id":301,"event":3,"team_h":1,"team_a":3,"team_h_difficulty":4,"team_a_difficulty":2,"kickoff_time":"2026-09-05T12:30:00Z","started":False,"finished":False},
    ]
    def fake(path, params=None):
        return {"bootstrap-static/":bootstrap,"entry/123/event/2/picks/":picks,"fixtures/":fixtures}[path]
    monkeypatch.setattr(fixture_service,"_get_json",fake)
    result=fixture_service.get_upcoming_team_fixtures(123,limit=3)
    assert [x["fixture_id"] for x in result["fixtures"]]==[301,302,401]
    assert result["fixtures"][0]["home_team"]=="Chelsea"
    assert result["fixtures"][0]["away_team"]=="Arsenal"
