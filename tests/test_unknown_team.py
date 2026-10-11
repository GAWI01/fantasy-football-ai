"""An unknown Team ID is a clear 404, not a server error (audit ISSUE-007)."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import fpl_gateway, main
from backend.fpl_gateway import FplGateway, FplNotFoundError


def test_gateway_does_not_retry_a_missing_resource():
    calls = []

    def http_get(url, **_):
        calls.append(url)
        return SimpleNamespace(status_code=404, raise_for_status=lambda: None, json=lambda: {})

    gateway = FplGateway(http_get=http_get)
    with pytest.raises(FplNotFoundError):
        gateway.get_json("entry/999999999/", ttl_seconds=60)
    assert len(calls) == 1


def test_dashboard_returns_404_json_with_cors_for_an_unknown_team(monkeypatch):
    def http_get(url, **_):
        return SimpleNamespace(status_code=404, raise_for_status=lambda: None, json=lambda: {})

    monkeypatch.setattr(fpl_gateway.default_gateway, "_http_get", http_get)
    fpl_gateway.default_gateway._cache.clear()
    client = TestClient(main.app)
    response = client.get("/api/v1/dashboard/999999999", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 404
    assert "No FPL team found with ID 999999999" in response.json()["detail"]
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
