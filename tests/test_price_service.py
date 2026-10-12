from datetime import datetime, timezone

from backend.price_service import build_price_changes

NOW = datetime(2026, 10, 12, 21, 0, tzinfo=timezone.utc)


def _bootstrap():
    return {
        "game_config": {
            "settings": {"price_change_deadlines": ["2026-10-11T23:00:00Z", "2026-10-12T23:00:00Z", "2026-10-13T23:00:00Z"]},
            "status": {"price_change_last_updated": "2026-10-12T20:50:15Z"},
        },
        "teams": [{"id": 1, "name": "Brighton", "short_name": "BHA"}],
        "elements": [
            {"id": 10, "web_name": "Riser", "team": 1, "element_type": 4, "now_cost": 56, "selected_by_percent": "8.5",
             "price_change_percent": "107.2", "price_change_hourly_rate": 1961, "price_change_locked_until": None,
             "price_change_projections": [{"offset": 1, "projected_percent": "143.3", "likelihood": 5},
                                          {"offset": 0, "projected_percent": "110.2", "likelihood": 5}]},
            {"id": 11, "web_name": "Faller", "team": 1, "element_type": 3, "now_cost": 97,
             "price_change_percent": "-43.0", "price_change_projections": [{"offset": 0, "projected_percent": "-40.7", "likelihood": -3}],
             "price_change_locked_until": "2026-10-17T21:00:00Z"},
            {"id": 12, "web_name": "Gone", "removed": True, "price_change_percent": "90"},
            {"id": 13, "web_name": "No data", "team": 1, "element_type": 2},
        ],
    }


def test_official_figures_are_passed_through_and_sorted_by_pressure():
    data = build_price_changes(_bootstrap(), NOW)
    assert [p["name"] for p in data["players"]] == ["Riser", "Faller"]
    riser = data["players"][0]
    assert riser["percent"] == 107.2 and riser["price"] == 5.6 and riser["position"] == "FWD"
    assert [item["offset"] for item in riser["projections"]] == [0, 1]
    assert riser["projections"][0] == {"offset": 0, "percent": 110.2, "likelihood": 5}


def test_only_future_change_windows_and_active_locks_are_kept():
    data = build_price_changes(_bootstrap(), NOW)
    assert data["next_change_at"] == "2026-10-12T23:00:00+00:00"
    assert len(data["change_windows"]) == 2
    assert data["players"][1]["locked_until"].startswith("2026-10-17")
    later = build_price_changes(_bootstrap(), datetime(2026, 10, 18, tzinfo=timezone.utc))
    assert later["players"][1]["locked_until"] is None
    assert later["next_change_at"] is None


def test_missing_config_does_not_fail():
    assert build_price_changes({"elements": [], "teams": []}, NOW) == {
        "next_change_at": None, "change_windows": [], "updated_at": None, "players": []}


def test_riser_bonus_uses_the_strongest_of_the_next_two_windows_and_skips_locks():
    from backend.price_service import price_likelihoods, riser_bonus

    likelihoods = price_likelihoods(_bootstrap())
    assert likelihoods[10] == 5  # Riser
    assert 11 not in likelihoods  # Faller is locked
    assert riser_bonus({1: 5, 2: 4, 3: 3, 4: -4, 5: -5}) == {1: 0.4, 2: 0.25, 4: -0.25, 5: -0.4}
