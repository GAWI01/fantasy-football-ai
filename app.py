import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from app_team import merge_team_with_predictions, normalize_team_id, TeamIdError
from backend.data_loader import (
    DataLoaderError,
    load_players,
    validate_current_data,
)
from optimizer.squad_optimizer import optimize_squad
from backend.team_service import (
    TeamServiceError,
    fetch_public_team,
)
from transfer_analysis import (
    analyze_transfer_in,
    analyze_transfer_optimizer,
    analyze_transfer_recommendation,
    analyze_transfer_scenario,
    analyze_transfer_out,
    TransferAnalysisError,
)


# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
PREDICTIONS_DIR = BASE_DIR / "historical_data" / "current_data"

PREDICTION_FILES = [
    "gw3_predictions.csv",
    "gw2_predictions_v5.csv",
    "gw2_predictions_v4.csv",
    "gw2_predictions.csv",
]


st.set_page_config(
    page_title="FPL-AI",
    page_icon="âš½",
    layout="wide",
)


# -------------------------------------------------------------------
# DATA HELPERS
# -------------------------------------------------------------------

def get_prediction_file():
    """Return the served forecast named by manifest.json, else a legacy CSV."""

    try:
        manifest = json.loads((PREDICTIONS_DIR / "manifest.json").read_text(encoding="utf-8"))
        served = PREDICTIONS_DIR / manifest["prediction_file"]
        if served.exists():
            return served
    except (OSError, ValueError, KeyError, TypeError):
        pass

    for filename in PREDICTION_FILES:
        path = PREDICTIONS_DIR / filename

        if path.exists():
            return path

    raise FileNotFoundError(
        "Fant ingen prediction-fil i "
        f"{PREDICTIONS_DIR}"
    )


def prepare_predictions(players):
    """Prepare prediction data for the dashboard."""

    required_columns = {
        "name",
        "position",
        "team",
        "price",
        "predicted_points",
    }

    missing = required_columns - set(players.columns)

    if missing:
        missing_columns = ", ".join(sorted(missing))

        raise ValueError(
            f"Prediction data mangler kolonner: {missing_columns}"
        )

    result = players.copy()

    result["price"] = pd.to_numeric(
        result["price"],
        errors="coerce",
    )

    result["predicted_points"] = pd.to_numeric(
        result["predicted_points"],
        errors="coerce",
    )

    result = result.dropna(
        subset=[
            "price",
            "predicted_points",
        ]
    )

    result = result.sort_values(
        "predicted_points",
        ascending=False,
    ).reset_index(drop=True)

    return result


def get_fixture_label(row):
    """Return a readable fixture label."""

    team = str(row.get("team", "Unknown"))
    opponent = str(row.get("opponent", "Unknown"))

    home = row.get(
        "home",
        row.get("was_home", None),
    )

    if isinstance(home, str):
        home = home.lower() in {
            "true",
            "1",
            "yes",
        }

    if home is True:
        return f"{team} vs {opponent}"

    if home is False:
        return f"{opponent} vs {team}"

    return f"{team} vs {opponent}"


def load_prediction_data():
    """Load and prepare the current prediction dataset."""

    path = get_prediction_file()

    predictions = pd.read_csv(path)
    predictions = prepare_predictions(predictions)

    return predictions, path


# -------------------------------------------------------------------
# POSITION NORMALIZATION
# -------------------------------------------------------------------

def normalize_positions(players):
    """
    Normalize FPL position names.

    The optimizer uses:
        GK / DEF / MID / FWD

    FPL prediction data can sometimes use:
        GKP / DEF / MID / FWD
    """

    result = players.copy()

    position_map = {
        "GKP": "GK",
        "GK": "GK",
        "DEF": "DEF",
        "MID": "MID",
        "FWD": "FWD",
    }

    result["position"] = (
        result["position"]
        .astype(str)
        .str.upper()
        .map(position_map)
    )

    result = result.dropna(
        subset=["position"]
    )

    return result


# -------------------------------------------------------------------
# MY TEAM
# -------------------------------------------------------------------

def prepare_my_team(team, predictions):
    """Prepare the user's FPL team for dashboard display."""

    result = merge_team_with_predictions(
        team,
        predictions,
    )

    position_order = {
        "GK": 0,
        "GKP": 0,
        "DEF": 1,
        "MID": 2,
        "FWD": 3,
    }

    result["_position_order"] = (
        result["position"]
        .astype(str)
        .str.upper()
        .map(position_order)
        .fillna(99)
    )

    result = (
        result
        .sort_values("_position_order")
        .drop(columns=["_position_order"])
        .reset_index(drop=True)
    )

    return result


def get_team_summary(team):
    """Return the key summary information for a user's team."""

    return {
        "team_id": team.get("team_id"),
        "name": team.get("name", "Unknown Team"),
        "bank": team.get("bank"),
        "event": team.get("event"),
        "transfers": team.get("transfers"),
        "players": len(team.get("picks", [])),
    }


# -------------------------------------------------------------------
# SQUAD OPTIMIZATION
# -------------------------------------------------------------------

def build_optimal_squad(predictions):
    """Build the best valid squad from predictions."""

    optimizer_data = normalize_positions(
        predictions
    )

    squad = optimize_squad(
        optimizer_data,
        budget=100.0,
    )

    return squad



