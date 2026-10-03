"""Read-only validation of the small, versioned backend serving bundle."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data_loader import CURRENT_DATA_DIR, DataLoaderError, validate_current_data
from .data_manifest import load_current_manifest


CURRENT_FILES = (
    "players_current.csv", "players_raw.csv", "teams_current.csv",
    "fixtures_current.csv", "gameweeks_current.csv",
)
PREDICTION_COLUMNS = {
    "player_id", "name", "position", "team", "price", "predicted_points",
}


def validate_runtime_artifacts(data_dir: Path = CURRENT_DATA_DIR) -> dict:
    """Validate structure, publication metadata and row integrity, not freshness."""
    try:
        validate_current_data(data_dir)
        manifest = load_current_manifest(data_dir / "manifest.json")
        sidecar = manifest.prediction_path.with_suffix(".csv.manifest.json")
        if json.loads(sidecar.read_text(encoding="utf-8")) != json.loads(
            (data_dir / "manifest.json").read_text(encoding="utf-8")
        ):
            raise ValueError("Prediction sidecar does not match manifest.json")
        predictions = pd.read_csv(manifest.prediction_path)
        missing = PREDICTION_COLUMNS - set(predictions.columns)
        if missing:
            raise ValueError("Prediction columns missing: " + ", ".join(sorted(missing)))
        if len(predictions) != manifest.player_count:
            raise ValueError("Prediction row count does not match manifest")
        numeric = predictions[["player_id", "price", "predicted_points"]].apply(
            pd.to_numeric, errors="coerce"
        )
        if not np.isfinite(numeric.to_numpy()).all():
            raise ValueError("Prediction numeric values must be finite")
        ids = numeric["player_id"]
        if ids.duplicated().any() or (ids <= 0).any() or (ids % 1 != 0).any():
            raise ValueError("Prediction player IDs must be unique positive integers")
        if predictions[list(PREDICTION_COLUMNS)].isna().any(axis=None):
            raise ValueError("Prediction serving fields cannot be empty")
        players = pd.read_csv(data_dir / "players_current.csv")
        if not set(ids).issubset(set(players["player_id"])):
            raise ValueError("Predictions reference unknown player IDs")
    except (OSError, DataLoaderError, pd.errors.ParserError, ValueError) as exc:
        raise ValueError(f"Runtime artifact validation failed: {exc}") from exc
    return {
        "loaded": True,
        "files": [*CURRENT_FILES, "manifest.json", manifest.prediction_file, sidecar.name],
        "prediction_rows": len(predictions),
    }


if __name__ == "__main__":
    print(json.dumps(validate_runtime_artifacts(), indent=2))
