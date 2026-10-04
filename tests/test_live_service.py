import pytest

import backend.live_service as live_service


def test_latest_finished_event_uses_highest_finished_gameweek():
    bootstrap = {
        "events": [
            {"id": 1, "finished": True},
            {"id": 2, "finished": True},
            {"id": 3, "finished": False, "is_current": True},
        ]
    }

    assert live_service.latest_finished_event(bootstrap)["id"] == 2


def test_latest_finished_event_rejects_bootstrap_without_finished_gameweek():
    with pytest.raises(live_service.LiveDataServiceError, match="finished gameweek"):
        live_service.latest_finished_event({"events": [{"id": 1, "finished": False}]})


def test_historical_public_readers_use_official_fpl_paths(monkeypatch):
    requested = []

    def fake_get_json(path):
        requested.append(path)
        return {
            "bootstrap-static/": {"events": []},
            "entry/123/event/2/picks/": {"picks": [{"element": 1}]},
            "entry/123/transfers/": [{"event": 2, "element_in": 1}],
            "event/2/live/": {"elements": [{"id": 1, "stats": {}}]},
        }[path]

    monkeypatch.setattr(live_service, "_get_json", fake_get_json)

    assert live_service.get_bootstrap_data() == {"events": []}
    assert live_service.get_event_picks(123, 2)["picks"][0]["element"] == 1
    assert live_service.get_manager_transfers(123)[0]["event"] == 2
    assert live_service.get_event_live(2)["elements"][0]["id"] == 1
    assert requested == [
        "bootstrap-static/",
        "entry/123/event/2/picks/",
        "entry/123/transfers/",
        "event/2/live/",
    ]


@pytest.mark.parametrize("team_id", [0, -1, "123"])
def test_historical_manager_readers_require_positive_integer_team_id(team_id):
    with pytest.raises(ValueError, match="positive integer"):
        live_service.get_event_picks(team_id, 2)
    with pytest.raises(ValueError, match="positive integer"):
        live_service.get_manager_transfers(team_id)


@pytest.mark.parametrize("event", [0, 39, "2"])
def test_historical_event_readers_require_gameweek_range(event):
    with pytest.raises(ValueError, match="between 1 and 38"):
        live_service.get_event_picks(123, event)
    with pytest.raises(ValueError, match="between 1 and 38"):
        live_service.get_event_live(event)


def test_historical_public_readers_reject_wrong_payload_shapes(monkeypatch):
    monkeypatch.setattr(live_service, "_get_json", lambda path: [])
    with pytest.raises(live_service.LiveDataServiceError, match="picks response"):
        live_service.get_event_picks(123, 2)

    monkeypatch.setattr(live_service, "_get_json", lambda path: {})
    with pytest.raises(live_service.LiveDataServiceError, match="transfers response"):
        live_service.get_manager_transfers(123)

    monkeypatch.setattr(live_service, "_get_json", lambda path: [])
    with pytest.raises(live_service.LiveDataServiceError, match="event live response"):
        live_service.get_event_live(2)


def test_live_players_exposes_the_next_official_deadline(monkeypatch):
    bootstrap = {
        "events": [
            {"id": 2, "name": "Gameweek 2", "is_current": True, "finished": True},
            {
                "id": 3,
                "name": "Gameweek 3",
                "is_next": True,
                "finished": False,
                "deadline_time": "2026-09-04T17:30:00Z",
            },
        ],
        "teams": [{"id": 1, "name": "Arsenal", "short_name": "ARS"}],
        "elements": [
            {
                "id": 1,
                "web_name": "Alpha",
                "team": 1,
                "element_type": 3,
                "now_cost": 75,
                "selected_by_percent": "10.0",
                "form": "5.0",
                "ep_this": "4.0",
            }
        ],
    }
    live = {"elements": [{"id": 1, "stats": {"total_points": 7, "minutes": 90}}]}
    monkeypatch.setattr(
        live_service,
        "_get_json",
        lambda path: bootstrap if path == "bootstrap-static/" else live,
    )

    result = live_service.get_live_players()

    assert result["next_event"] == 3
    assert result["next_deadline_time"] == "2026-09-04T17:30:00Z"


