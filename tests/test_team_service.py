import pytest

from backend.team_service import (
    TeamServiceError,
    fetch_public_team,
    normalize_team_response,
)


def test_normalize_team_response_extracts_team_and_squad():
    payload = {
        "entry": {
            "id": 1234567,
            "name": "Test Team",
            "player_first_name": "Gabri",
            "player_last_name": "Manager",
            "bank": 15,
            "event": 3,
            "transfers": 1,
        },
        "picks": [
            {
                "element": 10,
                "position": 1,
                "multiplier": 1,
                "purchase_price": 72,
                "selling_price": 76,
            },
            {
                "element": 20,
                "position": 2,
                "multiplier": 1,
            },
        ],
    }

    result = normalize_team_response(
        1234567,
        payload,
    )

    assert result["team_id"] == 1234567
    assert result["name"] == "Test Team"
    assert result["manager_name"] == "Manager"
    assert result["bank"] == 1.5
    assert result["event"] == 3
    assert result["transfers"] == 1
    assert result["picks"][0]["player_id"] == 10
    assert result["picks"][0]["position"] == 1
    assert result["picks"][0]["purchase_price"] == 7.2
    assert result["picks"][0]["selling_price"] == 7.6


def test_normalize_team_response_rejects_missing_entry():
    with pytest.raises(
        TeamServiceError,
        match="entry",
    ):
        normalize_team_response(
            1234567,
            {"picks": []},
        )


def test_normalize_team_response_rejects_missing_picks():
    payload = {
        "entry": {
            "id": 1234567,
            "name": "Test Team",
        },
    }

    with pytest.raises(
        TeamServiceError,
        match="picks",
    ):
        normalize_team_response(
            1234567,
            payload,
        )


def test_fetch_public_team_rejects_invalid_team_id():
    with pytest.raises(
        TeamServiceError,
        match="Team ID",
    ):
        fetch_public_team(0)


def test_fetch_public_team_rejects_negative_team_id():
    with pytest.raises(
        TeamServiceError,
        match="Team ID",
    ):
        fetch_public_team(-123)



def test_normalize_team_response_uses_entry_history_for_team_financials():
    from backend.team_service import normalize_team_response

    entry = {
        "id": 1234567,
        "name": "Test Team",
        "current_event": 3,
        "summary_overall_rank": 100,
        "summary_event_rank": 20,
    }

    picks_payload = {
        "entry_history": {
            "event": 3,
            "bank": 21,
            "value": 987,
            "event_transfers": 1,
            "event_transfers_cost": 0,
            "points": 50,
            "total_points": 150,
            "overall_rank": 100,
            "rank": 20,
        },
        "picks": [
            {
                "element": 10,
                "position": 1,
                "multiplier": 1,
            }
        ],
    }

    result = normalize_team_response(
        1234567,
        entry,
        picks_payload=picks_payload,
    )

    assert result["bank"] == 2.1
    assert result["value"] == 98.7
    assert result["transfers"] == 1
    assert result["event"] == 3
    assert result["event_points"] == 50
    assert result["total_points"] == 150
    assert result["overall_rank"] == 100
    assert result["event_rank"] == 20

def test_fetch_public_team_uses_public_fpl_endpoint(monkeypatch):
    payload = {
        "entry": {
            "id": 1234567,
            "name": "Test Team",
            "bank": 15,
            "event": 3,
            "transfers": 1,
        },
        "picks": [
            {
                "element": 10,
                "position": 1,
                "multiplier": 1,
            },
        ],
    }

    captured = {}

    class GatewayResult:
        data = payload

    def fake_get(url, ttl_seconds):
        captured["url"] = url
        captured["ttl_seconds"] = ttl_seconds
        return GatewayResult()

    monkeypatch.setattr(
        "backend.team_service.default_gateway.get_json",
        fake_get,
    )

    result = fetch_public_team(1234567)

    assert result["team_id"] == 1234567
    assert result["name"] == "Test Team"
    assert result["picks"][0]["player_id"] == 10

    assert (
        captured["url"]
        == "https://fantasy.premierleague.com/api/entry/1234567/"
    )

    assert captured["ttl_seconds"] > 0


def test_fetch_public_team_converts_http_failure_to_team_service_error(
    monkeypatch,
):
    from backend.fpl_gateway import FplGatewayError

    def fake_get(url, ttl_seconds):
        raise FplGatewayError("FPL API returned HTTP 404")

    monkeypatch.setattr(
        "backend.team_service.default_gateway.get_json",
        fake_get,
    )

    with pytest.raises(
        TeamServiceError,
        match="not found|unavailable|HTTP",
    ):
        fetch_public_team(1234567)


def test_fetch_public_team_converts_request_failure_to_team_service_error(
    monkeypatch,
):
    from backend.fpl_gateway import FplGatewayError

    def fake_get(url, ttl_seconds):
        raise FplGatewayError("FPL API request failed: connection failed")

    monkeypatch.setattr(
        "backend.team_service.default_gateway.get_json",
        fake_get,
    )

    with pytest.raises(
        TeamServiceError,
        match="request|connection|network",
    ):
        fetch_public_team(1234567)


def test_fetch_public_team_converts_invalid_json_to_team_service_error(
    monkeypatch,
):
    from backend.fpl_gateway import FplGatewayError

    def fake_get(url, ttl_seconds):
        raise FplGatewayError("FPL API returned invalid JSON")

    monkeypatch.setattr(
        "backend.team_service.default_gateway.get_json",
        fake_get,
    )

    with pytest.raises(
        TeamServiceError,
        match="JSON|response",
    ):
        fetch_public_team(1234567)


def test_fetch_public_team_converts_malformed_response_to_team_service_error(
    monkeypatch,
):
    class GatewayResult:
        data = {
            "entry": {
                "id": 1234567,
                "name": "Test Team",
            },
        }

    def fake_get(url, ttl_seconds):
        return GatewayResult()

    monkeypatch.setattr(
        "backend.team_service.default_gateway.get_json",
        fake_get,
    )

    with pytest.raises(
        TeamServiceError,
        match="picks",
    ):
        fetch_public_team(1234567)
