"""The one forecasting path shared by live predictions and model validation.

Live predictions append the target Gameweek's fixtures to the season's
completed history and run `build_feature_frame()` over the whole season, the
same call that produced every training and validation row. Validation replays
this exact function for each held-out Gameweek and checks that it reproduces
the historical feature rows (production parity).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from feature_contract import feature_matrix  # noqa: E402
from historical_data.build_features import build_feature_frame  # noqa: E402

POSITIONS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
ELEMENT_TYPES = {name: element_type for element_type, name in POSITIONS.items()}
BLANK_FIXTURE = 0


def fixture_sides(fixtures: pd.DataFrame, gw: int) -> pd.DataFrame:
    """Both clubs' view of every fixture scheduled in `gw`."""
    events = pd.to_numeric(fixtures["event"], errors="coerce")
    scheduled = fixtures[events == gw]
    sides = []
    for fixture in scheduled.itertuples(index=False):
        sides.append((int(fixture.team_h), int(fixture.id), True, int(fixture.team_a)))
        sides.append((int(fixture.team_a), int(fixture.id), False, int(fixture.team_h)))
    return pd.DataFrame(sides, columns=["team_id", "fixture", "was_home", "opponent_team"])


def target_rows(players: pd.DataFrame, fixtures: pd.DataFrame, gw: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Unplayed rows for `gw`: one per player and fixture, plus blank placeholders.

    `players` uses the official element layout (id, element_type, team,
    now_cost). A player whose club has no fixture gets one placeholder row so
    their history summary is still available; placeholders are never modelled.
    """
    roster = pd.DataFrame({
        "element": pd.to_numeric(players["id"], errors="raise").astype(int),
        "position": pd.to_numeric(players["element_type"], errors="raise").map(POSITIONS),
        "team_id": pd.to_numeric(players["team"], errors="raise").astype(int),
        "value": pd.to_numeric(players["now_cost"], errors="raise"),
    })
    if roster["element"].duplicated().any():
        raise ValueError("Player IDs must be unique")
    playing = roster.merge(fixture_sides(fixtures, gw), on="team_id", how="inner")
    blank = roster[~roster["element"].isin(playing["element"])].assign(
        fixture=BLANK_FIXTURE, was_home=False, opponent_team=0,
    )
    columns = ["element", "position", "team_id", "value", "fixture", "was_home", "opponent_team"]
    playing = playing[columns].assign(GW=gw, round=gw)
    blank = blank[columns].assign(GW=gw, round=gw)
    return playing.reset_index(drop=True), blank.reset_index(drop=True)


def live_feature_rows(history: pd.DataFrame, players: pd.DataFrame, fixtures: pd.DataFrame,
                      gw: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Feature rows for every `gw` fixture (modelled) and every blank player."""
    past = history[pd.to_numeric(history["GW"], errors="raise") < gw]
    playing, blank = target_rows(players, fixtures, gw)
    frame = build_feature_frame(
        pd.concat([past.assign(row_kind="history"), playing.assign(row_kind="fixture"),
                   blank.assign(row_kind="blank")], ignore_index=True),
        fixtures,
    )
    current = frame[frame["GW"] == gw]
    return (current[current["row_kind"] == "fixture"].reset_index(drop=True),
            current[current["row_kind"] == "blank"].reset_index(drop=True))


def predict_fixture_points(model, rows: pd.DataFrame) -> np.ndarray:
    """Expected points for each fixture row; negative model output is floored at zero."""
    if rows.empty:
        return np.zeros(0)
    predictions = np.asarray(model.predict(feature_matrix(rows)), dtype=float)
    if not np.isfinite(predictions).all():
        raise ValueError("Model returned a nonfinite prediction")
    return np.clip(predictions, 0.0, None)


def players_snapshot_from_history(rows: pd.DataFrame, fixtures: pd.DataFrame) -> pd.DataFrame:
    """Rebuild the official element layout for one played Gameweek (for parity checks)."""
    sides = fixtures[["id", "team_h", "team_a"]].rename(columns={"id": "fixture"})
    joined = rows.merge(sides, on="fixture", how="left", validate="many_to_one")
    home = joined["was_home"].map(lambda value: value if isinstance(value, bool)
                                  else str(value).strip().lower() in {"true", "1", "1.0"})
    joined["team"] = np.where(home, joined["team_h"], joined["team_a"])
    snapshot = joined.groupby("element", as_index=False).first()
    return pd.DataFrame({
        "id": snapshot["element"].astype(int),
        "element_type": snapshot["position"].astype(str).str.upper().replace({"GKP": "GK"}).map(ELEMENT_TYPES),
        "team": snapshot["team"].astype(int),
        "now_cost": snapshot["value"],
    })