def build_transfer_center(
    team: dict[str, Any],
    predictions: pd.DataFrame,
    player_out_id: int | None = None,
    budget: float | None = None,
) -> dict[str, Any]:
    """Build the transfer-center data from the existing analysis layer."""

    if not isinstance(team, dict):
        raise TransferAnalysisError("team must be a dictionary")

    if not isinstance(predictions, pd.DataFrame):
        raise TransferAnalysisError("predictions must be a pandas DataFrame")

    if player_out_id is None:
        raise TransferAnalysisError("player_out_id is required")

    recommendation = analyze_transfer_recommendation(
        team,
        predictions,
        player_out_id=player_out_id,
        budget=budget,
    )

    transfer_in = analyze_transfer_in(
        team,
        predictions,
        player_out_id=player_out_id,
        budget=budget,
    )

    transfer_out = analyze_transfer_out(team, predictions)

    return {
        "player_out_id": player_out_id,
        "recommended_player_id": recommendation["recommended_player_id"],
        "recommended_player": recommendation["recommended_player"],
        "predicted_gain": recommendation["predicted_gain"],
        "recommended_price": recommendation["recommended_price"],
        "recommended_predicted_points": recommendation[
            "recommended_predicted_points"
        ],
        "alternatives": recommendation["alternatives"],
        "recommendation": recommendation,
        "transfer_in": transfer_in,
        "transfer_out": transfer_out,
    }


# -------------------------------------------------------------------
# DISPLAY HELPERS
# -------------------------------------------------------------------

def format_player_table(players):
    """Create a clean player table for Streamlit."""

    display_columns = [
        "name",
        "position",
        "team",
        "price",
        "opponent",
        "predicted_points",
        "xP",
        "ml_prediction",
        "value",
        "form",
        "availability",
    ]

    available_columns = [
        column
        for column in display_columns
        if column in players.columns
    ]

    table = players[
        available_columns
    ].copy()

    rename_map = {
        "name": "Player",
        "position": "Pos",
        "team": "Team",
        "price": "Price",
        "opponent": "Opponent",
        "predicted_points": "AI Points",
        "xP": "xP",
        "ml_prediction": "ML",
        "value": "Value",
        "form": "Form",
        "availability": "Availability",
    }

    table = table.rename(
        columns=rename_map
    )

    return table


def display_squad(squad):
    """Display the optimized squad."""

    positions = [
        "GK",
        "DEF",
        "MID",
        "FWD",
    ]

    for position in positions:

        position_players = squad[
            squad["position"] == position
        ]

        if position_players.empty:
            continue

        st.markdown(
            f"**{position}**"
        )

        columns = st.columns(
            len(position_players)
        )

        for column, (_, player) in zip(
            columns,
            position_players.iterrows(),
        ):

            with column:

                st.metric(
                    label=player["name"],
                    value=f'{player["predicted_points"]:.2f}',
                    delta=f'Â£{player["price"]:.1f}m',
                )

                st.caption(
                    str(player["team"])
                )


