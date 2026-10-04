import json

import pandas as pd

from app import (
    PREDICTIONS_DIR,
    get_prediction_file,
    prepare_predictions,
    get_fixture_label,
)


def test_get_prediction_file_uses_the_served_forecast():
    manifest = json.loads((PREDICTIONS_DIR / "manifest.json").read_text(encoding="utf-8"))
    path = get_prediction_file()

    assert path.exists()
    assert path.name == manifest["prediction_file"]


def test_get_prediction_file_falls_back_to_legacy_files(tmp_path, monkeypatch):
    import app

    (tmp_path / "gw2_predictions_v5.csv").write_text("player_id\n1\n", encoding="utf-8")
    monkeypatch.setattr(app, "PREDICTIONS_DIR", tmp_path)

    assert app.get_prediction_file().name == "gw2_predictions_v5.csv"


def test_prepare_predictions_contains_required_display_columns():
    players = pd.DataFrame(
        {
            "name": ["Player A"],
            "position": ["MID"],
            "team": ["Chelsea"],
            "price": [7.5],
            "predicted_points": [6.5],
        }
    )

    result = prepare_predictions(players)

    assert "name" in result.columns
    assert "position" in result.columns
    assert "team" in result.columns
    assert "price" in result.columns
    assert "predicted_points" in result.columns


def test_prepare_predictions_sorts_by_predicted_points():
    players = pd.DataFrame(
        {
            "name": ["Low", "High"],
            "position": ["MID", "MID"],
            "team": ["A", "B"],
            "price": [5.0, 7.0],
            "predicted_points": [2.0, 8.0],
        }
    )

    result = prepare_predictions(players)

    assert result.iloc[0]["name"] == "High"
    assert result.iloc[1]["name"] == "Low"


def test_get_fixture_label_handles_home_fixture():
    row = pd.Series(
        {
            "team": "Chelsea",
            "opponent": "Brighton",
            "was_home": True,
        }
    )

    assert get_fixture_label(row) == "Chelsea vs Brighton"


def test_get_fixture_label_handles_away_fixture():
    row = pd.Series(
        {
            "team": "Chelsea",
            "opponent": "Brighton",
            "was_home": False,
        }
    )

    assert get_fixture_label(row) == "Brighton vs Chelsea"
def test_prepare_my_team_contains_prediction_columns():
    from app_team import merge_team_with_predictions

    team = {
        "team_id": 1234567,
        "name": "Test Team",
        "picks": [
            {
                "player_id": 10,
                "position": 1,
                "multiplier": 1,
            },
        ],
    }

    predictions = pd.DataFrame(
        {
            "player_id": [10],
            "name": ["Player A"],
            "position": ["GK"],
            "team": ["Team A"],
            "price": [5.0],
            "predicted_points": [6.5],
        }
    )

    result = merge_team_with_predictions(
        team,
        predictions,
    )

    assert "player_id" in result.columns
    assert "name" in result.columns
    assert "position" in result.columns
    assert "price" in result.columns
    assert "predicted_points" in result.columns


def test_prepare_my_team_preserves_multiplier():
    from app_team import merge_team_with_predictions

    team = {
        "team_id": 1234567,
        "name": "Test Team",
        "picks": [
            {
                "player_id": 10,
                "position": 1,
                "multiplier": 2,
            },
        ],
    }

    predictions = pd.DataFrame(
        {
            "player_id": [10],
            "name": ["Captain Player"],
            "predicted_points": [7.0],
        }
    )

    result = merge_team_with_predictions(
        team,
        predictions,
    )

    assert result.iloc[0]["multiplier"] == 2


