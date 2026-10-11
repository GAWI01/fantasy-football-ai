from datetime import datetime, timezone

from backend.planning_state import build_planning_state


def _bootstrap():
    return {
        "events": [
            {
                "id": 2,
                "is_current": True,
                "finished": False,
                "deadline_time": "2026-08-28T17:30:00Z",
            },
            {
                "id": 3,
                "is_next": True,
                "finished": False,
                "deadline_time": "2026-09-04T17:30:00Z",
            },
        ]
    }


def test_live_current_gameweek_does_not_lock_future_prediction_event():
    state = build_planning_state(
        _bootstrap(),
        prediction_event=3,
        now=datetime(2026, 9, 1, 12, tzinfo=timezone.utc),
    )

    assert state == {
        "current_event": 2,
        "prediction_event": 3,
        "target_deadline_time": "2026-09-04T17:30:00+00:00",
        "actions_locked": False,
    }


def test_prediction_event_locks_at_its_own_deadline():
    state = build_planning_state(
        _bootstrap(),
        prediction_event=3,
        now=datetime(2026, 9, 4, 17, 30, tzinfo=timezone.utc),
    )

    assert state["actions_locked"] is True


def test_missing_target_event_fails_closed():
    state = build_planning_state(
        _bootstrap(),
        prediction_event=4,
        now=datetime(2026, 9, 1, 12, tzinfo=timezone.utc),
    )

    assert state["prediction_event"] == 4
    assert state["target_deadline_time"] is None
    assert state["actions_locked"] is True
