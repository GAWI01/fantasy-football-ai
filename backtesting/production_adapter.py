from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from feature_contract import (
    FEATURE_COLUMNS,
    build_feature_row,
    validate_model_feature_names,
    validate_model_metadata,
    validate_feature_provenance,
)
from .engine import BacktestConfig, BacktestEngine
from .leakage import LookaheadError


class PredictionAdapterError(ValueError):
    pass


class FPLHistoricalPredictionAdapter:
    """Adapter for the existing FPL-AI model with production-aligned timing.

    Historical performance data available at decision GW G is passed to the
    predictor. The fixture rows for target GW G+1 are schedule information
    already known at decision time; their realised target columns are never
    passed into model.predict().
    """

    def __init__(self, project_root, model_path=None):
        self.project_root = Path(project_root).resolve()
        self.model_path = (
            Path(model_path).resolve()
            if model_path
            else self.project_root / "models" / "fpl_model_v1_corrected.pkl"
        )
        if not self.model_path.exists():
            raise PredictionAdapterError(f"Model not found: {self.model_path}")

        self.model = joblib.load(self.model_path)
        try:
            validate_model_metadata(self.model)
        except ValueError as exc:
            raise PredictionAdapterError(str(exc)) from exc
        names = getattr(self.model, "feature_names_in_", None)
        if names is not None:
            try:
                validate_model_feature_names(list(names))
            except Exception as exc:
                raise PredictionAdapterError(str(exc)) from exc

        self._target_features: pd.DataFrame | None = None

    def load_season(self, season):
        path = self.project_root / "historical_data" / season / "features.csv"
        if not path.exists():
            raise PredictionAdapterError(
                f"Historical feature dataset not found: {path}"
            )
        frame = pd.read_csv(path)
        required = {"player_id", "GW", "total_points", *FEATURE_COLUMNS}
        missing = required - set(frame.columns)
        if missing:
            raise PredictionAdapterError(
                "features.csv missing required column(s): "
                + ", ".join(sorted(missing))
            )
        return frame

    def predictor(self, history, decision_gw):
        if history.empty:
            raise PredictionAdapterError("Cannot predict from empty history.")

        gw = pd.to_numeric(history["GW"], errors="coerce")
        if (gw.dropna() > decision_gw).any():
            raise PredictionAdapterError(
                "Predictor received future performance-history rows."
            )

        target_gw = decision_gw + 1
        if self._target_features is None:
            raise PredictionAdapterError(
                "Target fixture features were not supplied for this backtest."
            )

        target = self._target_features.copy()
        target_gw_values = pd.to_numeric(target["GW"], errors="coerce")
        if not target_gw_values.eq(target_gw).all():
            raise PredictionAdapterError(
                f"Target feature context must be GW{target_gw}."
            )

        # The target feature row is a pre-match snapshot: only canonical model
        # features and known fixture context are used. Actual points are removed
        # before feature-contract conversion so the outcome cannot leak.
        rows = []
        for _, row in target.sort_values(
            ["player_id", "fixture"] if "fixture" in target.columns else ["player_id"]
        ).iterrows():
            payload = row.to_dict()
            try:
                validate_feature_provenance(payload, target_gw)
            except ValueError as exc:
                raise PredictionAdapterError(str(exc)) from exc
            payload.pop("total_points", None)
            rows.append(build_feature_row(payload))

        matrix = pd.DataFrame(rows, columns=FEATURE_COLUMNS)
        predictions = np.asarray(self.model.predict(matrix), dtype=float)

        if len(predictions) != len(target):
            raise PredictionAdapterError(
                "Model returned an unexpected prediction count."
            )

        ordered_target = target.sort_values(
            ["player_id", "fixture"] if "fixture" in target.columns else ["player_id"]
        )
        result = ordered_target[["player_id"]].copy()
        result["predicted_points"] = predictions
        # If a player has multiple target fixtures (DGW), return one row per
        # fixture. The engine aggregates actuals separately at player/GW level.
        return result

    def backtest_season(self, season, *, start_gw=2, end_gw=None):
        frame = self.load_season(season)

        def predictor(history, decision_gw):
            target_gw = decision_gw + 1
            target = frame[pd.to_numeric(frame["GW"], errors="coerce") == target_gw].copy()
            if target.empty:
                return pd.DataFrame(columns=["player_id", "predicted_points"])
            self._target_features = target
            try:
                return self.predictor(history, decision_gw)
            finally:
                self._target_features = None

        return BacktestEngine(
            BacktestConfig(start_gw=start_gw, end_gw=end_gw)
        ).run(frame, predictor)

    def backtest_seasons(self, seasons, *, start_gw=2, end_gw=None):
        outputs = []
        for season in seasons:
            result = self.backtest_season(
                season,
                start_gw=start_gw,
                end_gw=end_gw,
            )
            if not result.empty:
                result.insert(0, "season", season)
                outputs.append(result)

        if not outputs:
            return pd.DataFrame(
                columns=[
                    "season",
                    "GW",
                    "player_id",
                    "predicted_points",
                    "target_gw",
                    "actual_points",
                ]
            )

        return pd.concat(outputs, ignore_index=True)
