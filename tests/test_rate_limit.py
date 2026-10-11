from fastapi.testclient import TestClient

import backend.main as main
from backend import rate_limit


def test_a_client_over_the_limit_gets_429_and_health_stays_open(monkeypatch):
    monkeypatch.setenv("FPL_AI_RATE_LIMIT_PER_MINUTE", "3")
    monkeypatch.setattr(rate_limit, "_window", rate_limit._Window())
    client = TestClient(main.app)

    codes = [client.get("/api/v1/review/0").status_code for _ in range(4)]

    assert codes[:3] == [400, 400, 400]
    assert codes[3] == 429
    assert client.get("/api/v1/review/0").headers["Retry-After"]
    assert client.get("/health").status_code == 200


def test_the_window_rolls_after_a_minute():
    window = rate_limit._Window()
    assert window.allow("a", 1, 0.0)[0]
    assert not window.allow("a", 1, 30.0)[0]
    assert window.allow("b", 1, 30.0)[0]
    assert window.allow("a", 1, 61.0)[0]


def test_visitors_behind_the_proxy_get_their_own_limit(monkeypatch):
    monkeypatch.setenv("FPL_AI_RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setattr(rate_limit, "_window", rate_limit._Window())
    client = TestClient(main.app)

    first = client.get("/api/v1/review/0", headers={"X-Forwarded-For": "203.0.113.5"})
    other = client.get("/api/v1/review/0", headers={"X-Forwarded-For": "198.51.100.7"})
    # A spoofed first hop does not escape the limit: the proxy's entry is last.
    again = client.get("/api/v1/review/0", headers={"X-Forwarded-For": "1.2.3.4, 203.0.113.5"})

    assert first.status_code == 400 and other.status_code == 400
    assert again.status_code == 429
