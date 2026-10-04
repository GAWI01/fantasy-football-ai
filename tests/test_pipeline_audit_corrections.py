import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from backend.data_manifest import publish_prediction_manifest
from feature_contract import FEATURE_COLUMNS, FeatureContractError, build_feature_row
from feature_contract import feature_metadata
from historical_data.current_data import predict_gw, xmins
from historical_data.train_model import prepare_data, evaluate_model
from historical_data import build_features as historical_features
from backend import data_manifest


def player(player_id=1, **values):
    return {"player_id": player_id, "name": "Surname", "second_name": "Surname",
            "position": "MID", "team": "Arsenal", "price": 6.0, "status": "a",
            "chance_of_playing_next_round": 100, "minutes": 180, "form": 4,
            "points_per_game": 4, "expected_goals": 10, "expected_assists": 8,
            **values}


def history(gw, points, **values):
    return {"player_id": 1, "GW": gw, "fixture": gw * 100,
            "total_points": points, "minutes": 90, "goals_scored": 1,
            "assists": 0, "bps": 20, "influence": 30, "creativity": 12,
            "threat": 24, "ict_index": 6.6, **values}


def feature_row(**values):
    return {**{c: 0 for c in FEATURE_COLUMNS}, "position": "MID", "price": 6,
            "fixture_difficulty": 3, "xP": 0, **feature_metadata(),
            "history_cutoff_gw": 1, "history_complete": True, **values}


def test_availability_probability_is_not_minutes_probability():
    result = xmins.build_xmins_columns(pd.DataFrame([player(
        minutes_last_5=225, starts_last_5=0, chance_of_playing_next_round=50)]))
    assert result.loc[0, "availability_multiplier"] == 0.5
    assert result.loc[0, "start_probability"] <= 0.5


def test_injured_player_with_positive_official_chance_remains_a_risk():
    result = xmins.build_xmins_columns(pd.DataFrame([player(
        status="i", chance_of_playing_next_round=75, minutes_last_5=450, starts_last_5=5)]))
    assert result.loc[0, "availability_multiplier"] == 0.75
    assert result.loc[0, "xmins"] == 67.5
    assert result.loc[0, "availability"] == "MINOR_RISK"


def test_zero_completed_history_does_not_fall_back_to_old_season_minutes():
    result = xmins.build_xmins_columns(pd.DataFrame([player(
        history_gw_count=5, minutes_last_5=0, starts_last_5=0)]))
    assert result.loc[0, "xmins"] == 0


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_feature_contract_rejects_nonfinite_values(value):
    with pytest.raises(FeatureContractError, match="finite"):
        build_feature_row(feature_row(price=value))


def test_training_rejects_unverified_same_gameweek_xp():
    frame = pd.DataFrame([feature_row(GW=2, player_id=1, total_points=4, xP=8)])
    frame = frame.drop(columns=["feature_contract_version", "xp_source", "history_cutoff_gw"])
    with pytest.raises(FeatureContractError, match="provenance"):
        prepare_data(frame)


def test_training_rejects_a_history_cutoff_in_the_target_gameweek():
    frame = pd.DataFrame([feature_row(GW=2, player_id=1, total_points=4,
                                      history_cutoff_gw=2)])
    with pytest.raises(FeatureContractError, match="cutoff"):
        prepare_data(frame)


def test_training_rejects_xp_that_does_not_match_its_claimed_recipe():
    with pytest.raises(FeatureContractError, match="recipe"):
        prepare_data(pd.DataFrame([feature_row(GW=2, player_id=1, total_points=4,
                                              xP=9, points_avg_5=2)]))


def test_training_does_not_silently_replace_invalid_history_features_with_zero():
    with pytest.raises(FeatureContractError, match="finite"):
        prepare_data(pd.DataFrame([feature_row(GW=2, player_id=1, total_points=4,
                                              minutes_last_5=float("inf"))]))


def test_model_evaluation_does_not_display_historical_first_names(capsys):
    rows = pd.DataFrame([feature_row(player_id=1, GW=2, name="First Surname",
                                    second_name="Surname", total_points=4),
                         feature_row(player_id=2, GW=2, name="Other Family",
                                     second_name="Family", total_points=6)])
    evaluate_model(ConstantModel(), rows[list(FEATURE_COLUMNS)], pd.Series([4, 6]), rows)
    output = capsys.readouterr().out
    assert "First Surname" not in output
    assert "Surname" in output