def test_prepare_my_team_sorts_by_fpl_position():
    from app import prepare_my_team

    team = {
        "team_id": 1234567,
        "name": "Test Team",
        "picks": [
            {"player_id": 30, "position": 4, "multiplier": 1},
            {"player_id": 10, "position": 1, "multiplier": 1},
            {"player_id": 20, "position": 2, "multiplier": 1},
            {"player_id": 21, "position": 2, "multiplier": 1},
            {"player_id": 40, "position": 3, "multiplier": 1},
        ],
    }

    predictions = pd.DataFrame(
        {
            "player_id": [10, 20, 21, 30, 40],
            "name": [
                "Goalkeeper",
                "Defender A",
                "Defender B",
                "Forward",
                "Midfielder",
            ],
            "position": ["GK", "DEF", "DEF", "FWD", "MID"],
            "team": ["A", "B", "B", "C", "D"],
            "price": [5.0, 5.0, 5.5, 7.0, 6.5],
            "predicted_points": [5.0, 6.0, 5.5, 7.5, 8.0],
        }
    )

    result = prepare_my_team(
        team,
        predictions,
    )

    assert list(result["player_id"]) == [
        10,
        20,
        21,
        40,
        30,
    ]


def test_prepare_my_team_preserves_captain_multiplier():
    from app import prepare_my_team

    team = {
        "team_id": 1234567,
        "name": "Test Team",
        "picks": [
            {
                "player_id": 10,
                "position": 1,
                "multiplier": 2,
            },
        ],
    }

    predictions = pd.DataFrame(
        {
            "player_id": [10],
            "name": ["Captain"],
            "position": ["GK"],
            "price": [5.0],
            "predicted_points": [6.0],
        }
    )

    result = prepare_my_team(
        team,
        predictions,
    )

    assert result.iloc[0]["multiplier"] == 2


def test_prepare_my_team_handles_missing_predictions():
    from app import prepare_my_team

    team = {
        "team_id": 1234567,
        "name": "Test Team",
        "picks": [
            {
                "player_id": 999,
                "position": 1,
                "multiplier": 1,
            },
        ],
    }

    predictions = pd.DataFrame(
        {
            "player_id": [10],
            "name": ["Other Player"],
            "position": ["GK"],
            "price": [5.0],
            "predicted_points": [6.0],
        }
    )

    result = prepare_my_team(
        team,
        predictions,
    )

    assert len(result) == 1
    assert result.iloc[0]["player_id"] == 999
    assert pd.isna(result.iloc[0]["predicted_points"])


def test_get_team_summary():
    from app import get_team_summary

    team = {
        "team_id": 1234567,
        "name": "Test Team",
        "bank": 15,
        "event": 3,
        "transfers": 1,
        "picks": [
            {"player_id": 10},
            {"player_id": 20},
        ],
    }

    summary = get_team_summary(team)

    assert summary["team_id"] == 1234567
    assert summary["name"] == "Test Team"
    assert summary["bank"] == 15
    assert summary["event"] == 3
    assert summary["transfers"] == 1
    assert summary["players"] == 2

def test_build_team_display_contains_starting_xi_and_bench():
    from app import build_team_display

    team = {
        "name": "Test Team",
        "picks": [
            {"player_id": 1, "position": 1, "multiplier": 1},
            {"player_id": 2, "position": 2, "multiplier": 1},
            {"player_id": 3, "position": 2, "multiplier": 1},
            {"player_id": 4, "position": 2, "multiplier": 1},
            {"player_id": 5, "position": 2, "multiplier": 1},
            {"player_id": 6, "position": 3, "multiplier": 1},
            {"player_id": 7, "position": 3, "multiplier": 1},
            {"player_id": 8, "position": 3, "multiplier": 1},
            {"player_id": 9, "position": 3, "multiplier": 1},
            {"player_id": 10, "position": 4, "multiplier": 1},
            {"player_id": 11, "position": 4, "multiplier": 1},
            {"player_id": 12, "position": 2, "multiplier": 0},
            {"player_id": 13, "position": 3, "multiplier": 0},
            {"player_id": 14, "position": 3, "multiplier": 0},
            {"player_id": 15, "position": 4, "multiplier": 0},
        ],
    }

    predictions = pd.DataFrame(
        {
            "player_id": list(range(1, 16)),
            "name": [f"Player {i}" for i in range(1, 16)],
            "position": (
                ["GK"]
                + ["DEF"] * 4
                + ["MID"] * 4
                + ["FWD"] * 2
                + ["DEF", "MID", "MID", "FWD"]
            ),
            "team": ["Team"] * 15,
            "price": [5.0] * 15,
            "predicted_points": [5.0] * 15,
        }
    )

    result = build_team_display(
        team,
        predictions,
    )

    assert "starting_xi" in result
    assert "bench" in result
    assert len(result["starting_xi"]) == 11
    assert len(result["bench"]) == 4


