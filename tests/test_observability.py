import json
import logging

from fastapi.testclient import TestClient

from backend.main import app
from backend.observability import JsonLogFormatter


def test_json_log_formatter_emits_machine_readable_request_fields():
    record = logging.LogRecord(
        name="fpl_ai.request",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_complete",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-123"
    record.method = "GET"
    record.path = "/health"
    record.status_code = 200
    record.duration_ms = 4.25

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["event"] == "request_complete"
    assert payload["request_id"] == "req-123"
    assert payload["method"] == "GET"
    assert payload["path"] == "/health"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] == 4.25
    assert payload["timestamp"].endswith("+00:00")


def test_request_middleware_preserves_request_id_and_logs_completion(caplog):
    with caplog.at_level(logging.INFO, logger="fpl_ai.request"):
        response = TestClient(app).get(
            "/health",
            headers={"X-Request-ID": "customer-request-7"},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "customer-request-7"
    record = next(
        item
        for item in caplog.records
        if item.name == "fpl_ai.request" and item.getMessage() == "request_complete"
    )
    assert record.method == "GET"
    assert record.path == "/health"
    assert record.status_code == 200
    assert record.duration_ms >= 0


def test_logged_paths_never_contain_team_or_league_ids():
    from backend.observability import _loggable_path

    assert _loggable_path("/api/v1/dashboard/6658075") == "/api/v1/dashboard/{id}"
    assert _loggable_path("/api/v1/league/77/rival/123") == "/api/v1/league/{id}/rival/{id}"
    assert _loggable_path("/health") == "/health"
