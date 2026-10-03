from __future__ import annotations

import os
from collections import OrderedDict, deque
from dataclasses import dataclass
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from threading import RLock
from time import monotonic
from typing import Any, Callable

import requests


FPL_API = "https://fantasy.premierleague.com/api"
REQUEST_TIMEOUT_SECONDS = 10
# A public deployment must stay a polite, low-volume reader of the official API.
# These bounds cap memory use and the upstream request rate regardless of traffic.
MAX_CACHE_ENTRIES = int(os.getenv("FPL_AI_UPSTREAM_CACHE_ENTRIES", "2000"))
MAX_UPSTREAM_REQUESTS_PER_MINUTE = int(os.getenv("FPL_AI_UPSTREAM_MAX_PER_MINUTE", "60"))
USER_AGENT = os.getenv(
    "FPL_AI_UPSTREAM_USER_AGENT",
    "FantasyFootballAI/1.0 (independent non-commercial tool; +https://github.com/GAWI01/FPL-AI)",
)


class FplGatewayError(RuntimeError):
    """Raised when official FPL data is unavailable and no cache can help."""


@dataclass(frozen=True)
class GatewayResult:
    data: Any
    fetched_at: datetime
    stale: bool


_gateway_trace: ContextVar[list[GatewayResult] | None] = ContextVar(
    "fpl_gateway_trace",
    default=None,
)


def begin_gateway_trace() -> Token:
    return _gateway_trace.set([])


def end_gateway_trace(token: Token) -> list[GatewayResult]:
    results = list(_gateway_trace.get() or [])
    _gateway_trace.reset(token)
    return results


def _record(result: GatewayResult) -> GatewayResult:
    trace = _gateway_trace.get()
    if trace is not None:
        trace.append(result)
    return result


@dataclass(frozen=True)
class _CacheEntry:
    data: Any
    fetched_at: datetime
    stored_at: float


class FplGateway:
    def __init__(
        self,
        *,
        http_get: Callable[..., Any] = requests.get,
        clock: Callable[[], float] = monotonic,
        max_entries: int = MAX_CACHE_ENTRIES,
        max_requests_per_minute: int = MAX_UPSTREAM_REQUESTS_PER_MINUTE,
    ) -> None:
        if max_entries < 1 or max_requests_per_minute < 1:
            raise ValueError("gateway limits must be positive")
        self._http_get = http_get
        self._clock = clock
        self._max_entries = max_entries
        self._max_requests_per_minute = max_requests_per_minute
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._request_times: deque[float] = deque()
        self._lock = RLock()

    def _take_request_slot(self) -> bool:
        """Reserve one upstream request within the rolling one-minute budget."""
        with self._lock:
            now = self._clock()
            while self._request_times and now - self._request_times[0] >= 60:
                self._request_times.popleft()
            if len(self._request_times) >= self._max_requests_per_minute:
                return False
            self._request_times.append(now)
            return True

    @staticmethod
    def _url(path: str) -> str:
        if path.startswith(f"{FPL_API}/"):
            return path
        return f"{FPL_API}/{path.lstrip('/')}"

    def get_json(self, path: str, ttl_seconds: int) -> GatewayResult:
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds cannot be negative")

        url = self._url(path)
        with self._lock:
            now = self._clock()
            cached = self._cache.get(url)
            if cached is not None:
                self._cache.move_to_end(url)
            if cached is not None and now - cached.stored_at <= ttl_seconds:
                return _record(GatewayResult(
                    data=cached.data,
                    fetched_at=cached.fetched_at,
                    stale=False,
                ))

        last_error: Exception | None = None
        data: Any | None = None
        for _attempt in range(2):
            if not self._take_request_slot():
                last_error = FplGatewayError("upstream request budget exhausted")
                break
            try:
                response = self._http_get(
                    url,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, (dict, list)):
                    raise TypeError("FPL API JSON must be an object or list")
                break
            except (requests.RequestException, OSError, ValueError, TypeError) as exc:
                last_error = exc

        if data is None:
            with self._lock:
                cached = self._cache.get(url) or cached
            if cached is not None:
                return _record(GatewayResult(
                    data=cached.data,
                    fetched_at=cached.fetched_at,
                    stale=True,
                ))
            raise FplGatewayError(f"FPL API request failed: {url}") from last_error

        fetched_at = datetime.now(timezone.utc)
        with self._lock:
            self._cache[url] = _CacheEntry(
                data=data,
                fetched_at=fetched_at,
                stored_at=self._clock(),
            )
            self._cache.move_to_end(url)
            while len(self._cache) > self._max_entries:
                self._cache.popitem(last=False)
        return _record(GatewayResult(
            data=data,
            fetched_at=fetched_at,
            stale=False,
        ))


default_gateway = FplGateway()
