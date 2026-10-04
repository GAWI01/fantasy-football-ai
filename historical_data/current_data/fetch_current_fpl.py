import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.fpl_gateway import USER_AGENT  # noqa: E402


BASE_DIR = Path(__file__).resolve().parent

API_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"


def main():

    print("=" * 65)
    print("FPL AI — CURRENT 2026/27 DATA")
    print("=" * 65)

    print()
    print("Henter FPL-data...")

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    response = requests.get(
        API_URL,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    print("✓ FPL API svarte")

    # ---------------------------------------------------------
    # PLAYERS
    # ---------------------------------------------------------

    players = pd.DataFrame(data["elements"])

    print()
    print(f"Spillere: {len(players)}")

    # ---------------------------------------------------------
    # TEAMS
    # ---------------------------------------------------------

    teams = pd.DataFrame(data["teams"])

    team_map = dict(
        zip(
            teams["id"],
            teams["name"]
        )
    )

    players["team_name"] = players["team"].map(team_map)

    # ---------------------------------------------------------
    # POSITIONS
    # ---------------------------------------------------------

    position_map = {
        1: "GKP",
        2: "DEF",
        3: "MID",
        4: "FWD"
    }

    players["position_name"] = (
        players["element_type"]
        .map(position_map)
    )

    # ---------------------------------------------------------
    # PRICE
    # ---------------------------------------------------------

    players["price"] = (
        players["now_cost"] / 10
    )

    # ---------------------------------------------------------
    # SAVE RAW DATA
    # ---------------------------------------------------------

    raw_file = (
        BASE_DIR
        / "players_raw.csv"
    )

    players.to_csv(
        raw_file,
        index=False
    )

    # ---------------------------------------------------------
    # SAVE CLEAN PLAYER DATA
    # ---------------------------------------------------------

    columns = [
        "id",
        "first_name",
        "second_name",
        "web_name",
        "position_name",
        "team_name",
        "price",
        "status",
        "news",
        "chance_of_playing_next_round",
        "selected_by_percent",
        "form",
        "points_per_game",
        "total_points",
        "minutes",
        "goals_scored",
        "assists",
        "clean_sheets",
        "expected_goals",
        "expected_assists",
        "influence",
        "creativity",
        "threat",
        "ict_index",
        "bps",
        "bonus",
        "transfers_in",
        "transfers_out",
        "transfers_in_event",
        "transfers_out_event"
    ]

    # Bare behold bare kolonner som faktisk finnes
    columns = [
        c for c in columns
        if c in players.columns
    ]

    clean = players[columns].copy()

    clean = clean.rename(
        columns={
            "id": "player_id",
            "first_name": "first_name",
            "second_name": "second_name",
            "web_name": "name",
            "position_name": "position",
            "team_name": "team"
        }
    )

    clean_file = (
        BASE_DIR
        / "players_current.csv"
    )

    clean.to_csv(
        clean_file,
        index=False
    )

    # ---------------------------------------------------------
    # TEAMS
    # ---------------------------------------------------------

    teams_file = (
        BASE_DIR
        / "teams_current.csv"
    )

    teams.to_csv(
        teams_file,
        index=False
    )

    # ---------------------------------------------------------
    # GAMEWEEKS
    # ---------------------------------------------------------

    events = pd.DataFrame(
        data["events"]
    )

    events_file = (
        BASE_DIR
        / "gameweeks_current.csv"
    )

    events.to_csv(
        events_file,
        index=False
    )

    # ---------------------------------------------------------
    # FIXTURES
    # ---------------------------------------------------------

    fixtures_response = requests.get(
        "https://fantasy.premierleague.com/api/fixtures/",
        headers=headers,
        timeout=30
    )

    fixtures_response.raise_for_status()

    fixtures = pd.DataFrame(
        fixtures_response.json()
    )

    fixtures_file = (
        BASE_DIR
        / "fixtures_current.csv"
    )

    fixtures.to_csv(
        fixtures_file,
        index=False
    )

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------

    print()
    print("DATA LAGRET")
    print("-" * 65)

    print(f"✓ Spillere:    {clean_file}")
    print(f"✓ Lag:          {teams_file}")
    print(f"✓ Gameweeks:    {events_file}")
    print(f"✓ Fixtures:     {fixtures_file}")

    print()
    print("TOPP 10 ETTER PRIS")
    print("-" * 65)

    top = clean.sort_values(
        "price",
        ascending=False
    ).head(10)

    for _, player in top.iterrows():

        print(
            f"{player['name']:<25}"
            f"{player['position']:<5}"
            f"{player['team']:<20}"
            f"£{player['price']:.1f}m"
        )

    print()
    print("DATA-SJEKK")
    print("-" * 65)

    print(
        f"Antall spillere: {len(clean)}"
    )

    print(
        f"Antall lag:      {len(teams)}"
    )

    print(
        f"Antall fixtures: {len(fixtures)}"
    )

    print()
    print(
        "Hentet:",
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    print()
    print("=" * 65)
    print("CURRENT DATA FERDIG")
    print("=" * 65)


if __name__ == "__main__":
    main()