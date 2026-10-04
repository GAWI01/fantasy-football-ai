import joblib
import pandas as pd
import pytest
from sklearn.dummy import DummyRegressor

from backtesting.production_adapter import (
    FPLHistoricalPredictionAdapter,
    PredictionAdapterError,
)
from feature_contract import FEATURE_COLUMNS, feature_metadata


def source_row(price=5.0):
    row = {c: 0.0 for c in FEATURE_COLUMNS}
    row["price"] = price
    row["position"] = "MID"
    row["opponent_team"] = 2.0
    row["was_home"] = 1.0
    return row


def make_model(path):
    X = pd.DataFrame(
        [source_row(5.0), source_row(6.0)],
        columns=FEATURE_COLUMNS,
    )
    numeric = [c for c in FEATURE_COLUMNS if c != "position"]
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.pipeline import Pipeline

    pre = ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore"), ["position"]),
            ("num", "passthrough", numeric),
        ]
    )
    model = Pipeline(
        [
            ("preprocessor", pre),
            ("model", DummyRegressor(strategy="mean")),
        ]
    )
    model.fit(X, [2.0, 3.0])
    model.feature_contract_metadata_ = {**feature_metadata(), "validation_state": "unverified"}
    joblib.dump(model, path)


def target_row(player_id, gw, fixture, points):
    return {
        "player_id": player_id,
        "GW": gw,
        "fixture": fixture,
        "total_points": points,
        **source_row(),
        **feature_metadata(),
        "history_cutoff_gw": gw - 1,
    }


def test_rejects_future_performance_history_rows(tmp_path):
    p = tmp_path / "model.pkl"
    make_model(p)
    a = FPLHistoricalPredictionAdapter(tmp_path, model_path=p)
    a._target_features = pd.DataFrame([target_row(1, 3, 103, 7)])

    history = pd.DataFrame(
        [
            {"player_id": 1, "GW": 1, "total_points": 2, **source_row()},
            {"player_id": 1, "GW": 3, "total_points": 7, **source_row()},
        ]
    )
    with pytest.raises(PredictionAdapterError):
        a.predictor(history, 2)


def test_target_fixture_rows_are_used_without_target_leakage(tmp_path):
    p = tmp_path / "model.pkl"
    make_model(p)
    a = FPLHistoricalPredictionAdapter(tmp_path, model_path=p)

    history = pd.DataFrame(
        [
            {"player_id": 1, "GW": 1, "total_points": 2, **source_row()},
            {"player_id": 2, "GW": 2, "total_points": 4, **source_row()},
        ]
    )
    a._target_features = pd.DataFrame(
        [
            target_row(1, 3, 301, 10),
            target_row(2, 3, 302, 1),
        ]
    )

    out = a.predictor(history, 2)

    assert out["player_id"].tolist() == [1, 2]
    assert len(out) == 2
    assert "actual_points" not in out.columns


def test_double_gameweek_returns_one_prediction_per_fixture(tmp_path):
    p = tmp_path / "model.pkl"
    make_model(p)
    a = FPLHistoricalPredictionAdapter(tmp_path, model_path=p)

    history = pd.DataFrame(
        [{"player_id": 1, "GW": 1, "total_points": 2, **source_row()}]
    )
    a._target_features = pd.DataFrame(
        [
            target_row(1, 2, 201, 5),
            target_row(1, 2, 202, 8),
        ]
    )

    out = a.predictor(history, 1)

    assert out["player_id"].tolist() == [1, 1]
    assert len(out) == 2