def display_my_team(team_df):
    """Display the imported FPL team grouped by position."""

    if team_df.empty:
        st.warning("Fant ingen spillere pÃ¥ laget.")
        return

    positions = [
        ("GK", "ðŸ§¤ Goalkeepers"),
        ("DEF", "ðŸ›¡ï¸ Defenders"),
        ("MID", "ðŸŽ¯ Midfielders"),
        ("FWD", "âš¡ Forwards"),
    ]

    for position, title in positions:

        position_players = team_df[
            team_df["position"] == position
        ]

        if position_players.empty:
            continue

        st.markdown(f"#### {title}")

        columns = st.columns(
            min(len(position_players), 5)
        )

        for index, (_, player) in enumerate(
            position_players.iterrows()
        ):

            column = columns[
                index % len(columns)
            ]

            with column:

                name = str(
                    player.get(
                        "name",
                        "Unknown",
                    )
                )

                multiplier = player.get(
                    "multiplier",
                    1,
                )

                try:
                    multiplier = int(
                        multiplier
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    multiplier = 1

                predicted = player.get(
                    "predicted_points"
                )

                price = player.get(
                    "price"
                )

                if pd.notna(predicted):
                    points_text = (
                        f"{float(predicted):.2f} pts"
                    )
                else:
                    points_text = "No prediction"

                if pd.notna(price):
                    price_text = (
                        f"Â£{float(price):.1f}m"
                    )
                else:
                    price_text = "â€”"

                if multiplier == 2:
                    name = f"â­ {name}"

                st.metric(
                    label=name,
                    value=points_text,
                    delta=price_text,
                )

                team_name = player.get(
                    "team"
                )

                if pd.notna(team_name):
                    st.caption(
                        str(team_name)
                    )

                if multiplier == 2:
                    st.caption(
                        "Captain"
                    )

def build_team_display(team, predictions):
    """Build a structured display model for the user's FPL team."""

    result = prepare_my_team(team, predictions)

    if result.empty:
        return {
            "starting_xi": result.copy(),
            "bench": result.copy(),
            "captain": None,
            "captain_id": None,
            "vice_captain": None,
            "vice_captain_id": None,
            "all_players": result.copy(),
        }

    working = result.copy()

    if "position_team" in working.columns:
        working["_slot"] = pd.to_numeric(
            working["position_team"],
            errors="coerce",
        )
    else:
        working["_slot"] = pd.Series(
            range(1, len(working) + 1),
            index=working.index,
            dtype="float64",
        )

    working = working.sort_values(
        "_slot",
        na_position="last",
    ).reset_index(drop=True)

    starting_xi = working[working["_slot"] <= 11].copy()
    bench = working[working["_slot"] > 11].copy()

    if len(starting_xi) == 0 and len(working) > 0:
        starting_xi = working.iloc[:11].copy()
        bench = working.iloc[11:].copy()

    captain = None
    captain_id = None

    if "multiplier" in working.columns:
        multipliers = pd.to_numeric(
            working["multiplier"],
            errors="coerce",
        )

        captain_rows = working[multipliers == 2]

        if not captain_rows.empty:
            captain = captain_rows.iloc[0].to_dict()
            captain_id = captain_rows.iloc[0]["player_id"]

    vice_captain = None
    vice_captain_id = None

    if "multiplier" in working.columns:
        vice_rows = working[
            (pd.to_numeric(working["multiplier"], errors="coerce") == 1)
            & (working["_slot"] <= 11)
        ]

        if not vice_rows.empty:
            vice_captain = vice_rows.iloc[0].to_dict()
            vice_captain_id = vice_rows.iloc[0]["player_id"]

    starting_xi = starting_xi.drop(
        columns=["_slot"],
        errors="ignore",
    ).reset_index(drop=True)

    bench = bench.drop(
        columns=["_slot"],
        errors="ignore",
    ).reset_index(drop=True)

    all_players = working.drop(
        columns=["_slot"],
        errors="ignore",
    ).reset_index(drop=True)

    return {
        "starting_xi": starting_xi,
        "bench": bench,
        "captain": captain,
        "captain_id": captain_id,
        "vice_captain": vice_captain,
        "vice_captain_id": vice_captain_id,
        "all_players": all_players,
    }

def analyze_my_team(team, predictions):
    """Analyze the user's team using player predictions."""

    result = prepare_my_team(team, predictions)

    if result.empty:
        return {
            "total_predicted_points": 0.0,
            "best_player_id": None,
            "best_player_name": None,
            "captain_id": None,
            "strongest_position": None,
            "weakest_position": None,
            "team_rating": 0.0,
        }

    points = pd.to_numeric(
        result["predicted_points"],
        errors="coerce",
    ).fillna(0.0)

    total_predicted_points = float(points.sum())

    best_index = points.idxmax()
    best_player = result.loc[best_index]

    captain_id = None

    if "multiplier" in result.columns:
        multipliers = pd.to_numeric(
            result["multiplier"],
            errors="coerce",
        )

        captain_rows = result[multipliers == 2]

        if not captain_rows.empty:
            captain_id = captain_rows.iloc[0]["player_id"]

    strongest_position = None
    weakest_position = None

    if "position" in result.columns:
        position_points = (
            result.assign(
                _points=points,
            )
            .groupby("position")["_points"]
            .sum()
        )

        if not position_points.empty:
            strongest_position = position_points.idxmax()

            # For weakness analysis, prefer positions with multiple players.
            # This avoids treating a single goalkeeper as the weakest area
            # simply because the squad has only one player there.
            multi_player_positions = (
                result.groupby("position").size()
            )
            eligible_positions = position_points[
                position_points.index.map(
                    lambda position: multi_player_positions.get(position, 0) >= 2
                )
            ]

            if not eligible_positions.empty:
                weakest_position = eligible_positions.idxmin()
            else:
                weakest_position = position_points.idxmin()

    # Simple 0-10 team rating based on predicted points.
    # This is intentionally kept simple for now; later we can
    # replace it with a more sophisticated FPL-specific rating.
    team_rating = min(
        10.0,
        max(
            0.0,
            total_predicted_points / 10.0,
        ),
    )

    return {
        "total_predicted_points": total_predicted_points,
        "best_player_id": best_player["player_id"],
        "best_player_name": best_player["name"],
        "captain_id": captain_id,
        "strongest_position": strongest_position,
        "weakest_position": weakest_position,
        "team_rating": team_rating,
    }


# -------------------------------------------------------------------
# DATA LOAD
# -------------------------------------------------------------------

try:
    validate_current_data()
    canonical_players = load_players()
except DataLoaderError as exc:
    st.error(f"Data error: {exc}")
    st.stop()

try:
    predictions, prediction_path = load_prediction_data()
except (FileNotFoundError, ValueError, pd.errors.ParserError) as exc:
    st.error(f"Prediction data error: {exc}")
    st.stop()

try:
    optimal_squad = build_optimal_squad(predictions)
    optimizer_error = None
except Exception as exc:
    optimal_squad = None
    optimizer_error = str(exc)


# -------------------------------------------------------------------
# DESIGN SYSTEM
# -------------------------------------------------------------------

st.markdown(
    """
    <style>
    :root {
        --bg: #070b12;
        --panel: #0d131d;
        --panel-2: #111927;
        --border: #202b3b;
        --text: #f4f7fb;
        --muted: #8f9bad;
        --purple: #8b5cf6;
        --purple-2: #6d28d9;
        --green: #70e000;
        --green-soft: rgba(112, 224, 0, .12);
        --red: #ff4d5e;
        --yellow: #f5b83d;
    }

    .stApp {
        background:
            radial-gradient(circle at 70% -10%, rgba(109, 40, 217, .13), transparent 32%),
            radial-gradient(circle at 15% 10%, rgba(112, 224, 0, .045), transparent 28%),
            var(--bg);
        color: var(--text);
    }

    [data-testid="stHeader"] {
        background: rgba(7, 11, 18, .88);
    }

    [data-testid="stSidebar"] {
        background: #080d15;
        border-right: 1px solid var(--border);
    }

    [data-testid="stSidebar"] * {
        color: #d9dfeb;
    }

    .block-container {
        max-width: 1500px;
        padding-top: 1.4rem;
        padding-bottom: 3rem;
    }

    h1, h2, h3, h4 {
        color: var(--text) !important;
        letter-spacing: -.025em;
    }

    .topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1.15rem;
    }

    .brand {
        font-size: 1.55rem;
        font-weight: 800;
        letter-spacing: -.04em;
    }

    .brand-mark {
        display: inline-flex;
        width: 34px;
        height: 34px;
        border-radius: 11px;
        align-items: center;
        justify-content: center;
        margin-right: 9px;
        background: linear-gradient(135deg, var(--purple), #35167a);
        box-shadow: 0 0 24px rgba(139, 92, 246, .25);
    }

    .live {
        font-size: .82rem;
        color: var(--muted);
    }

    .live-dot {
        color: var(--green);
        margin-right: 5px;
    }

    .section-label {
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: .11em;
        font-size: .7rem;
        font-weight: 700;
        margin-bottom: .45rem;
    }

    .card {
        background: linear-gradient(145deg, rgba(17, 25, 39, .96), rgba(10, 15, 24, .96));
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 1rem 1.05rem;
        box-shadow: 0 12px 35px rgba(0,0,0,.16);
    }

    .metric-card {
        min-height: 108px;
    }

    .metric-title {
        color: var(--muted);
        font-size: .76rem;
        margin-bottom: .55rem;
    }

    .metric-value {
        color: var(--text);
        font-size: 1.72rem;
        line-height: 1;
        font-weight: 800;
        letter-spacing: -.035em;
    }

    .metric-value.green { color: var(--green); }
    .metric-sub {
        color: var(--muted);
        font-size: .72rem;
        margin-top: .55rem;
    }

    .positive { color: var(--green) !important; }
    .negative { color: var(--red) !important; }
    .warning { color: var(--yellow) !important; }

    .pitch {
        position: relative;
        min-height: 530px;
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid #314e37;
        background:
            linear-gradient(rgba(8, 60, 24, .22), rgba(4, 45, 18, .18)),
            repeating-linear-gradient(
                90deg,
                #0b4b22 0,
                #0b4b22 8.33%,
                #0c5426 8.33%,
                #0c5426 16.66%
            );
    }

    .pitch-lines {
        position: absolute;
        inset: 7% 8%;
        border: 1px solid rgba(255,255,255,.22);
        border-radius: 4px;
        pointer-events: none;
    }

    .pitch-lines:before {
        content: "";
        position: absolute;
        left: 0;
        right: 0;
        top: 50%;
        border-top: 1px solid rgba(255,255,255,.2);
    }

    .player-row {
        position: absolute;
        left: 4%;
        right: 4%;
        display: flex;
        justify-content: center;
        gap: 5%;
    }

    .player-row.gk { top: 7%; }
    .player-row.def { top: 26%; }
    .player-row.mid { top: 47%; }
    .player-row.fwd { top: 68%; }

    .pitch-player {
        min-width: 88px;
        text-align: center;
    }

    .player-head {
        width: 48px;
        height: 48px;
        margin: 0 auto 5px;
        border-radius: 50%;
        background: linear-gradient(145deg, #172235, #070b12);
        border: 2px solid rgba(255,255,255,.45);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: .7rem;
        font-weight: 800;
        overflow: hidden;
    }

    .player-head img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }

    .player-name {
        display: inline-block;
        max-width: 100px;
        padding: 3px 7px;
        border-radius: 7px;
        background: rgba(5, 9, 15, .88);
        color: #fff;
        font-size: .68rem;
        font-weight: 700;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .player-points {
        color: #b9c2d1;
        font-size: .62rem;
        margin-top: 2px;
    }

    .captain-badge {
        display: inline-block;
        margin-left: 3px;
        color: var(--green);
        font-size: .58rem;
        font-weight: 800;
    }

    .bench {
        margin-top: .7rem;
        padding: .7rem .85rem;
        border-radius: 11px;
        background: rgba(5, 9, 15, .72);
        border: 1px solid rgba(255,255,255,.08);
    }

    .bench-title {
        color: var(--muted);
        font-size: .66rem;
        text-transform: uppercase;
        letter-spacing: .08em;
        margin-bottom: .5rem;
    }

    .bench-grid {
        display: flex;
        justify-content: space-around;
        gap: .4rem;
    }

    .bench-player {
        text-align: center;
        color: #cbd4e2;
        font-size: .63rem;
    }

    .ai-card {
        min-height: 355px;
    }

    .transfer-player {
        text-align: center;
        padding: .6rem;
        border-radius: 11px;
        background: rgba(255,255,255,.025);
        border: 1px solid var(--border);
    }

    .transfer-tag {
        font-size: .62rem;
        text-transform: uppercase;
        letter-spacing: .1em;
        color: var(--muted);
        margin-top: .3rem;
    }

    .transfer-name {
        color: var(--text);
        font-size: .88rem;
        font-weight: 750;
        margin-top: .25rem;
    }

    .arrow {
        font-size: 1.7rem;
        color: #bac3d0;
        text-align: center;
        padding-top: 2rem;
    }

    .gain {
        font-size: 2rem;
        line-height: 1;
        font-weight: 850;
        color: var(--green);
    }

    .confidence {
        height: 7px;
        border-radius: 99px;
        background: #202a38;
        overflow: hidden;
        margin-top: .5rem;
    }

    .confidence > div {
        height: 100%;
        width: 87%;
        background: linear-gradient(90deg, var(--purple), var(--green));
        border-radius: 99px;
    }

    .fixture-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: .65rem .1rem;
        border-bottom: 1px solid rgba(255,255,255,.06);
        font-size: .75rem;
    }

    .fixture-row:last-child { border-bottom: 0; }

    .fixture-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        margin-left: 7px;
        background: var(--green);
    }

    .fixture-dot.medium { background: var(--yellow); }
    .fixture-dot.hard { background: var(--red); }

    .form-card {
        text-align: center;
        padding: .65rem .25rem;
    }

    .form-name {
        font-size: .7rem;
        font-weight: 700;
        margin-top: .35rem;
    }

    .form-points {
        font-size: .72rem;
        color: var(--muted);
    }

    .avatar {
        width: 55px;
        height: 55px;
        border-radius: 50%;
        margin: 0 auto;
        background: linear-gradient(145deg, #263248, #090e17);
        border: 1px solid #354258;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        font-weight: 800;
        color: #dce5f2;
    }

    .avatar img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }

    .insight {
        border-left: 3px solid var(--purple);
        padding: .15rem 0 .15rem .85rem;
        color: #c7cfdb;
        font-size: .82rem;
        line-height: 1.55;
    }

    .small-muted {
        color: var(--muted);
        font-size: .72rem;
    }

    .sidebar-version {
        color: #5f6b7d;
        font-size: .68rem;
        margin-top: 2rem;
    }

    /* Make Streamlit controls blend into the dashboard. */
    div[data-testid="stMetric"] {
        background: transparent;
    }

    div[data-testid="stButton"] > button {
        border-radius: 9px;
        border: 1px solid #3b2a66;
        background: linear-gradient(135deg, #6d28d9, #4c1d95);
        color: white;
        font-weight: 700;
    }

    div[data-testid="stButton"] > button:hover {
        border-color: #8b5cf6;
        color: white;
    }

    [data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 12px;
        overflow: hidden;
    }

    @media (max-width: 900px) {
        .pitch { min-height: 470px; }
        .player-head { width: 40px; height: 40px; }
        .player-name { font-size: .6rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -------------------------------------------------------------------
# SIDEBAR
# -------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        """
        <div class="brand">
            <span class="brand-mark">AI</span> FPL-AI
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption("Fantasy Premier League Decision Engine")
    st.divider()

    page = st.radio(
        "Navigation",
        [
            "Overview",
            "My Team",
            "Transfer Center",
            "AI Recommendations",
            "Players",
            "Fixtures",
            "Chips",
            "Statistics",
            "Settings",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown(
        """
        <div class="small-muted">● AI Mode</div>
        <div style="color:#70e000;font-size:.8rem;font-weight:700;margin-top:3px;">
            Active
        </div>
        <div class="sidebar-version">FPL-AI v2 • Local development</div>
        """,
        unsafe_allow_html=True,
    )


# -------------------------------------------------------------------
# TOP BAR
# -------------------------------------------------------------------

st.markdown(
    """
    <div class="topbar">
        <div>
            <div class="section-label">Fantasy analytics</div>
            <div class="brand">Gameweek Intelligence</div>
        </div>
        <div class="live">
            <span class="live-dot">●</span> Live data
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

gw_col, load_col, status_col = st.columns([1.2, 1.5, 2.3])

with gw_col:
    st.selectbox("Gameweek", ["GW3"], label_visibility="collapsed")

with load_col:
    team_id_input = st.text_input(
        "Team ID",
        value=st.session_state.get("team_id_input", ""),
        placeholder="FPL Team ID",
        label_visibility="collapsed",
    )

with status_col:
    load_team = st.button(
        "↻  Load My Team",
        use_container_width=True,
        type="primary",
    )

if load_team:
    try:
        team_id = normalize_team_id(team_id_input)
        with st.spinner("Fetching your FPL team..."):
            loaded_team = fetch_public_team(team_id)
        st.session_state["team_id_input"] = str(team_id)
        st.session_state["my_team"] = loaded_team
        st.rerun()
    except TeamIdError as exc:
        st.error(str(exc))
    except TeamServiceError as exc:
        st.error(f"Could not fetch team: {exc}")


my_team = st.session_state.get("my_team")
my_team_players = pd.DataFrame()

if my_team is not None:
    try:
        my_team_players = prepare_my_team(my_team, predictions)
    except Exception as exc:
        st.warning(f"Could not prepare team display: {exc}")


# -------------------------------------------------------------------
# GLOBAL METRICS
# -------------------------------------------------------------------

optimal_points = (
    float(optimal_squad["predicted_points"].sum())
    if optimal_squad is not None
    else None
)

team_analysis = (
    analyze_my_team(my_team, predictions)
    if my_team is not None
    else {
        "total_predicted_points": 0.0,
        "best_player_id": None,
        "best_player_name": None,
        "captain_id": None,
        "strongest_position": None,
        "weakest_position": None,
        "team_rating": 0.0,
    }
)

projected_team_points = (
    team_analysis["total_predicted_points"]
    if my_team is not None
    else optimal_points or 0.0
)

team_rating = team_analysis["team_rating"] if my_team is not None else 0.0

bank_value = None
transfers_available = None
team_name = "No team loaded"

if my_team is not None:
    team_name = my_team.get("name", "My Team")
    raw_bank = my_team.get("bank")
    if raw_bank is not None:
        try:
            bank_value = float(raw_bank) / 10
        except (TypeError, ValueError):
            bank_value = None
    transfers_available = my_team.get("transfers")


metric_cols = st.columns(5)

metrics = [
    ("Projected Points", f"{projected_team_points:.1f}", "Current squad", True),
    ("Team Rating", f"{team_rating:.1f}", "AI score / 10", True),
    ("Team Value", "—" if my_team is None else "Loaded", team_name, False),
    ("Optimal xPoints", "—" if optimal_points is None else f"{optimal_points:.1f}", "AI optimized squad", False),
    ("Transfers", "—" if transfers_available is None else str(transfers_available), "Free transfers", False),
]

for column, (title, value, sub, green) in zip(metric_cols, metrics):
    with column:
        value_class = "green" if green else ""
        st.markdown(
            f"""
            <div class="card metric-card">
                <div class="metric-title">{title}</div>
                <div class="metric-value {value_class}">{value}</div>
                <div class="metric-sub">{sub}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


st.write("")


# -------------------------------------------------------------------
# MAIN DASHBOARD
# -------------------------------------------------------------------

if page in ("Overview", "My Team", "Transfer Center", "AI Recommendations"):

    main_col, transfer_col, fixtures_col = st.columns([1.65, 1.45, .9])

    # MY TEAM
    with main_col:
        st.markdown('<div class="section-label">Squad</div>', unsafe_allow_html=True)
        st.markdown(f"### {team_name}")

        if my_team is None:
            st.info("Load your FPL Team ID above to see your squad here.")
        elif my_team_players.empty:
            st.warning("No player prediction matches were found for this team.")
        else:
            team_display = build_team_display(my_team, predictions)
            xi = team_display["starting_xi"]
            bench = team_display["bench"]

            rows = {"GK": [], "DEF": [], "MID": [], "FWD": []}
            for _, player in xi.iterrows():
                pos = str(player.get("position", "")).upper()
                if pos == "GKP":
                    pos = "GK"
                if pos in rows:
                    rows[pos].append(player)

            def player_html(player):
                name = str(player.get("name", "Player"))
                pts = player.get("predicted_points")
                pid = player.get("player_id")
                multiplier = player.get("multiplier", 1)

                try:
                    pts_text = f"{float(pts):.1f} pts"
                except (TypeError, ValueError):
                    pts_text = "—"

                # Use an image only when the prediction dataset supplies one.
                image = ""
                for key in ("photo_url", "image_url", "photo", "image"):
                    candidate = player.get(key)
                    if candidate is not None and pd.notna(candidate):
                        url = str(candidate)
                        if url:
                            image = f'<img src="{url}" alt="">'
                            break

                initial = name[:2].upper()
                captain = (
                    '<span class="captain-badge">C</span>'
                    if str(multiplier) == "2"
                    else ""
                )

                return f"""
                    <div class="pitch-player" title="{name}">
                        <div class="player-head">{image or initial}</div>
                        <div class="player-name">{name}{captain}</div>
                        <div class="player-points">{pts_text}</div>
                    </div>
                """

            pitch_html = '<div class="pitch"><div class="pitch-lines"></div>'

            for pos, css_class in [
                ("GK", "gk"),
                ("DEF", "def"),
                ("MID", "mid"),
                ("FWD", "fwd"),
            ]:
                pitch_html += f'<div class="player-row {css_class}">'
                for player in rows[pos]:
                    pitch_html += player_html(player)
                pitch_html += "</div>"

            pitch_html += "</div>"
            st.markdown(pitch_html, unsafe_allow_html=True)

            if not bench.empty:
                bench_html = '<div class="bench"><div class="bench-title">Bench</div><div class="bench-grid">'
                for _, player in bench.iterrows():
                    name = str(player.get("name", "Player"))
                    pts = player.get("predicted_points")
                    try:
                        pts_text = f"{float(pts):.1f}"
                    except (TypeError, ValueError):
                        pts_text = "—"
                    bench_html += (
                        f'<div class="bench-player"><strong>{name}</strong><br>'
                        f'<span class="small-muted">{pts_text} pts</span></div>'
                    )
                bench_html += "</div></div>"
                st.markdown(bench_html, unsafe_allow_html=True)

    # AI TRANSFER
    with transfer_col:
        st.markdown('<div class="section-label">Decision engine</div>', unsafe_allow_html=True)
        st.markdown("### AI Recommendation")

        if my_team is None or my_team_players.empty:
            st.markdown(
                '<div class="card ai-card"><div class="small-muted">'
                'Load your team to unlock personalized transfer recommendations.'
                '</div></div>',
                unsafe_allow_html=True,
            )
        else:
            out_ids = my_team_players["player_id"].tolist()
            selected_out = st.selectbox(
                "Player to replace",
                out_ids,
                format_func=lambda pid: str(
                    my_team_players.loc[
                        my_team_players["player_id"] == pid,
                        "name",
                    ].iloc[0]
                ),
                key="transfer_out_select",
            )

            try:
                transfer_data = build_transfer_center(
                    my_team,
                    predictions,
                    player_out_id=selected_out,
                    budget=bank_value,
                )

                rec_name = str(transfer_data["recommended_player"])
                rec_price = float(transfer_data["recommended_price"])
                gain = float(transfer_data["predicted_gain"])

                out_row = my_team_players[
                    my_team_players["player_id"] == selected_out
                ].iloc[0]

                st.markdown(
                    f"""
                    <div class="card ai-card">
                        <div class="small-muted">Recommended move</div>
                        <div style="height:14px"></div>
                        <div style="display:grid;grid-template-columns:1fr 42px 1fr;gap:8px;align-items:center;">
                            <div class="transfer-player">
                                <div class="transfer-tag">OUT</div>
                                <div class="transfer-name">{out_row["name"]}</div>
                                <div class="small-muted">£{float(out_row["price"]):.1f}m</div>
                            </div>
                            <div class="arrow">→</div>
                            <div class="transfer-player">
                                <div class="transfer-tag">IN</div>
                                <div class="transfer-name">{rec_name}</div>
                                <div class="small-muted">£{rec_price:.1f}m</div>
                            </div>
                        </div>
                        <div style="height:25px"></div>
                        <div class="small-muted">Expected gain</div>
                        <div class="gain">+{gain:.1f} pts</div>
                        <div class="small-muted" style="margin-top:14px;">AI confidence</div>
                        <div class="confidence"><div></div></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                alternatives = transfer_data.get("alternatives")
                if isinstance(alternatives, pd.DataFrame) and not alternatives.empty:
                    with st.expander("View alternatives"):
                        st.dataframe(
                            format_player_table(alternatives),
                            width="stretch",
                            hide_index=True,
                        )

            except TransferAnalysisError as exc:
                st.warning(str(exc))
            except Exception as exc:
                st.warning(f"Transfer analysis unavailable: {exc}")

    # FIXTURES
    with fixtures_col:
        st.markdown('<div class="section-label">Fixtures</div>', unsafe_allow_html=True)
        st.markdown("### Next 5")

        fixture_view = predictions.copy()
        if "difficulty" in fixture_view.columns:
            fixture_view = fixture_view.sort_values(
                "difficulty",
                ascending=True,
            )

        shown = 0
        fixture_html = '<div class="card">'
        for _, row in fixture_view.head(5).iterrows():
            opponent = str(row.get("opponent", "Unknown"))
            difficulty = row.get("difficulty", None)
            try:
                diff = float(difficulty)
            except (TypeError, ValueError):
                diff = 3

            cls = "hard" if diff >= 4 else "medium" if diff >= 3 else ""
            fixture_html += (
                f'<div class="fixture-row">'
                f'<span>{opponent}</span>'
                f'<span>{"" if difficulty is None else int(diff)}'
                f'<span class="fixture-dot {cls}"></span></span>'
                f'</div>'
            )
            shown += 1

        if shown == 0:
            fixture_html += '<div class="small-muted">No fixture data available.</div>'

        fixture_html += "</div>"
        st.markdown(fixture_html, unsafe_allow_html=True)


    # SECONDARY CARDS
    st.write("")
    captain_col, summary_col, form_col = st.columns([.85, 1.05, 1.8])

    with captain_col:
        st.markdown('<div class="section-label">Captaincy</div>', unsafe_allow_html=True)
        st.markdown("### Captain Pick")

        captain = team_analysis.get("captain_id")
        captain_row = (
            my_team_players[
                my_team_players["player_id"] == captain
            ].iloc[0]
            if captain is not None
            and not my_team_players[
                my_team_players["player_id"] == captain
            ].empty
            else None
        )

        if captain_row is not None:
            st.markdown(
                f"""
                <div class="card">
                    <div class="avatar">{str(captain_row["name"])[:2].upper()}</div>
                    <div style="text-align:center;margin-top:8px;font-weight:800;">
                        {captain_row["name"]}
                    </div>
                    <div style="text-align:center;color:#70e000;font-weight:800;">
                        {float(captain_row["predicted_points"]):.1f} pts
                    </div>
                    <div class="small-muted" style="text-align:center;margin-top:4px;">
                        Captain
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="card"><div class="small-muted">'
                'Captain information appears after loading your team.'
                '</div></div>',
                unsafe_allow_html=True,
            )

    with summary_col:
        st.markdown('<div class="section-label">Squad health</div>', unsafe_allow_html=True)
        st.markdown("### Team Summary")

        strongest = team_analysis.get("strongest_position") or "—"
        weakest = team_analysis.get("weakest_position") or "—"

        st.markdown(
            f"""
            <div class="card">
                <div style="font-size:2rem;font-weight:850;color:#70e000;">
                    {team_rating:.1f}<span style="font-size:.85rem;color:#8f9bad;"> / 10</span>
                </div>
                <div class="small-muted">Overall AI rating</div>
                <div style="height:13px"></div>
                <div style="display:flex;justify-content:space-between;">
                    <span>Strongest</span><strong class="positive">{strongest}</strong>
                </div>
                <div style="display:flex;justify-content:space-between;margin-top:7px;">
                    <span>Weakest</span><strong class="warning">{weakest}</strong>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with form_col:
        st.markdown('<div class="section-label">Market watch</div>', unsafe_allow_html=True)
        st.markdown("### Player Form")

        form_players = predictions.head(5)
        form_cols = st.columns(min(5, max(1, len(form_players))))

        for column, (_, player) in zip(form_cols, form_players.iterrows()):
            with column:
                name = str(player.get("name", "Player"))
                pts = player.get("predicted_points")
                try:
                    pts_text = f"{float(pts):.1f}"
                except (TypeError, ValueError):
                    pts_text = "—"

                st.markdown(
                    f"""
                    <div class="card form-card">
                        <div class="avatar">{name[:2].upper()}</div>
                        <div class="form-name">{name}</div>
                        <div class="form-points">{pts_text} pts</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


    # TOP PLAYERS + AI INSIGHT
    st.write("")
    table_col, insight_col = st.columns([2.1, 1])

    with table_col:
        st.markdown('<div class="section-label">Gameweek market</div>', unsafe_allow_html=True)
        st.markdown("### Top Players")

        top_table = predictions.head(10).copy()
        st.dataframe(
            format_player_table(top_table),
            width="stretch",
            hide_index=True,
        )

    with insight_col:
        st.markdown('<div class="section-label">AI analyst</div>', unsafe_allow_html=True)
        st.markdown("### AI Insight")

        if my_team is not None and team_analysis.get("weakest_position"):
            insight = (
                f"Your squad's current weakness is {team_analysis['weakest_position']}. "
                "Prioritize upgrades there when the expected gain and fixture run support the move."
            )
        else:
            insight = (
                "Load your FPL team to unlock squad-specific AI insights, "
                "transfer opportunities and captain recommendations."
            )

        st.markdown(
            f"""
            <div class="card" style="min-height:250px;">
                <div class="insight">{insight}</div>
                <div style="height:30px"></div>
                <div class="small-muted">
                    Prediction source
                </div>
                <div style="margin-top:5px;font-weight:700;">
                    {prediction_path.stem}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# -------------------------------------------------------------------
# OTHER PAGES
# -------------------------------------------------------------------

elif page == "Players":
    st.markdown('<div class="section-label">Player intelligence</div>', unsafe_allow_html=True)
    st.title("Players")
    f1, f2, f3 = st.columns(3)

    with f1:
        positions = ["All"] + sorted(predictions["position"].dropna().astype(str).unique())
        selected_position = st.selectbox("Position", positions)
    with f2:
        teams = ["All"] + sorted(predictions["team"].dropna().astype(str).unique())
        selected_team = st.selectbox("Team", teams)
    with f3:
        minimum_points = st.slider("Minimum AI Points", 0.0, 10.0, 0.0, .5)

    filtered = predictions.copy()
    if selected_position != "All":
        filtered = filtered[filtered["position"] == selected_position]
    if selected_team != "All":
        filtered = filtered[filtered["team"] == selected_team]
    filtered = filtered[filtered["predicted_points"] >= minimum_points]

    st.dataframe(
        format_player_table(filtered),
        width="stretch",
        hide_index=True,
    )

elif page == "Fixtures":
    st.markdown('<div class="section-label">Fixture intelligence</div>', unsafe_allow_html=True)
    st.title("Fixtures")

    fixture_columns = [
        c for c in
        ["name", "team", "opponent", "home", "difficulty", "predicted_points"]
        if c in predictions.columns
    ]
    fixture_preview = predictions[fixture_columns].head(30).copy()

    if "home" in fixture_preview.columns:
        fixture_preview["Fixture"] = predictions.loc[
            fixture_preview.index
        ].apply(get_fixture_label, axis=1)
        fixture_preview = fixture_preview.drop(columns=["home"], errors="ignore")

    st.dataframe(
        fixture_preview.rename(
            columns={
                "name": "Player",
                "team": "Team",
                "opponent": "Opponent",
                "difficulty": "Difficulty",
                "predicted_points": "AI Points",
            }
        ),
        width="stretch",
        hide_index=True,
    )

elif page == "Transfer Center":
    st.markdown('<div class="section-label">Transfer engine</div>', unsafe_allow_html=True)
    st.title("Transfer Center")

    if my_team is None:
        st.info("Load your FPL team first.")
    else:
        players = prepare_my_team(my_team, predictions)
        if players.empty:
            st.warning("No matching player predictions found.")
        else:
            selected_out = st.selectbox(
                "Player to transfer out",
                players["player_id"].tolist(),
                format_func=lambda pid: str(
                    players.loc[players["player_id"] == pid, "name"].iloc[0]
                ),
            )
            try:
                center = build_transfer_center(
                    my_team,
                    predictions,
                    player_out_id=selected_out,
                    budget=bank_value,
                )
                c1, c2, c3 = st.columns(3)
                c1.metric("Recommended", center["recommended_player"])
                c2.metric("Expected Gain", f'+{float(center["predicted_gain"]):.1f}')
                c3.metric("Price", f'£{float(center["recommended_price"]):.1f}m')

                alternatives = center.get("alternatives")
                if isinstance(alternatives, pd.DataFrame):
                    st.dataframe(
                        format_player_table(alternatives),
                        width="stretch",
                        hide_index=True,
                    )
            except TransferAnalysisError as exc:
                st.warning(str(exc))

elif page == "AI Recommendations":
    st.markdown('<div class="section-label">Decision engine</div>', unsafe_allow_html=True)
    st.title("AI Recommendations")

    if optimal_squad is not None:
        st.subheader("Optimal Squad")
        st.dataframe(
            format_player_table(optimal_squad),
            width="stretch",
            hide_index=True,
        )
    else:
        st.error(optimizer_error or "Optimizer unavailable.")

elif page == "My Team":
    st.markdown('<div class="section-label">Squad intelligence</div>', unsafe_allow_html=True)
    st.title(team_name)

    if my_team is None:
        st.info("Load your team above.")
    else:
        st.json(
            {
                "team": team_name,
                "projected_points": projected_team_points,
                "team_rating": team_rating,
                "strongest_position": team_analysis.get("strongest_position"),
                "weakest_position": team_analysis.get("weakest_position"),
            }
        )

elif page == "Chips":
    st.markdown('<div class="section-label">Strategy</div>', unsafe_allow_html=True)
    st.title("Chips")
    st.info("Chip intelligence is the next strategy module to be connected.")

elif page == "Statistics":
    st.markdown('<div class="section-label">Analytics</div>', unsafe_allow_html=True)
    st.title("Statistics")
    st.dataframe(
        predictions.describe(include="all").transpose(),
        width="stretch",
    )

elif page == "Settings":
    st.markdown('<div class="section-label">Application</div>', unsafe_allow_html=True)
    st.title("Settings")
    st.caption(f"Prediction source: {prediction_path.name}")
    st.caption(f"Players loaded: {len(predictions):,}")


st.divider()
st.caption("FPL-AI • Local development • Dark analytics interface")
