from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import re
import time
from typing import Any, Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response


REQUEST_LOGGER_NAME = "fpl_ai.request"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_REQUEST_FIELDS = (
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
)


class JsonLogFormatter(logging.Formatter):
    """Serialize operational logs as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for field in _REQUEST_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def configure_json_logging() -> logging.Logger:
    logger = logging.getLogger(REQUEST_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    if not any(getattr(handler, "_fpl_ai_json", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonLogFormatter())
        handler._fpl_ai_json = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    logger.propagate = True
    return logger


request_logger = configure_json_logging()


def _request_id(value: str | None) -> str:
    if value and _REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return str(uuid4())


def _loggable_path(path: str) -> str:
    """The route without IDs: Team and league IDs identify FPL managers."""
    return re.sub(r"/\d+(?=/|$)", "/{id}", path)


async def request_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = _request_id(request.headers.get("X-Request-ID"))
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        request_logger.exception(
            "request_failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": _loggable_path(request.url.path),
                "status_code": 500,
                "duration_ms": duration_ms,
            },
        )
        raise
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    request_logger.info(
        "request_complete",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": _loggable_path(request.url.path),
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response