def test_build_team_display_includes_prediction_columns():
    from app import build_team_display

    team = {
        "name": "Test Team",
        "picks": [
            {
                "player_id": 1,
                "position": 1,
                "multiplier": 1,
            }
        ],
    }

    predictions = pd.DataFrame(
        {
            "player_id": [1],
            "name": ["Test Player"],
            "position": ["GK"],
            "team": ["Team"],
            "price": [5.0],
            "predicted_points": [6.5],
        }
    )

    result = build_team_display(
        team,
        predictions,
    )

    player = result["starting_xi"].iloc[0]

    assert player["name"] == "Test Player"
    assert player["price"] == 5.0
    assert player["predicted_points"] == 6.5


def test_build_team_display_preserves_captain():
    from app import build_team_display

    team = {
        "name": "Test Team",
        "picks": [
            {
                "player_id": 1,
                "position": 1,
                "multiplier": 1,
            },
            {
                "player_id": 2,
                "position": 2,
                "multiplier": 2,
            },
        ],
    }

    predictions = pd.DataFrame(
        {
            "player_id": [1, 2],
            "name": ["Keeper", "Captain"],
            "position": ["GK", "DEF"],
            "team": ["A", "B"],
            "price": [5.0, 6.0],
            "predicted_points": [4.0, 7.0],
        }
    )

    result = build_team_display(
        team,
        predictions,
    )

    assert result["captain_id"] == 2

def test_analyze_my_team_returns_prediction_summary():
    from app import analyze_my_team

    team = {
        "name": "Test Team",
        "picks": [
            {
                "player_id": 1,
                "position": 1,
                "multiplier": 1,
            },
            {
                "player_id": 2,
                "position": 2,
                "multiplier": 2,
            },
            {
                "player_id": 3,
                "position": 3,
                "multiplier": 1,
            },
        ],
    }

    predictions = pd.DataFrame(
        {
            "player_id": [1, 2, 3],
            "name": ["Keeper", "Captain", "Midfielder"],
            "position": ["GK", "DEF", "MID"],
            "team": ["A", "B", "C"],
            "price": [5.0, 6.0, 7.0],
            "predicted_points": [4.0, 8.0, 6.0],
        }
    )

    result = analyze_my_team(
        team,
        predictions,
    )

    assert result["total_predicted_points"] == 18.0
    assert result["best_player_id"] == 2
    assert result["best_player_name"] == "Captain"
    assert result["captain_id"] == 2

def test_analyze_my_team_includes_position_analysis():
    from app import analyze_my_team

    team = {
        "name": "Test Team",
        "picks": [
            {
                "player_id": 1,
                "position": 1,
                "multiplier": 1,
            },
            {
                "player_id": 2,
                "position": 2,
                "multiplier": 1,
            },
            {
                "player_id": 3,
                "position": 2,
                "multiplier": 1,
            },
            {
                "player_id": 4,
                "position": 3,
                "multiplier": 1,
            },
        ],
    }

    predictions = pd.DataFrame(
        {
            "player_id": [1, 2, 3, 4],
            "name": [
                "Keeper",
                "Defender A",
                "Defender B",
                "Midfielder",
            ],
            "position": [
                "GK",
                "DEF",
                "DEF",
                "MID",
            ],
            "team": ["A", "B", "C", "D"],
            "price": [5.0, 5.0, 5.0, 7.0],
            "predicted_points": [6.0, 3.0, 4.0, 8.0],
        }
    )

    result = analyze_my_team(
        team,
        predictions,
    )

    assert result["strongest_position"] == "MID"
    assert result["weakest_position"] == "DEF"
    assert result["team_rating"] > 0