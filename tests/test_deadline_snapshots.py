"""Pre-deadline archives must describe what was actually acquired."""

import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
import requests

from historical_data import deadline_snapshots as snapshots


def test_release_inventory_only_deduplicates_completed_nonempty_uploads():
    """A failed GitHub upload must not prevent the next attempt to archive."""
    import re
    import shutil
    import subprocess
    from pathlib import Path

    jq = shutil.which("jq")
    if not jq:
        pytest.skip("jq is required to check the GitHub-hosted workflow query")
    workflow = (Path(__file__).resolve().parents[1] /
                ".github/workflows/deadline-snapshots.yml").read_text()
    query = next(query for query in re.findall(r"--jq '([^']+)'", workflow)
                 if query.endswith(".name"))
    assets = [
        {"name": "snapshot-complete.tar.gz", "state": "uploaded", "size": 120},
        {"name": "snapshot-failed.tar.gz", "state": "starter", "size": 0},
        {"name": "snapshot-empty.tar.gz", "state": "uploaded", "size": 0},
        {"name": "snapshot-unfinished.tar.gz", "state": "starter", "size": 120},
    ]
    result = subprocess.run([jq, "-r", query], input=json.dumps(assets), text=True,
                            capture_output=True, check=True)
    assert result.stdout.splitlines() == ["snapshot-complete.tar.gz"]


DEADLINE = datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)


def bootstrap():
    return {
        "events": [
            {"id": 7, "deadline_time": "2026-10-03T10:00:00Z", "is_current": True, "is_next": False},
            {"id": 8, "deadline_time": "2026-10-17T10:00:00Z", "is_current": False, "is_next": False},
            {"id": 9, "deadline_time": "2026-10-24T10:00:00Z", "is_current": False, "is_next": True},
        ],
        "elements": [{"id": 1, "ep_this": "4.2", "ep_next": "5.1"}],
    }


class Clock:
    def __init__(self, *times):
        self.times = iter(times)
        self.last = times[-1]

    def __call__(self):
        return next(self.times, self.last)


class Response:
    def __init__(self, payload):
        self.content = json.dumps(payload, indent=1).encode()

    def raise_for_status(self):
        pass


class Session:
    def __init__(self, responses=None):
        self.responses = iter(responses or [Response(bootstrap()), Response([{"id": 1, "event": 8}])])
        self.urls = []
        self.options = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        self.options.append(kwargs)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.mark.parametrize("minutes,expected", [
    (24 * 60 + 16, None), (24 * 60 + 15, "24h"), (24 * 60, "24h"),
    (24 * 60 - 45, "24h"), (24 * 60 - 46, None),
    (106, None), (105, "90min"), (90, "90min"), (45, "90min"), (44, None), (0, None), (-1, None),
])
def test_bounded_due_windows(minutes, expected):
    assert snapshots.due_window(DEADLINE, DEADLINE - timedelta(minutes=minutes)) == expected


def test_nearest_future_event_does_not_assume_is_next_is_target():
    target = snapshots.select_target(bootstrap(), DEADLINE - timedelta(hours=24))
    assert target["id"] == 8
    assert snapshots.forecast_event_mapping(bootstrap()) == {"ep_this": [7], "ep_next": [9]}
    assert snapshots.select_target(bootstrap(), DEADLINE)["id"] == 9


def test_capture_preserves_full_raw_responses_hashes_and_real_completion_times(tmp_path):
    start = DEADLINE - timedelta(hours=24)
    session = Session()
    path = snapshots.record_snapshot(tmp_path, session=session, clock=Clock(start, start + timedelta(seconds=2), start + timedelta(seconds=3), start + timedelta(seconds=5), start + timedelta(seconds=6)))
    manifest = json.loads((path / "manifest.json").read_text())
    assert manifest["complete"] is True
    assert manifest["target_event"] == 8
    assert manifest["season"] == "2026-27"
    assert manifest["deadline_time"] == "2026-10-17T10:00:00Z"
    assert manifest["forecast_event_mapping"] == {"ep_this": [7], "ep_next": [9]}
    assert manifest["captured_at"] == "2026-10-16T10:00:06Z"
    for name in ("bootstrap-static", "fixtures"):
        source = manifest["sources"][name]
        raw = (path / source["file"]).read_bytes()
        assert source["sha256"] == hashlib.sha256(raw).hexdigest()
        assert source["url"] == snapshots.SOURCE_URLS[name]
        assert start < datetime.fromisoformat(source["completed_at"].replace("Z", "+00:00")) < DEADLINE
    assert json.loads((path / "bootstrap-static.json").read_bytes()) == bootstrap()


def test_no_fixtures_request_when_not_due_or_already_archived(tmp_path):
    session = Session()
    assert snapshots.record_snapshot(tmp_path, session=session, clock=Clock(DEADLINE - timedelta(hours=10))) is None
    assert session.urls == [snapshots.SOURCE_URLS["bootstrap-static"]]
    session = Session()
    assert snapshots.record_snapshot(tmp_path, session=session, clock=Clock(DEADLINE - timedelta(hours=24)), archived_assets=["snapshot-2026-27-gw8-24h-20261016T100000Z-123-1.tar.gz"]) is None
    assert session.urls == [snapshots.SOURCE_URLS["bootstrap-static"]]
    # Encrypted uploads count as archived too.
    session = Session()
    assert snapshots.record_snapshot(tmp_path, session=session, clock=Clock(DEADLINE - timedelta(hours=24)), archived_assets=["snapshot-2026-27-gw8-24h-20261016T100000Z-123-1.tar.gz.enc"]) is None
    assert session.urls == [snapshots.SOURCE_URLS["bootstrap-static"]]


