"""Refresh official data and publish the next-Gameweek forecast when it is due.

`python -m historical_data.refresh_predictions` is the single refresh command,
suitable for a scheduled job. It:

1. refreshes the official current-data snapshot (players, teams, fixtures, Gameweeks);
2. refreshes the current season's completed fixture history and scores each
   newly finished Gameweek's pre-deadline forecast (historical_data.forecast_check);
3. publishes the next Gameweek's forecast once every earlier Gameweek is
   finished and data-checked (otherwise it reports that the forecast is not due);
4. validates the serving bundle.

It decides what is worth committing: a new forecast, or a change to the
fixture schedule (Gameweek, clubs or kickoff). Prices and ownership move all
the time and alone are not worth a commit. The decision is printed and, when
$GITHUB_OUTPUT is set, also written there.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.runtime_artifacts import validate_runtime_artifacts  # noqa: E402
from historical_data import fetch_season_history, forecast_check  # noqa: E402
from historical_data.current_data import fetch_current_fpl, predict_gw  # noqa: E402

CURRENT_DIR = PROJECT_ROOT / "historical_data" / "current_data"
SCHEDULE_COLUMNS = ["id", "event", "team_h", "team_a", "kickoff_time"]


def _bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


def schedule_signature(path: Path) -> str | None:
    """Digest of what defines the fixture schedule, ignoring scores and live status."""
    if not path.is_file():
        return None
    frame = pd.read_csv(path)
    columns = [column for column in SCHEDULE_COLUMNS if column in frame.columns]
    table = frame[columns].sort_values("id").astype(str).to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(table.encode("utf-8")).hexdigest()


def refresh() -> dict:
    manifest_before = _bytes(CURRENT_DIR / "manifest.json")
    schedule_before = schedule_signature(CURRENT_DIR / "fixtures_current.csv")

    fetch_current_fpl.main()
    season = None
    try:
        season = fetch_season_history.fetch_season()["season"]
    except fetch_season_history.SeasonHistoryError as exc:
        if "No completed Gameweek" not in str(exc):
            raise
        print(f"Season history: {exc}")

    checks = []
    if season:
        history_path = PROJECT_ROOT / "historical_data" / season / "merged_gw.csv"
        checks = forecast_check.check_finished_gameweeks(
            season, pd.read_csv(history_path), pd.read_csv(CURRENT_DIR / "gameweeks_current.csv"))
        forecast_check.announce(checks)

    forecast = None
    try:
        forecast = predict_gw.main()
    except predict_gw.HistoryIncompleteError as exc:
        print(f"Forecast not due: {exc}")

    validate_runtime_artifacts()
    new_forecast = _bytes(CURRENT_DIR / "manifest.json") != manifest_before
    schedule_changed = schedule_signature(CURRENT_DIR / "fixtures_current.csv") != schedule_before
    if new_forecast and forecast is not None:
        message = f"Publish {forecast.stem.split('_')[0].upper()} forecasts from the certified model"
    elif checks:
        message = f"Check the GW{checks[-1]['gameweek']} forecast against final scores"
    elif schedule_changed:
        message = "Refresh the official fixture schedule"
    else:
        message = ""
    return {"changed": bool(message), "message": message, "season": season or ""}


def _report_failure(exc: BaseException) -> None:
    """Surface the failure as a GitHub annotation, which is visible without log access."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        message = f"{type(exc).__name__}: {exc}".replace("%", "%25").replace(chr(13), "%0D").replace(chr(10), "%0A")
        print(f"::error title=Forecast refresh failed::{message[:2000]}", flush=True)


def main() -> None:
    try:
        result = refresh()
    except Exception as exc:
        _report_failure(exc)
        raise
    print(f"changed={str(result['changed']).lower()} {result['message']}".rstrip())
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"changed={str(result['changed']).lower()}\n")
            handle.write(f"message={result['message']}\n")
            handle.write(f"season={result['season']}\n")


if __name__ == "__main__":
    main()
