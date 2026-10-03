import json
import shutil
from pathlib import Path

import pytest

from backend.runtime_artifacts import validate_runtime_artifacts


SOURCE = Path(__file__).resolve().parents[1] / "historical_data" / "current_data"
FILES = (
    "players_current.csv", "players_raw.csv", "teams_current.csv",
    "fixtures_current.csv", "gameweeks_current.csv", "manifest.json",
    "gw3_predictions_v11.csv", "gw3_predictions_v11.csv.manifest.json",
)


@pytest.fixture
def bundle(tmp_path):
    for name in FILES:
        shutil.copyfile(SOURCE / name, tmp_path / name)
    return tmp_path


def test_serving_bundle_is_self_contained(bundle):
    result = validate_runtime_artifacts(bundle)
    assert result["loaded"] is True
    assert result["prediction_rows"] == 623
    assert set(result["files"]) == set(FILES)


@pytest.mark.parametrize("name", FILES)
def test_missing_runtime_file_fails_validation(bundle, name):
    (bundle / name).unlink()
    with pytest.raises(ValueError):
        validate_runtime_artifacts(bundle)


def test_manifest_row_count_must_match_csv(bundle):
    for name in ("manifest.json", "gw3_predictions_v11.csv.manifest.json"):
        path = bundle / name
        payload = json.loads(path.read_text())
        payload["player_count"] = 624
        path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="row count"):
        validate_runtime_artifacts(bundle)


def test_prediction_sidecar_must_match_manifest(bundle):
    path = bundle / "gw3_predictions_v11.csv.manifest.json"
    payload = json.loads(path.read_text())
    payload["prediction_event"] = 4
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="sidecar"):
        validate_runtime_artifacts(bundle)


def test_prediction_csv_requires_serving_columns(bundle):
    (bundle / "gw3_predictions_v11.csv").write_text("player_id,predicted_points\n1,2\n")
    with pytest.raises(ValueError, match="columns"):
        validate_runtime_artifacts(bundle)
