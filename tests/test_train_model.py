import pandas as pd

from historical_data.train_model import prepare_data


def test_prepare_data_targets_current_gameweek_when_features_are_for_that_gameweek():
    frame = pd.DataFrame(
        [
            {
                "player_id": 1,
                "GW": 1,
                "total_points": 6,
                "position": "MID",
                "xP": 0,
                "feature_contract_version": 2,
                "xp_source": "previous_completed_gw_points_mean_v1",
                "history_cutoff_gw": 0,
                "price": 6,
                "was_home": True,
                "points_last_3": 0,
                "points_last_5": 0,
                "points_avg_5": 0,
                "minutes_last_5": 0,
                "starts_last_5": 0,
                "goals_last_5": 0,
                "assists_last_5": 0,
                "bps_avg_5": 0,
                "influence_avg_5": 0,
                "creativity_avg_5": 0,
                "threat_avg_5": 0,
                "ict_index_avg_5": 0,
                "form_5": 0,
                "opponent_team": 2,
            },
            {
                "player_id": 1,
                "GW": 2,
                "total_points": 9,
                "position": "MID",
                "xP": 6,
                "feature_contract_version": 2,
                "xp_source": "previous_completed_gw_points_mean_v1",
                "history_cutoff_gw": 1,
                "price": 6,
                "was_home": False,
                "points_last_3": 6,
                "points_last_5": 6,
                "points_avg_5": 6,
                "minutes_last_5": 90,
                "starts_last_5": 1,
                "goals_last_5": 1,
                "assists_last_5": 0,
                "bps_avg_5": 20,
                "influence_avg_5": 30,
                "creativity_avg_5": 10,
                "threat_avg_5": 20,
                "ict_index_avg_5": 6,
                "form_5": 6,
                "opponent_team": 3,
            },
        ]
    )

    result = prepare_data(frame)

    assert result["GW"].tolist() == [1, 2]
    assert result["target"].tolist() == [6.0, 9.0]
