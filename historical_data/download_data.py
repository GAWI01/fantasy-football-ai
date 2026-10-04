import sys

import requests
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data"

SEASONS = [
    "2020-21",
    "2021-22",
    "2022-23",
    "2023-24",
    "2024-25",
    "2025-26",
]

OUTPUT_DIR = Path("historical_data")


def download_file(url, destination):
    response = requests.get(url, timeout=120)

    if response.status_code != 200:
        print(f"FEIL {response.status_code}: {url}")
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(response.content)

    print(f"✓ {destination}")
    return True


def main():

    print("=" * 65)
    print("FPL AI — HISTORICAL DATA DOWNLOADER V2")
    print("=" * 65)

    seasons = sys.argv[1:] or SEASONS
    for season in seasons:

        print()
        print(f"--- Sesong {season} ---")

        season_dir = OUTPUT_DIR / season

        # Spillerdata
        players_url = (
            f"{BASE_URL}/{season}/players_raw.csv"
        )

        # Alle gameweeks samlet i én fil
        merged_gw_url = (
            f"{BASE_URL}/{season}/gws/merged_gw.csv"
        )

        # Fixtures
        fixtures_url = (
            f"{BASE_URL}/{season}/fixtures.csv"
        )

        # Lagdata
        teams_url = (
            f"{BASE_URL}/{season}/teams.csv"
        )

        download_file(
            players_url,
            season_dir / "players_raw.csv"
        )

        download_file(
            merged_gw_url,
            season_dir / "merged_gw.csv"
        )

        download_file(
            fixtures_url,
            season_dir / "fixtures.csv"
        )

        download_file(
            teams_url,
            season_dir / "teams.csv"
        )

    print()
    print("=" * 65)
    print("NEDLASTING FERDIG")
    print("=" * 65)


if __name__ == "__main__":
    main()