"""Per-client request limit for the public API.

The app shares one polite budget of requests to the official FPL API
(`fpl_gateway.MAX_UPSTREAM_REQUESTS_PER_MINUTE`). Without an inbound limit a
single client could exhaust it for everyone, or pull the whole player
database in a loop. Each client IP gets `FPL_AI_RATE_LIMIT_PER_MINUTE`
requests per rolling minute (0 disables the limit, e.g. in tests).
"""
from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict, deque
from typing import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

WINDOW_SECONDS = 60.0
MAX_TRACKED_CLIENTS = 10_000
EXEMPT_PATHS = {"/health"}


def _limit() -> int:
    return int(os.getenv("FPL_AI_RATE_LIMIT_PER_MINUTE", "120"))


class _Window:
    def __init__(self) -> None:
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def allow(self, client: str, limit: int, now: float) -> tuple[bool, int]:
        with self._lock:
            hits = self._hits.pop(client, None) or deque()
            while hits and now - hits[0] >= WINDOW_SECONDS:
                hits.popleft()
            allowed = len(hits) < limit
            if allowed:
                hits.append(now)
            self._hits[client] = hits
            while len(self._hits) > MAX_TRACKED_CLIENTS:
                self._hits.popitem(last=False)
            retry_after = 0 if allowed else max(1, int(WINDOW_SECONDS - (now - hits[0])) + 1)
            return allowed, retry_after


_window = _Window()


def _client_ip(request: Request) -> str:
    """The visitor's IP behind the hosting proxy.

    uvicorn only trusts X-Forwarded-For from 127.0.0.1, so behind Railway
    `request.client` is the proxy and every visitor would share one bucket.
    The proxy appends the address it saw to X-Forwarded-For, so the last
    entry is the one a client cannot forge.
    """
    forwarded = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",") if part.strip()]
    if forwarded:
        return forwarded[-1]
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


async def rate_limit_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    limit = _limit()
    if limit <= 0 or request.url.path in EXEMPT_PATHS or request.method == "OPTIONS":
        return await call_next(request)
    client = _client_ip(request)
    allowed, retry_after = _window.allow(client, limit, time.monotonic())
    if not allowed:
        return JSONResponse(
            {"detail": "Too many requests. Please wait a moment and try again."},
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )
    return await call_next(request)