def test_historical_builder_replaces_unverified_scraped_xp_using_only_prior_gws(tmp_path, monkeypatch):
    directory = tmp_path / "2024-25"
    directory.mkdir()
    pd.DataFrame([history(1, 2, value=60, position="MID", xP=999, was_home=True),
                  history(2, 10, value=60, position="MID", xP=888, was_home=True),
                  history(2, 1, fixture=202, value=60, position="MID", xP=777, was_home=False),
                  history(3, 3, value=60, position="MID", xP=666, was_home=True)]).to_csv(
                      directory / "merged_gw.csv", index=False)
    monkeypatch.setattr(historical_features, "BASE", tmp_path)
    assert historical_features.build_features("2024-25")
    result = pd.read_csv(directory / "features.csv")
    assert result.loc[result.GW == 2, "xP"].tolist() == [2, 2]
    assert result.loc[result.GW == 3, "xP"].tolist() == [6.5]
    assert result.loc[result.GW == 3, "history_cutoff_gw"].tolist() == [2]


def test_manifest_rerun_is_idempotent_and_retains_original_timestamp(tmp_path):
    artifact = tmp_path / "gw3_predictions_v11.csv"
    artifact.write_bytes(b"player_id,predicted_points\n1,5.2\n")
    path = publish_prediction_manifest(artifact, season="2026-27", prediction_event=3, player_count=1)
    previous = path.read_bytes()
    publish_prediction_manifest(artifact, season="2026-27", prediction_event=3, player_count=1)
    assert path.read_bytes() == previous


