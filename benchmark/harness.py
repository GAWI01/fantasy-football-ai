"""Replay recorded official FPL responses through the real API.

The decision benchmark must compare engine versions on identical inputs. A
snapshot stores every upstream JSON response the dashboard needs (bootstrap,
fixtures, entries, picks, histories, transfers, live scores). Replaying it
swaps only the HTTP layer of the shared gateway, so every backend code path
runs unchanged.

`pre_deadline_event` rewrites the bootstrap Gameweek flags so the snapshot is
seen just before that Gameweek's deadline (the served forecast's target).
"""
from __future__ import annotations

import copy
import gzip
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from backend import fpl_gateway

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"


class _Response:
    def __init__(self, url: str, payload):
        self.url, self._payload = url, payload
        self.status_code = 404 if payload is None else 200

    def raise_for_status(self):
        if self._payload is None:
            import requests
            raise requests.HTTPError(f"404 Client Error: Not Found for url: {self.url}", response=self)

    def json(self):
        return copy.deepcopy(self._payload)


def load_snapshot(name: str) -> dict:
    with gzip.open(SNAPSHOT_DIR / f"{name}.json.gz", "rt", encoding="utf-8") as handle:
        return json.load(handle)


def save_snapshot(name: str, responses: dict) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"{name}.json.gz"
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(responses, handle, sort_keys=True, separators=(",", ":"))
    return path


def _as_pre_deadline(bootstrap: dict, event: int) -> dict:
    data = copy.deepcopy(bootstrap)
    deadline = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat().replace("+00:00", "Z")
    for item in data["events"]:
        item["is_current"] = item["id"] == event - 1
        item["is_next"] = item["id"] == event
        if item["id"] >= event:
            item["finished"] = False
            item["data_checked"] = False
        if item["id"] == event:
            item["deadline_time"] = deadline
    return data


@contextmanager
def replay(responses: dict, *, pre_deadline_event: int | None = None) -> Iterator[None]:
    """Serve `responses` (url -> JSON, None for 404) through the default gateway."""
    overrides = {}
    if pre_deadline_event is not None:
        key = f"{fpl_gateway.FPL_API}/bootstrap-static/"
        overrides[key] = _as_pre_deadline(responses[key], pre_deadline_event)

    def http_get(url, **_kwargs):
        return _Response(url, overrides[url] if url in overrides else responses.get(url))

    gateway = fpl_gateway.default_gateway
    original = gateway._http_get
    gateway._http_get = http_get
    gateway._cache.clear()
    gateway._request_times.clear()
    try:
        yield
    finally:
        gateway._http_get = original
        gateway._cache.clear()
        gateway._request_times.clear()


@contextmanager
def record() -> Iterator[dict]:
    """Record every upstream JSON response fetched while the block runs."""
    responses: dict = {}
    gateway = fpl_gateway.default_gateway
    original = gateway._http_get

    def http_get(url, **kwargs):
        response = original(url, **kwargs)
        try:
            response.raise_for_status()
            responses[url] = response.json()
        except Exception:
            responses[url] = None
        return response

    gateway._http_get = http_get
    gateway._cache.clear()
    try:
        yield responses
    finally:
        gateway._http_get = original


DATA_DIR = Path(__file__).resolve().parent / "data"


@contextmanager
def pinned_data(name: str) -> Iterator[Path]:
    """Serve the forecast, manifest, fixtures and clubs pinned for a snapshot."""
    from backend import data_loader, main

    directory = DATA_DIR / name
    saved = (main.PREDICTIONS_DIR, data_loader.CURRENT_DATA_DIR)
    main.PREDICTIONS_DIR = directory
    data_loader.CURRENT_DATA_DIR = directory
    try:
        yield directory
    finally:
        main.PREDICTIONS_DIR, data_loader.CURRENT_DATA_DIR = saved
