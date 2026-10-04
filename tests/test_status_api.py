from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import backend.main as main


app = main.app


def test_status_v1_reports_official_and_model_freshness(monkeypatch):
    gateway_result = SimpleNamespace(
        data={
            "events": [
                {"id": 2, "is_current": True, "is_next": False},
                {"id": 3, "is_current": False, "is_next": True},
            ],
            "elements": [{"id": 1}, {"id": 2}],
            "teams": [{"id": index} for index in range(1, 21)],
        },
        fetched_at=datetime(2026, 8, 31, 18, tzinfo=timezone.utc),
        stale=False,
    )
    monkeypatch.setattr(
        main,
        "default_gateway",
        SimpleNamespace(get_json=lambda path, ttl_seconds: gateway_result),
        raising=False,
    )
    monkeypatch.setattr(
        main,
        "load_current_manifest",
        lambda path: SimpleNamespace(
            season="2026-27",
            prediction_event=3,
            prediction_file="gw3_predictions_v11.csv",
            prediction_path=Path("gw3_predictions_v11.csv"),
            generated_at=datetime(2026, 8, 31, 17, tzinfo=timezone.utc),
            player_count=623,
            schema_version=1,
            model_provenance=None,
        ),
        raising=False,
    )

    response = TestClient(app).get("/api/v1/status")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["official"]["current_event"] == 2
    assert body["data"]["official"]["next_event"] == 3
    assert body["data"]["official"]["player_count"] == 2
    assert body["data"]["model"]["prediction_event"] == 3
    assert body["data"]["service_state"] == "degraded"
    assert body["data"]["model"]["validation_state"] == "unverified"
    assert body["meta"]["official"]["source"] == "official"
    assert body["meta"]["model"]["source"] == "model"
    assert body["data"]["model"]["generated_at"] == "2026-08-31T17:00:00+00:00"
    assert body["data"]["model"]["target_event"] == 3
    assert body["data"]["model"]["matches_target_event"] is True
    assert body["data"]["artifacts"]["loaded"] is True


def _official(monkeypatch, *, target=4, stale=False):
    monkeypatch.setattr(main, "default_gateway", SimpleNamespace(get_json=lambda *a, **k: SimpleNamespace(
        data={"events": [{"id": target, "is_next": True}], "elements": [], "teams": []},
        fetched_at=datetime.now(timezone.utc), stale=stale,
    )))


def test_status_rejects_old_target_even_with_valid_artifacts(monkeypatch):
    _official(monkeypatch)
    body = TestClient(app).get("/api/v1/status").json()
    assert body["data"]["artifacts"]["loaded"] is True
    assert body["data"]["model"]["matches_target_event"] is False
    assert body["data"]["service_state"] == "degraded"
    assert any("GW4" in error["message"] for error in body["errors"])


def test_status_reports_missing_artifacts_without_breaking_liveness(monkeypatch):
    _official(monkeypatch, target=3)
    def missing(_directory):
        raise ValueError("Missing current-data file: teams_current.csv")
    monkeypatch.setattr(main, "validate_runtime_artifacts", missing)
    client = TestClient(app)
    body = client.get("/api/v1/status").json()
    assert body["data"]["artifacts"]["loaded"] is False
    assert body["data"]["service_state"] == "degraded"
    assert any(error["area"] == "artifacts" for error in body["errors"])
    assert client.get("/health").json() == {"status": "ok"}


def test_cached_official_data_cannot_report_ready(monkeypatch):
    _official(monkeypatch, target=3, stale=True)
    body = TestClient(app).get("/api/v1/status").json()
    assert body["data"]["service_state"] == "degraded"
    assert body["meta"]["official"]["stale"] is True


def test_unknown_target_cannot_report_ready(monkeypatch):
    _official(monkeypatch, target=None)
    body = TestClient(app).get("/api/v1/status").json()
    assert body["data"]["service_state"] == "degraded"
    assert body["data"]["model"]["matches_target_event"] is None
