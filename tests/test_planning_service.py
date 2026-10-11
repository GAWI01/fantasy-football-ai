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
    assert result[2].iloc[0]["projection_method"] == "fixture_scaled_v2"
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


def _status_player(**overrides):
    row = {
        "player_id": 7, "name": "Starter", "position": "MID", "team": "Alpha", "price": 7.0,
        "ml_prediction": 6.0, "predicted_points": 0.0, "difficulty": 3, "home": True,
        "xmins": 0.0, "xmins_available": 85.0, "start_probability": 0.0,
        "start_probability_available": 0.95, "status": "s", "chance_of_playing_next_round": 0,
        "news": "",
    }
    row.update(overrides)
    return pd.DataFrame([row])


def _weekly_fixtures(first_event=7, weeks=5, start_day=17):
    return pd.DataFrame([
        {"event": first_event + week, "team_h": 1, "team_a": 2, "team_h_difficulty": 3,
         "team_a_difficulty": 3, "kickoff_time": f"2026-10-{start_day + 7 * week:02d}T14:00:00Z"
         if start_day + 7 * week <= 31 else f"2026-11-{start_day + 7 * week - 31:02d}T14:00:00Z"}
        for week in range(weeks)
    ])


def _points(result):
    return [round(float(result[step].iloc[0]["predicted_points"]), 3) for step in sorted(result)]


def test_one_match_suspension_only_removes_the_target_gameweek():
    result = build_fixture_scaled_horizon(
        _status_player(news="Suspended until 20 Oct"), _weekly_fixtures(), teams(),
        prediction_event=7, horizon=5)
    points = _points(result)
    assert points[0] == 0.0
    assert all(value > 0 for value in points[1:]), points
    assert result[2].iloc[0]["availability_multiplier"] == 1.0


def test_suspension_with_later_return_date_covers_only_missed_gameweeks():
    result = build_fixture_scaled_horizon(
        _status_player(news="Suspended until 1 Nov"), _weekly_fixtures(), teams(),
        prediction_event=7, horizon=5)
    points = _points(result)
    # Kickoffs 17, 24, 31 Oct are before the return; 7 and 14 Nov are after.
    assert points[:3] == [0.0, 0.0, 0.0]
    assert points[3] > 0 and points[4] > 0


def test_suspension_without_return_date_assumes_a_single_match():
    result = build_fixture_scaled_horizon(_status_player(), _weekly_fixtures(), teams(),
                                          prediction_event=7, horizon=3)
    points = _points(result)
    assert points[0] == 0.0 and points[1] > 0 and points[2] > 0


def test_injury_with_expected_return_is_zero_until_back_then_reduced_first_week():
    result = build_fixture_scaled_horizon(
        _status_player(status="i", news="Hamstring injury - Expected back 30 Oct"),
        _weekly_fixtures(), teams(), prediction_event=7, horizon=5)
    multipliers = [float(result[step].iloc[0].get("availability_multiplier", 0.0)) for step in range(2, 6)]
    assert _points(result)[0] == 0.0
    assert multipliers == [0.0, 0.75, 1.0, 1.0]


def test_injury_with_unknown_return_recovers_gradually_not_zero_for_the_horizon():
    result = build_fixture_scaled_horizon(
        _status_player(status="i", chance_of_playing_next_round=None, news="Knee injury - Unknown return date"),
        _weekly_fixtures(), teams(), prediction_event=7, horizon=5)
    points = _points(result)
    assert points[0] == 0.0
    assert points[1] < points[2] < points[3] < points[4]
    assert points[4] == round(6.0, 3)


def test_left_club_is_unavailable_for_the_whole_horizon():
    result = build_fixture_scaled_horizon(
        _status_player(status="u", news="Has joined Al Hilal permanently"), _weekly_fixtures(), teams(),
        prediction_event=7, horizon=5)
    assert _points(result) == [0.0] * 5


def test_doubtful_player_recovers_after_the_target_gameweek():
    row = _status_player(status="d", chance_of_playing_next_round=50, predicted_points=3.0,
                         news="Ankle injury - 50% chance of playing")
    result = build_fixture_scaled_horizon(row, _weekly_fixtures(), teams(), prediction_event=7, horizon=3)
    multipliers = [float(result[step].iloc[0]["availability_multiplier"]) for step in (2, 3)]
    assert multipliers == [0.75, 1.0]


def test_blank_in_target_gameweek_does_not_zero_later_gameweeks():
    fixtures = _weekly_fixtures(first_event=8, weeks=2, start_day=24)
    row = _status_player(status="a", chance_of_playing_next_round=None, ml_prediction=0.0,
                         ml_per_fixture=5.0, predicted_points=0.0)
    result = build_fixture_scaled_horizon(row, fixtures, teams(), prediction_event=7, horizon=3)
    points = _points(result)
    assert points[0] == 0.0
    # Average-difficulty home fixtures: 5.0 x 1.03.
    assert points[1] == 5.15 and points[2] == 5.15


def test_future_minutes_use_minutes_if_available_not_the_target_week_zero():
    result = build_fixture_scaled_horizon(_status_player(), _weekly_fixtures(), teams(),
                                          prediction_event=7, horizon=2)
    assert result[1].iloc[0]["xmins"] == 0.0
    assert result[2].iloc[0]["xmins"] == 85.0
