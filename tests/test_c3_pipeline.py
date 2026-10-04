import pandas as pd

from backtesting.c3_pipeline import (
    C3PipelineConfig,
    calculate_backtest_metrics,
    validate_backtest_results,
)
from feature_contract import FEATURE_CONTRACT_VERSION


def test_backtest_metrics_are_deterministic():
    frame = pd.DataFrame(
        {
            "predicted_points": [2.0, 4.0, 8.0],
            "actual_points": [3.0, 3.0, 6.0],
        }
    )
    metrics = calculate_backtest_metrics(frame)
    assert metrics["rows"] == 3
    assert metrics["mae"] == 4 / 3
    assert round(metrics["rmse"], 6) == round((6 / 3) ** 0.5, 6)


def test_validate_backtest_results_rejects_future_prediction_rows():
    frame = pd.DataFrame(
        {
            "GW": [2, 3],
            "target_gw": [3, 4],
            "predicted_points": [4.0, 5.0],
            "actual_points": [3.0, 6.0],
        }
    )
    validate_backtest_results(frame, decision_gw_column="GW")
def test_c3_pipeline_config_has_safe_corrected_artifact_default(tmp_path):
    config = C3PipelineConfig(project_root=tmp_path)
    assert config.corrected_model_path.name == "fpl_model_v1_corrected.pkl"
    assert config.original_model_path.name == "fpl_model_v1.pkl"


def test_xp_baseline_metrics_use_same_player_gw_keys():
    from backtesting.c3_pipeline import calculate_xp_baseline_metrics

    result = pd.DataFrame({
        "target_gw": [2, 2],
        "player_id": [1, 2],
        "predicted_points": [1.0, 1.0],
        "actual_points": [2.0, 3.0],
    })
    features = pd.DataFrame({
        "GW": [2, 2],
        "player_id": [1, 2],
        "xP": [2.0, 4.0],
        "points_avg_5": [2.0, 4.0],
        "feature_contract_version": [FEATURE_CONTRACT_VERSION] * 2,
        "xp_source": ["previous_completed_gw_points_mean_v1"] * 2,
        "history_cutoff_gw": [1, 1],
    })
    metrics = calculate_xp_baseline_metrics(result, features)
    assert metrics["mae"] == 0.5


def test_per_gw_metrics_return_one_row_per_target_gw():
    from backtesting.c3_pipeline import calculate_per_gw_metrics

    frame = pd.DataFrame({
        "target_gw": [2, 2, 3],
        "predicted_points": [1.0, 3.0, 4.0],
        "actual_points": [2.0, 2.0, 5.0],
    })
    result = calculate_per_gw_metrics(frame)
    assert result["target_gw"].tolist() == [2, 3]
    assert result["rows"].tolist() == [2, 1]
