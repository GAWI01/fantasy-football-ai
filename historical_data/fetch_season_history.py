"""Fetch the current season's completed fixtures in the historical merged_gw layout.

The output directory (historical_data/<season>/) gets the same files as the
archived Vaastav seasons: merged_gw.csv (one row per player and fixture),
fixtures.csv and teams.csv. Only Gameweeks that the official game marks as
finished and data-checked are included, so the history never contains
provisional live scores. The current season then flows through exactly the
same feature code as every training season.
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data_manifest import season_for_date  # noqa: E402
from backend.fpl_gateway import USER_AGENT  # noqa: E402

API = "https://fantasy.premierleague.com/api"
POSITIONS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
HISTORY_COLUMNS = (
    "element", "fixture", "opponent_team", "total_points", "was_home", "kickoff_time",
    "team_h_score", "team_a_score", "round", "minutes", "goals_scored", "assists",
    "clean_sheets", "goals_conceded", "own_goals", "penalties_saved", "penalties_missed",
    "yellow_cards", "red_cards", "saves", "bonus", "bps", "influence", "creativity",
    "threat", "ict_index", "starts", "expected_goals", "expected_assists",
    "expected_goal_involvements", "expected_goals_conceded", "clearances_blocks_interceptions",
    "recoveries", "tackles", "defensive_contribution", "value", "selected",
    "transfers_balance", "transfers_in", "transfers_out",
)


class SeasonHistoryError(RuntimeError):
    """Raised when official data cannot produce a complete season history."""


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return session


def _get_json(session: requests.Session, path: str, attempts: int = 5):
    delay = 1.0
    for attempt in range(attempts):
        try:
            response = session.get(f"{API}/{path}", timeout=30)
            if response.status_code == 200:
                return response.json()
            if response.status_code not in {429, 500, 502, 503, 504}:
                raise SeasonHistoryError(f"{path}: HTTP {response.status_code}")
        except requests.RequestException as exc:
            if attempt == attempts - 1:
                raise SeasonHistoryError(f"{path}: {exc}") from exc
        time.sleep(delay)
        delay *= 2
    raise SeasonHistoryError(f"{path}: no successful response after {attempts} attempts")


def completed_events(bootstrap: dict) -> list[int]:
    """Gameweeks whose scores are final: finished and data-checked, in order."""
    done = []
    for event in sorted(bootstrap["events"], key=lambda item: item["id"]):
        if not (event.get("finished") and event.get("data_checked")):
            break
        done.append(int(event["id"]))
    return done


def season_label(bootstrap: dict) -> str:
    first = next(event for event in bootstrap["events"] if event["id"] == 1)
    return season_for_date(datetime.fromisoformat(first["deadline_time"].replace("Z", "+00:00")))


def history_rows(bootstrap: dict, summaries: dict[int, dict], events: list[int]) -> pd.DataFrame:
    teams = {int(team["id"]): team["name"] for team in bootstrap["teams"]}
    rows = []
    for player in bootstrap["elements"]:
        summary = summaries.get(int(player["id"]))
        if summary is None:
            raise SeasonHistoryError(f"Missing element summary for player {player['id']}")
        for fixture in summary.get("history", []):
            if int(fixture["round"]) not in events:
                continue
            row = {column: fixture.get(column) for column in HISTORY_COLUMNS}
            row.update(
                name=player.get("web_name") or player.get("second_name") or f"Player {player['id']}",
                position=POSITIONS.get(int(player["element_type"]), "UNK"),
                team=teams.get(int(player["team"]), "Unknown"),
                GW=int(fixture["round"]),
            )
            rows.append(row)
    columns = ["name", "position", "team", *HISTORY_COLUMNS, "GW"]
    frame = pd.DataFrame(rows, columns=columns)
    return frame.sort_values(["GW", "fixture", "element"], kind="mergesort").reset_index(drop=True)


def fetch_season(output_root: Path = PROJECT_ROOT / "historical_data", workers: int = 6) -> dict:
    session = _session()
    bootstrap = _get_json(session, "bootstrap-static/")
    fixtures = _get_json(session, "fixtures/")
    events = completed_events(bootstrap)
    if not events:
        raise SeasonHistoryError("No completed Gameweek is available yet")
    ids = [int(player["id"]) for player in bootstrap["elements"]]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        summaries = dict(zip(ids, pool.map(lambda pid: _get_json(session, f"element-summary/{pid}/"), ids)))
    season = season_label(bootstrap)
    directory = output_root / season
    directory.mkdir(parents=True, exist_ok=True)
    merged = history_rows(bootstrap, summaries, events)
    missing_events = sorted(set(events) - set(merged["GW"]))
    if missing_events:
        raise SeasonHistoryError(f"Completed Gameweeks without fixtures in history: {missing_events}")
    merged.to_csv(directory / "merged_gw.csv", index=False, lineterminator="\n")
    pd.DataFrame(fixtures).to_csv(directory / "fixtures.csv", index=False, lineterminator="\n")
    pd.DataFrame(bootstrap["teams"]).to_csv(directory / "teams.csv", index=False, lineterminator="\n")
    return {"season": season, "completed_events": events, "rows": len(merged), "directory": str(directory)}


def main() -> None:
    info = fetch_season()
    print(f"{info['season']}: {info['rows']} fixture rows for GW{info['completed_events'][0]}"
          f"-GW{info['completed_events'][-1]} -> {info['directory']}")


if __name__ == "__main__":
    main()
