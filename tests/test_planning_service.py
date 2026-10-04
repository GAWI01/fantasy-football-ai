import pandas as pd
from time import perf_counter

from backend.planning_service import build_fixture_scaled_horizon


def predictions():
    return pd.DataFrame([
        {
            "player_id": 1,
            "name": "Forward",
            "position": "FWD",
            "team": "Alpha",
            "price": 8.0,
            "predicted_points": 10.0,
            "difficulty": 2,
            "home": True,
            "xmins": 90,
        },
    ])


def teams():
    return pd.DataFrame([
        {"id": 1, "name": "Alpha", "short_name": "ALP"},
        {"id": 2, "name": "Beta", "short_name": "BET"},
        {"id": 3, "name": "Gamma", "short_name": "GAM"},
    ])


def test_future_fixture_strength_changes_projection_and_labels_method():
    fixtures = pd.DataFrame([
        {"event": 3, "team_h": 1, "team_a": 2, "team_h_difficulty": 2, "team_a_difficulty": 4},
        {"event": 4, "team_h": 3, "team_a": 1, "team_h_difficulty": 2, "team_a_difficulty": 5},
    ])

    result = build_fixture_scaled_horizon(predictions(), fixtures, teams(), prediction_event=3, horizon=2)

    assert sorted(result) == [1, 2]
    assert result[1].iloc[0]["predicted_points"] == 10.0
    assert result[1].iloc[0]["projection_method"] == "native_model"
    assert result[2].iloc[0]["gameweek"] == 4
    assert result[2].iloc[0]["opponent"] == "Gamma"
    assert result[2].iloc[0]["predicted_points"] == 7.297
    assert result[2].iloc[0]["projection_method"] == "fixture_scaled_v1"
    assert result[2].iloc[0]["uncertainty"] > result[1].iloc[0]["uncertainty"]


def test_blank_and_double_gameweeks_are_explicit():
    fixtures = pd.DataFrame([
        {"event": 5, "team_h": 1, "team_a": 2, "team_h_difficulty": 3, "team_a_difficulty": 3},
        {"event": 5, "team_h": 3, "team_a": 1, "team_h_difficulty": 3, "team_a_difficulty": 4},
    ])

    result = build_fixture_scaled_horizon(predictions(), fixtures, teams(), prediction_event=3, horizon=3)

    blank = result[2].iloc[0]
    double = result[3].iloc[0]
    assert blank["predicted_points"] == 0.0
    assert blank["projection_method"] == "blank_gameweek"
    assert double["fixture_count"] == 2
    assert double["predicted_points"] > 10.0
    assert double["opponent"] == "Beta / Gamma"


def test_double_base_gw_is_not_counted_twice_in_single_future_gw():
    players = predictions()
    players['difficulty'] = 3
    players['home'] = True
    fixtures = pd.DataFrame([
        {'event': event, 'team_h': 1, 'team_a': opponent,
         'team_h_difficulty': 3, 'team_a_difficulty': 3}
        for event, opponent in [(3, 2), (3, 3), (4, 2)]
    ])
    result = build_fixture_scaled_horizon(players, fixtures, teams(), prediction_event=3, horizon=2)
    assert result[1].iloc[0]['fixture_count'] == 2
    assert result[2].iloc[0]['predicted_points'] == 5.0


def test_horizon_stops_at_final_official_gameweek():
    fixtures = pd.DataFrame(columns=['event', 'team_h', 'team_a', 'team_h_difficulty', 'team_a_difficulty'])
    result = build_fixture_scaled_horizon(predictions(), fixtures, teams(), prediction_event=38, horizon=5)
    assert len(result) == 1
    assert result[1].iloc[0]['gameweek'] == 38


def test_full_five_gameweek_horizon_stays_within_interactive_latency_budget():
    team_rows = [
        {"id": team_id, "name": f"Team {team_id}", "short_name": f"T{team_id}"}
        for team_id in range(1, 21)
    ]
    player_rows = [
        {
            "player_id": player_id,
            "name": f"Player {player_id}",
            "position": "MID",
            "team": f"Team {((player_id - 1) % 20) + 1}",
            "price": 6.0,
            "predicted_points": 5.0,
            "difficulty": 3,
            "home": True,
        }
        for player_id in range(1, 601)
    ]
    fixture_rows = []
    for event in range(3, 8):
        for team_h in range(1, 20, 2):
            fixture_rows.append({
                "event": event,
                "team_h": team_h,
                "team_a": team_h + 1,
                "team_h_difficulty": 2,
                "team_a_difficulty": 4,
            })

    started = perf_counter()
    result = build_fixture_scaled_horizon(
        pd.DataFrame(player_rows),
        pd.DataFrame(fixture_rows),
        pd.DataFrame(team_rows),
        prediction_event=3,
        horizon=5,
    )
    duration = perf_counter() - started

    assert len(result) == 5
    assert all(len(frame) == 600 for frame in result.values())
    assert result[5].iloc[0]["opponent"] == "Team 2"
    assert duration < 0.5, f"five-Gameweek horizon took {duration:.2f}s"
