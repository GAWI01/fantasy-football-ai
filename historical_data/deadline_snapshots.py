"""Record public FPL responses at their actual pre-deadline acquisition time."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import uuid4

import requests


SOURCE_URLS = {
    "bootstrap-static": "https://fantasy.premierleague.com/api/bootstrap-static/",
    "fixtures": "https://fantasy.premierleague.com/api/fixtures/",
}
USER_AGENT = "fantasy-football-ai/deadline-snapshots (public-data archive)"
WINDOWS = {"24h": timedelta(hours=24), "90min": timedelta(minutes=90)}


class SnapshotError(RuntimeError):
    """An acquisition cannot be advertised as a complete pre-deadline bundle."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise SnapshotError("Acquisition clock must include a UTC offset")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _deadline(event: dict) -> datetime:
    return _utc(datetime.fromisoformat(event["deadline_time"].replace("Z", "+00:00")))


def select_target(bootstrap: dict, now: datetime) -> dict | None:
    """Nearest future deadline, independently of the upstream event flags."""
    future = [event for event in bootstrap["events"] if _deadline(event) > _utc(now)]
    return min(future, key=_deadline) if future else None


def forecast_event_mapping(bootstrap: dict) -> dict:
    """Preserve official flags; absent/ambiguous mappings remain explicit lists."""
    return {
        "ep_this": [event["id"] for event in bootstrap["events"] if event.get("is_current")],
        "ep_next": [event["id"] for event in bootstrap["events"] if event.get("is_next")],
    }


def due_window(deadline: datetime, now: datetime) -> str | None:
    """Allow 15 minutes early and at most 45 minutes late relative to a target."""
    remaining = _utc(deadline) - _utc(now)
    if remaining <= timedelta(0):
        return None
    for name, lead in WINDOWS.items():
        if lead - timedelta(minutes=45) <= remaining <= lead + timedelta(minutes=15):
            return name
    return None


def _fetch(name, session, clock, sleeper):
    started = _utc(clock())
    for attempt in range(3):
        try:
            response = session.get(
                SOURCE_URLS[name], timeout=(5, 20), headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            raw = response.content
            completed = _utc(clock())
            payload = json.loads(raw)
            if completed < started:
                raise SnapshotError("Acquisition clock moved backwards")
            expected = dict if name == "bootstrap-static" else list
            if not isinstance(payload, expected):
                raise SnapshotError(f"Unexpected JSON shape for {name}")
            return raw, payload, {
                "url": SOURCE_URLS[name], "file": f"{name}.json",
                "started_at": _iso(started), "completed_at": _iso(completed),
                "sha256": hashlib.sha256(raw).hexdigest(), "attempts": attempt + 1,
            }, started, completed
        except (requests.RequestException, ValueError) as error:
            if attempt == 2:
                raise SnapshotError(f"Could not acquire {name} after 3 attempts") from error
            sleeper(2 ** attempt)
    raise AssertionError("unreachable")


def record_snapshot(
    output_dir: Path,
    *,
    session=None,
    clock: Callable[[], datetime] = _utc_now,
    sleeper: Callable[[float], None] = time.sleep,
    archived_assets: list[str] | None = None,
    force: bool = False,
) -> Path | None:
    """Return a new complete bundle, or None when no scheduled capture is needed."""
    session = session or requests.Session()
    bootstrap_raw, bootstrap, bootstrap_source, started, completed = _fetch("bootstrap-static", session, clock, sleeper)
    # Use the start time to prevent a slow response silently switching Gameweeks.
    target = select_target(bootstrap, started)
    if target is None:
        return None
    deadline = _deadline(target)
    if completed >= deadline:
        raise SnapshotError("Target deadline crossed during bootstrap acquisition")
    window = "manual" if force else due_window(deadline, started)
    if window is None:
        return None
    first_deadline = min(_deadline(event) for event in bootstrap["events"])
    season_start = first_deadline.year if first_deadline.month >= 7 else first_deadline.year - 1
    season = f"{season_start}-{(season_start + 1) % 100:02d}"
    key = f"{season}-gw{target['id']}-{window}"
    if not force and any(name.startswith(f"snapshot-{key}-") and name.endswith(".tar.gz") for name in archived_assets or []):
        return None
    if force:
        key += f"-{started.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:12]}"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / key
    if destination.exists():
        return None
    # Exclusive reservation serializes writers; a crashed reservation fails closed.
    reservation = output_dir / f".{key}.lock"
    try:
        reservation.mkdir()
    except FileExistsError:
        return None
    stage = None
    try:
        if destination.exists():
            return None
        fixture_raw, _, fixture_source, _, fixture_completed = _fetch("fixtures", session, clock, sleeper)
        if fixture_completed >= deadline:
            raise SnapshotError("Target deadline crossed during fixtures acquisition")
        stage = Path(tempfile.mkdtemp(prefix=f".{key}.partial-", dir=output_dir))
        (stage / "bootstrap-static.json").write_bytes(bootstrap_raw)
        (stage / "fixtures.json").write_bytes(fixture_raw)
        captured = _utc(clock())
        if captured >= deadline:
            raise SnapshotError("Target deadline crossed before bundle completion")
        if captured < fixture_completed or fixture_completed < completed:
            raise SnapshotError("Acquisition clock moved backwards")
        manifest = {
            "schema_version": 1, "complete": True,
            "season": season, "target_event": target["id"],
            "deadline_time": _iso(deadline), "capture_window": window,
            "capture_started_at": _iso(started), "captured_at": _iso(captured),
            "seconds_before_deadline": (deadline - captured).total_seconds(),
            "intended_capture_at": _iso(deadline - WINDOWS[window]) if window in WINDOWS else None,
            "forecast_event_mapping": forecast_event_mapping(bootstrap),
            "sources": {"bootstrap-static": bootstrap_source, "fixtures": fixture_source},
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        # Only this successful rename exposes a complete bundle to callers.
        os.rename(stage, destination)
        stage = None
        return destination
    finally:
        if stage is not None:
            shutil.rmtree(stage)
        reservation.rmdir()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("output/deadline-snapshots"))
    parser.add_argument("--archived-assets", type=Path, help="JSON array of existing GitHub Release asset names")
    parser.add_argument("--force", action="store_true", help="Capture now as a distinctly labelled manual pre-deadline bundle")
    args = parser.parse_args(argv)
    try:
        assets = json.loads(args.archived_assets.read_text()) if args.archived_assets else []
        if not isinstance(assets, list) or not all(isinstance(name, str) for name in assets):
            raise SnapshotError("Archived assets must be a JSON array of strings")
        path = record_snapshot(args.output_dir, archived_assets=assets, force=args.force)
        print(json.dumps({"captured": path is not None, "bundle": str(path.resolve()) if path else None}))
        if path and os.environ.get("GITHUB_OUTPUT"):
            manifest = json.loads((path / "manifest.json").read_text())
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                output.write(f"captured=true\nbundle={path.resolve()}\nseason={manifest['season']}\n")
        return 0
    except (SnapshotError, OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Snapshot failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