def test_identical_legacy_rerun_preserves_immutable_metadata_bytes(tmp_path):
    artifact = tmp_path / "gw3.csv"
    artifact.write_bytes(b"player_id,predicted_points\n1,5\n")
    payload = {"season": "2026-27", "prediction_event": 3, "prediction_file": artifact.name,
               "generated_at": "2026-08-31T18:00:00+00:00", "player_count": 1, "schema_version": 1}
    sidecar = artifact.with_suffix(".csv.manifest.json")
    sidecar.write_bytes(json.dumps(payload, indent=4).replace("\n", "\r\n").encode("utf-8"))
    manifest = tmp_path / "manifest.json"
    manifest.write_bytes(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    originals = [path.read_bytes() for path in [artifact, sidecar, manifest]]
    publish_prediction_manifest(artifact, season="2026-27", prediction_event=3, player_count=1)
    assert [path.read_bytes() for path in [artifact, sidecar, manifest]] == originals


def test_a_validation_flag_without_evidence_remains_unverified(tmp_path):
    artifact = tmp_path / "gw3_predictions_v11.csv"
    artifact.write_text("player_id,predicted_points\n1,5\n", encoding="utf-8")
    path = publish_prediction_manifest(artifact, season="2026-27", prediction_event=3,
                                      player_count=1, model_provenance={"validation_state": "validated"})
    manifest = data_manifest.load_current_manifest(path)
    assert data_manifest.model_validation_state(manifest) == "unverified"


def test_failed_pointer_publication_rolls_back_and_keeps_previous_forecast(tmp_path, monkeypatch):
    old = tmp_path / "gw2.csv"
    path = data_manifest.publish_prediction_artifact(
        old, b"player_id,predicted_points\n1,5\n", season="2026-27", prediction_event=2, player_count=1)
    original = path.read_bytes()
    new = tmp_path / "gw3.csv"
    real_replace = type(path).replace

    def fail_pointer(source, destination):
        if destination == path:
            raise OSError("simulated pointer failure")
        return real_replace(source, destination)

    monkeypatch.setattr(type(path), "replace", fail_pointer)
    with pytest.raises(OSError, match="pointer failure"):
        data_manifest.publish_prediction_artifact(
            new, b"player_id,predicted_points\n1,6\n", season="2026-27", prediction_event=3, player_count=1)
    assert path.read_bytes() == original
    assert old.read_bytes() == b"player_id,predicted_points\n1,5\n"
    assert not new.exists()
    assert not new.with_suffix(".csv.manifest.json").exists()


def test_competing_writer_cannot_overwrite_a_publication_in_progress(tmp_path, monkeypatch):
    artifact = tmp_path / "gw3.csv"
    real_replace = type(artifact).replace
    attempted = False

    def compete(source, destination):
        nonlocal attempted
        if destination == artifact and not attempted:
            attempted = True
            with pytest.raises(ValueError, match="in progress"):
                data_manifest.publish_prediction_artifact(
                    artifact, b"player_id,predicted_points\n1,9\n", season="2026-27",
                    prediction_event=3, player_count=1)
        return real_replace(source, destination)

    monkeypatch.setattr(type(artifact), "replace", compete)
    path = data_manifest.publish_prediction_artifact(
        artifact, b"player_id,predicted_points\n1,5\n", season="2026-27", prediction_event=3, player_count=1)
    assert artifact.read_bytes() == b"player_id,predicted_points\n1,5\n"
    assert data_manifest.load_current_manifest(path).player_count == 1


@pytest.mark.parametrize("content", [
    b"player_id,predicted_points\n1,nan\n", b"player_id,predicted_points\n1,inf\n",
    b"player_id,predicted_points\n1,-1\n", b"player_id,predicted_points\n0,2\n",
    b"player_id,predicted_points\n1.5,2\n", b"player_id,predicted_points\n1,2\n1,3\n",
    b"player_id,other\n1,2\n", b"player_id,predicted_points\n"])
def test_invalid_new_forecast_is_rejected_before_any_publication(tmp_path, content):
    path = tmp_path / "gw3.csv"
    with pytest.raises(ValueError):
        data_manifest.publish_prediction_artifact(path, content, season="2026-27",
                                                 prediction_event=3, player_count=1)
    assert not path.exists()
    assert not (tmp_path / "manifest.json").exists()


@pytest.mark.parametrize(("season", "event"), [("2026-27", 39), ("bad", 3), ("2026-99", 3)])
def test_loader_rejects_invalid_season_or_event_metadata(tmp_path, season, event):
    artifact = tmp_path / "gw3.csv"
    artifact.write_text("player_id,predicted_points\n1,2\n", encoding="utf-8")
    manifest = {"season": season, "prediction_event": event, "prediction_file": artifact.name,
                "generated_at": "2026-10-04T00:00:00+00:00", "player_count": 1, "schema_version": 1}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        data_manifest.load_current_manifest(path)


class ConstantModel:
    feature_names_in_ = np.array(FEATURE_COLUMNS)
    feature_contract_metadata_ = feature_metadata()

    def predict(self, matrix):
        return np.full(len(matrix), 4.0)


def certified_model(tmp_path, *, train_seasons=None, metrics=None, sklearn_version=None):
    import joblib
    import sklearn
    from sklearn.compose import ColumnTransformer
    from sklearn.dummy import DummyRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    path = tmp_path / "fpl_model_v3.pkl"
    sklearn_version = sklearn_version or sklearn.__version__
    model = Pipeline([("pre", ColumnTransformer([
        ("position", OneHotEncoder(handle_unknown="ignore"), ["position"]),
        ("numeric", "passthrough", [c for c in FEATURE_COLUMNS if c != "position"])])),
        ("model", DummyRegressor())])
    model.fit(pd.DataFrame([feature_row()], columns=FEATURE_COLUMNS), [4])
    model.feature_contract_metadata_ = {**feature_metadata(), "validation_state": "unverified"}
    joblib.dump(model, path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    report = {**feature_metadata(), "validation_state": "validated", "model_sha256": digest,
              "production_parity_verified": True, "xp_timing_verified": True,
              "held_out_season": "2024-25", "train_seasons": train_seasons or ["2023-24"],
              "metrics": metrics or {"rows": 2, "mae": 1, "rmse": 1}}
    report_bytes = json.dumps(report).encode("utf-8")
    (tmp_path / "validation.json").write_bytes(report_bytes)
    certificate = {**feature_metadata(), "validation_state": "validated", "model_sha256": digest,
                   "sklearn_version": sklearn_version,
                   "validation_report_file": "validation.json",
                   "validation_report_sha256": hashlib.sha256(report_bytes).hexdigest()}
    path.with_suffix(".pkl.metadata.json").write_text(json.dumps(certificate), encoding="utf-8")
    return path


def test_future_training_seasons_cannot_certify_an_earlier_holdout(tmp_path):
    path = certified_model(tmp_path, train_seasons=["2025-26"])
    with pytest.raises(FeatureContractError, match="temporal"):
        predict_gw.load_prediction_model(path)


def test_negative_validation_error_cannot_certify_a_model(tmp_path):
    path = certified_model(tmp_path, metrics={"rows": 2, "mae": -1, "rmse": 1})
    with pytest.raises(FeatureContractError, match="metrics"):
        predict_gw.load_prediction_model(path)


def test_default_prediction_model_is_certified_and_hash_linked(tmp_path, monkeypatch):
    path = certified_model(tmp_path)
    monkeypatch.setattr(predict_gw, "MODEL_PATH", path)
    model, provenance = predict_gw.load_prediction_model()
    assert model.predict(pd.DataFrame([feature_row()], columns=FEATURE_COLUMNS)).tolist() == [4]
    assert provenance["model_file"] == "fpl_model_v3.pkl"
    assert provenance["evaluation"]["production_parity"] is True


def test_tampering_with_certified_model_bytes_rejects_regeneration(tmp_path):
    path = certified_model(tmp_path)
    # joblib permits trailing bytes; the independent digest must still reject it.
    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(FeatureContractError, match="provenance"):
        predict_gw.load_prediction_model(path)


def test_model_trained_with_another_scikit_learn_version_is_rejected(tmp_path):
    path = certified_model(tmp_path, sklearn_version="0.0.1")
    with pytest.raises(FeatureContractError, match="scikit-learn"):
        predict_gw.load_prediction_model(path)


def test_model_without_feature_provenance_is_rejected(tmp_path, monkeypatch):
    model = ConstantModel()
    model.feature_contract_metadata_ = None
    monkeypatch.setattr(predict_gw.joblib, "load", lambda path: model)
    with pytest.raises(FeatureContractError, match="provenance"):
        predict_gw.load_prediction_model(tmp_path / "fpl_model_v3.pkl")
