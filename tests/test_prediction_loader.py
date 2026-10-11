from pathlib import Path
import json

import pytest

from backend.main import (
    _get_prediction_event,
    _select_prediction_file,
)


def test_prediction_event_uses_next_gameweek():
    assert _get_prediction_event(2, 3) == 3


def test_prediction_event_falls_back_to_current_when_no_next_gameweek():
    assert _get_prediction_event(2, None) == 2


def test_select_prediction_file_requires_current_gameweek(
    tmp_path: Path,
):
    (tmp_path / "gw2_predictions_v5.csv").write_text(
        "player_id,predicted_points\n1,5.0\n"
    )
    (tmp_path / "manifest.json").write_text(json.dumps({
        "season": "2026-27",
        "prediction_event": 2,
        "prediction_file": "gw2_predictions_v5.csv",
        "generated_at": "2026-08-28T12:00:00+00:00",
        "player_count": 1,
        "schema_version": 1,
    }))

    with pytest.raises(
        ValueError,
        match="No prediction file found for GW3",
    ):
        _select_prediction_file(tmp_path, 3)


def test_prediction_file_uses_only_manifest_selected_artifact(
    tmp_path: Path,
):
    old_file = tmp_path / "gw3_predictions_v4.csv"
    new_file = tmp_path / "gw3_predictions_v5.csv"

    old_file.write_text(
        "player_id,predicted_points\n1,5.0\n"
    )

    new_file.write_text(
        "player_id,predicted_points\n1,7.5\n"
    )
    (tmp_path / "manifest.json").write_text(json.dumps({
        "season": "2026-27",
        "prediction_event": 3,
        "prediction_file": old_file.name,
        "generated_at": "2026-09-01T08:00:00+00:00",
        "player_count": 1,
        "schema_version": 1,
    }))

    selected = _select_prediction_file(
        tmp_path,
        3,
    )

    assert selected == old_file
