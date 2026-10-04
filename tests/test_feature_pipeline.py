"""The production feature code: causal rolling windows, DGWs and contract v3."""

import pandas as pd
import pytest

from feature_contract import FEATURE_COLUMNS, FeatureContractError, build_feature_row, feature_matrix
from historical_data.build_features import build_feature_frame


def fixture_row(gw, points, *, fixture=None, minutes=90, player=1, position="MID", **values):
    return {"element": player, "GW": gw, "fixture": fixture or gw * 100 + player, "position": position,
            "value": 60, "was_home": True, "opponent_team": 2, "total_points": points,
            "minutes": minutes, "goals_scored": 0, "assists": 0, "bps": 10, "influence": 20,
            "creativity": 10, "threat": 10, "ict_index": 4, **values}


def fixtures_for(rows):
    return pd.DataFrame([{"id": row["fixture"], "team_h_difficulty": 2, "team_a_difficulty": 4}
                         for row in rows]).drop_duplicates("id")


def test_contract_v3_has_fixture_difficulty_and_no_club_id_or_duplicate_xp():
    assert "fixture_difficulty" in FEATURE_COLUMNS
    assert "position" in FEATURE_COLUMNS
    assert not {"opponent_team", "xP", "form_5"} & set(FEATURE_COLUMNS)


def test_build_feature_row_rejects_missing_required_feature():
    with pytest.raises(FeatureContractError):
        build_feature_row({"price": 6.0, "was_home": True, "position": "MID"})


def test_rolling_features_use_only_earlier_gameweeks():
    rows = [fixture_row(1, 2), fixture_row(2, 20), fixture_row(3, 5)]
    frame = build_feature_frame(pd.DataFrame(rows), fixtures_for(rows)).set_index("GW")
    assert frame.loc[1, "points_last_5"] == 0
    assert frame.loc[2, "points_last_5"] == 2
    assert frame.loc[3, "points_last_5"] == 22
    assert frame.loc[3, "history_cutoff_gw"] == 2
    assert frame.loc[3, "history_gw_count"] == 2
    assert frame.loc[3, "xP"] == frame.loc[3, "points_avg_5"] == 11


def test_double_gameweek_fixtures_never_see_each_other():
    rows = [fixture_row(1, 2), fixture_row(2, 10, fixture=201), fixture_row(2, 1, fixture=202, minutes=20),
            fixture_row(3, 4)]
    frame = build_feature_frame(pd.DataFrame(rows), fixtures_for(rows))
    assert frame.loc[frame.GW == 2, "points_last_5"].tolist() == [2, 2]
    gw3 = frame[frame.GW == 3].iloc[0]
    assert gw3["points_last_5"] == 13
    # A 60-minute appearance counts once per fixture, not once per Gameweek total.
    assert gw3["starts_last_5"] == 2


def test_unplayed_target_rows_get_features_from_completed_history():
    rows = [fixture_row(1, 6), fixture_row(2, 8), fixture_row(3, None, minutes=None)]
    frame = build_feature_frame(pd.DataFrame(rows), fixtures_for(rows))
    target = frame[frame.GW == 3].iloc[0]
    assert target["points_avg_5"] == 7
    assert target["fixture_difficulty"] == 2  # home side of the fixture


def test_a_completed_gameweek_after_an_unplayed_one_is_rejected():
    rows = [fixture_row(1, None, minutes=None), fixture_row(2, 8)]
    with pytest.raises(ValueError, match="out of order"):
        build_feature_frame(pd.DataFrame(rows), fixtures_for(rows))


def test_assistant_manager_rows_are_not_players():
    rows = [fixture_row(1, 2), fixture_row(1, 9, player=2, position="AM")]
    frame = build_feature_frame(pd.DataFrame(rows), fixtures_for(rows))
    assert frame["player_id"].tolist() == [1]


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_model_matrix_rejects_nonfinite_inputs(value):
    rows = [fixture_row(1, 2)]
    frame = build_feature_frame(pd.DataFrame(rows), fixtures_for(rows))
    frame["fixture_difficulty"] = value
    with pytest.raises(FeatureContractError, match="finite"):
        feature_matrix(frame)