def test_rerun_cannot_overwrite_or_make_duplicate_complete_bundle(tmp_path):
    clock = Clock(DEADLINE - timedelta(hours=24))
    path = snapshots.record_snapshot(tmp_path, session=Session(), clock=clock)
    before = {file.name: file.read_bytes() for file in path.iterdir()}
    session = Session()
    assert snapshots.record_snapshot(tmp_path, session=session, clock=clock) is None
    assert {file.name: file.read_bytes() for file in path.iterdir()} == before
    assert session.urls == [snapshots.SOURCE_URLS["bootstrap-static"]]


def test_deadline_crossed_during_bootstrap_does_not_capture_later_event(tmp_path):
    with pytest.raises(snapshots.SnapshotError, match="deadline"):
        snapshots.record_snapshot(tmp_path, session=Session(), clock=Clock(DEADLINE - timedelta(seconds=1), DEADLINE + timedelta(seconds=1)))
    assert not list(tmp_path.rglob("manifest.json"))


def test_deadline_crossed_during_fixtures_fails_closed(tmp_path):
    with pytest.raises(snapshots.SnapshotError, match="deadline"):
        snapshots.record_snapshot(tmp_path, session=Session(), clock=Clock(DEADLINE - timedelta(minutes=45), DEADLINE - timedelta(minutes=44), DEADLINE - timedelta(minutes=44), DEADLINE))
    assert not list(tmp_path.rglob("manifest.json"))


def test_second_source_failure_does_not_advertise_partial_snapshot(tmp_path):
    session = Session([Response(bootstrap()), requests.Timeout("slow"), requests.Timeout("slow"), requests.Timeout("slow")])
    with pytest.raises(snapshots.SnapshotError):
        snapshots.record_snapshot(tmp_path, session=session, clock=Clock(DEADLINE - timedelta(hours=24)), sleeper=lambda _: None)
    assert not list(tmp_path.rglob("manifest.json"))
    assert len(session.urls) == 4
    assert all(option["timeout"] == (5, 20) for option in session.options)
    assert all("deadline-snapshots" in option["headers"]["User-Agent"] for option in session.options)


def test_bounded_retry_can_recover(tmp_path):
    session = Session([requests.Timeout("slow"), Response(bootstrap()), Response([])])
    path = snapshots.record_snapshot(tmp_path, session=session, clock=Clock(DEADLINE - timedelta(hours=24)), sleeper=lambda _: None)
    assert path.is_dir()
    assert len(session.urls) == 3


def test_manual_capture_is_predeadline_and_labels_actual_timing(tmp_path):
    now = DEADLINE - timedelta(hours=10)
    path = snapshots.record_snapshot(tmp_path, session=Session(), clock=Clock(now), force=True)
    manifest = json.loads((path / "manifest.json").read_text())
    assert manifest["capture_window"] == "manual"
    assert manifest["captured_at"] == "2026-10-17T00:00:00Z"
    assert manifest["seconds_before_deadline"] == 36000


def test_failed_atomic_publish_has_no_complete_bundle(tmp_path, monkeypatch):
    def fail(*_args):
        raise OSError("disk full")

    monkeypatch.setattr(snapshots.os, "rename", fail)
    with pytest.raises(OSError, match="disk full"):
        snapshots.record_snapshot(tmp_path, session=Session(), clock=Clock(DEADLINE - timedelta(hours=24)))
    assert not list(tmp_path.rglob("manifest.json"))


def test_deadline_crossed_before_bundle_completion_fails_closed(tmp_path):
    with pytest.raises(snapshots.SnapshotError, match="deadline"):
        snapshots.record_snapshot(tmp_path, session=Session(), clock=Clock(DEADLINE - timedelta(minutes=45), DEADLINE - timedelta(minutes=44), DEADLINE - timedelta(minutes=44), DEADLINE - timedelta(seconds=1), DEADLINE))
    assert not list(tmp_path.rglob("manifest.json"))


def test_existing_reservation_prevents_concurrent_complete_capture(tmp_path):
    (tmp_path / ".2026-27-gw8-24h.lock").mkdir()
    session = Session()
    assert snapshots.record_snapshot(tmp_path, session=session, clock=Clock(DEADLINE - timedelta(hours=24))) is None
    assert session.urls == [snapshots.SOURCE_URLS["bootstrap-static"]]


def test_no_upcoming_event_needs_no_fixtures(tmp_path):
    session = Session()
    assert snapshots.record_snapshot(tmp_path, session=session, clock=Clock(DEADLINE + timedelta(days=10))) is None
    assert session.urls == [snapshots.SOURCE_URLS["bootstrap-static"]]


def test_workflow_never_uploads_unencrypted_data():
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/deadline-snapshots.yml").read_text()
    assert "secrets.SNAPSHOT_ARCHIVE_KEY" in workflow
    assert "openssl enc -aes-256-cbc" in workflow
    upload = [line for line in workflow.splitlines() if "gh release upload" in line]
    assert upload == ['          gh release upload "$tag" "$asset"']
    assert 'asset="${plain}.enc"' in workflow