def test_normalized_live_players_preserve_official_availability_news():
    bootstrap = {
        "events": [],
        "teams": [{"id": 1, "name": "Arsenal", "short_name": "ARS"}],
        "elements": [
            {
                "id": 1,
                "web_name": "Alpha",
                "team": 1,
                "element_type": 3,
                "now_cost": 75,
                "selected_by_percent": "10.0",
                "form": "5.0",
                "ep_this": "4.0",
                "status": "d",
                "chance_of_playing_next_round": 75,
                "news": "Knock - 75% chance of playing",
                "news_added": "2026-09-01T08:00:00Z",
            }
        ],
    }
    rows = live_service.normalize_live_players(
        bootstrap,
        {"elements": [{"id": 1, "stats": {"total_points": 2}}]},
    )

    assert rows[0]["status"] == "d"
    assert rows[0]["chance_of_playing_next_round"] == 75
    assert rows[0]["news"] == "Knock - 75% chance of playing"
    assert rows[0]["news_added"] == "2026-09-01T08:00:00Z"


@pytest.mark.parametrize("web_name,second_name,want", [
    (None, "Surname", "Surname"),
    ("missing", "Surname", "Surname"),
    ("", "Surname", "Surname"),
    (None, None, "Player 1"),
])
def test_live_player_name_fallback_never_displays_the_first_name(web_name, second_name, want):
    bootstrap = {
        "teams": [{"id": 1, "name": "Arsenal", "short_name": "ARS"}],
        "elements": [{"id": 1, "team": 1, "element_type": 3, "web_name": web_name,
                      "first_name": "PrivateFirst", "second_name": second_name, "now_cost": 75}],
    }
    if web_name == "missing":
        bootstrap["elements"][0].pop("web_name")
    rows = live_service.normalize_live_players(bootstrap, {"elements": []})
    assert rows[0]["name"] == want


def test_normalized_live_players_keeps_new_market_entries_without_event_stats():
    bootstrap = {
        "teams": [{"id": 1, "name": "Arsenal", "short_name": "ARS"}],
        "elements": [
            {
                "id": 1,
                "web_name": "Played",
                "team": 1,
                "element_type": 3,
                "now_cost": 75,
                "selected_by_percent": "10.0",
                "form": "5.0",
                "ep_this": "4.0",
            },
            {
                "id": 2,
                "web_name": "New signing",
                "team": 1,
                "element_type": 4,
                "now_cost": 70,
                "selected_by_percent": "0.0",
                "form": "0.0",
                "ep_this": "0.0",
            },
        ],
    }

    rows = live_service.normalize_live_players(
        bootstrap,
        {"elements": [{"id": 1, "stats": {"total_points": 6, "minutes": 90}}]},
    )

    assert [row["player_id"] for row in rows] == [1, 2]
    assert rows[1]["event_points"] == 0
    assert rows[1]["minutes"] == 0


def test_event_fixtures_expose_live_scores_and_official_match_state(monkeypatch):
    bootstrap = {
        "teams": [
            {"id": 1, "name": "Arsenal", "short_name": "ARS"},
            {"id": 2, "name": "Chelsea", "short_name": "CHE"},
        ],
    }
    fixtures = [{
        "id": 22,
        "event": 2,
        "team_h": 1,
        "team_a": 2,
        "team_h_score": 2,
        "team_a_score": 1,
        "started": True,
        "finished": False,
        "minutes": 67,
        "kickoff_time": "2026-08-29T14:00:00Z",
    }]
    requested = []

    def fake_get_json(path):
        requested.append(path)
        return bootstrap if path == "bootstrap-static/" else fixtures

    monkeypatch.setattr(live_service, "_get_json", fake_get_json)

    result = live_service.get_event_fixtures(2)

    assert requested == ["bootstrap-static/", "fixtures/?event=2"]
    assert result == {
        "event": 2,
        "fixtures": [{
            "fixture_id": 22,
            "home_team_id": 1,
            "away_team_id": 2,
            "home_team": "Arsenal",
            "home_team_short": "ARS",
            "away_team": "Chelsea",
            "away_team_short": "CHE",
            "home_score": 2,
            "away_score": 1,
            "kickoff_time": "2026-08-29T14:00:00Z",
            "started": True,
            "finished": False,
            "minutes": 67,
        }],
    }
