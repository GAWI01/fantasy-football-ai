import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from backend.data_manifest import publish_prediction_manifest
from feature_contract import FEATURE_COLUMNS, FeatureContractError, build_feature_row
from feature_contract import feature_metadata
from historical_data.current_data import build_player_features, predict_gw, xmins
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
            "opponent_team": 2, "feature_contract_version": 2,
            "xp_source": "previous_completed_gw_points_mean_v1",
            "history_cutoff_gw": 1, "history_complete": True, **values}


def setup_builder(tmp_path, monkeypatch, players, histories, target=3):
    pd.DataFrame(players).to_csv(tmp_path / "players_current.csv", index=False)
    for gw, frame in histories.items():
        pd.DataFrame(frame).to_csv(tmp_path / f"gw{gw}_history.csv", index=False)
    pd.DataFrame([{"id": target, "is_next": True}]).to_csv(
        tmp_path / "gameweeks_current.csv", index=False)
    monkeypatch.setattr(build_player_features, "BASE", tmp_path)
    monkeypatch.setattr(build_player_features, "PLAYERS_FILE", tmp_path / "players_current.csv")
    monkeypatch.setattr(build_player_features, "GW1_FILE", tmp_path / "gw1_history.csv")
    monkeypatch.setattr(build_player_features, "OUTPUT_FILE", tmp_path / "players_features_current.csv")


def test_current_builder_uses_all_completed_history_and_retains_ict(tmp_path, monkeypatch):
    # Regresses reading GW1 only and dropping the ICT source columns.
    setup_builder(tmp_path, monkeypatch, [player()], {
        1: [history(1, 2, minutes_gw1=90, started_gw1=1, played_gw1=1,
                    total_points_gw1=2, goals_gw1=1, assists_gw1=0)],
        2: [history(2, 8)], 3: [history(3, 100)]})
    build_player_features.main()
    result = pd.read_csv(tmp_path / "players_features_current.csv").iloc[0]
    assert result["points_last_5"] == 10
    assert result["points_avg_5"] == 5
    assert result["influence_avg_5"] == 30
    assert result["creativity_avg_5"] == 12
    assert result["threat_avg_5"] == 24
    assert result["ict_index_avg_5"] == 6.6
    assert result["xP"] == 5
    assert result["history_cutoff_gw"] == 2


def test_missing_history_is_not_converted_to_explicit_nonappearance(tmp_path, monkeypatch):
    setup_builder(tmp_path, monkeypatch, [player(), player(2, minutes=90)], {
        1: [history(1, 0, minutes_gw1=0, started_gw1=0, played_gw1=0,
                    total_points_gw1=0, goals_gw1=0, assists_gw1=0, minutes=0)]}, target=2)
    build_player_features.main()
    result = pd.read_csv(tmp_path / "players_features_current.csv").set_index("player_id")
    assert result.loc[1, "xmins"] == 0
    assert result.loc[2, "xmins"] == 90


def test_xmins_writer_preserves_existing_rolling_features(tmp_path, monkeypatch):
    root = tmp_path / "project"
    directory = root / "historical_data" / "current_data"
    directory.mkdir(parents=True)
    pd.DataFrame([player()]).to_csv(directory / "players_current.csv", index=False)
    pd.DataFrame([player(points_last_5=21, minutes_last_5=360, starts_last_5=4)]).to_csv(
        directory / "players_features_current.csv", index=False)
    monkeypatch.setattr(xmins, "__file__", str(directory / "xmins.py"))
    xmins.main()
    result = pd.read_csv(directory / "players_features_current.csv")
    assert result.loc[0, "points_last_5"] == 21
    assert result.loc[0, "minutes_last_5"] == 360


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


def test_zero_minutes_has_zero_xp():
    assert predict_gw.calculate_xp(4, 4, 0, 10, 8) == 0


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_feature_contract_rejects_nonfinite_values(value):
    with pytest.raises(FeatureContractError, match="finite"):
        build_feature_row(feature_row(xP=value))


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
    pd.DataFrame([history(1, 2, value=60, position="MID", xP=999),
                  history(2, 10, value=60, position="MID", xP=888),
                  history(2, 1, fixture=202, value=60, position="MID", xP=777),
                  history(3, 3, value=60, position="MID", xP=666)]).to_csv(
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
    feature_contract_metadata_ = {"feature_contract_version": 2,
                                  "xp_source": "previous_completed_gw_points_mean_v1",
                                  "target": "same_fixture_total_points"}

    def predict(self, matrix):
        return np.full(len(matrix), 4.0)


def setup_prediction(tmp_path, monkeypatch, players, fixtures):
    frame = pd.DataFrame([{**feature_row(), **p} for p in players])
    frame.to_csv(tmp_path / "players_features_current.csv", index=False)
    pd.DataFrame([{"id": 1, "name": "Arsenal"}, {"id": 2, "name": "Liverpool"},
                  {"id": 3, "name": "Chelsea"}, {"id": 4, "name": "Spurs"}]).to_csv(
                      tmp_path / "teams_current.csv", index=False)
    pd.DataFrame(fixtures).to_csv(tmp_path / "fixtures_current.csv", index=False)
    pd.DataFrame([{"id": 1, "is_next": False, "deadline_time": "2026-08-21T17:30:00Z"},
                  {"id": 3, "is_next": True, "deadline_time": "2026-09-04T17:30:00Z"}]).to_csv(
                      tmp_path / "gameweeks_current.csv", index=False)
    monkeypatch.setattr(predict_gw, "CURRENT_DIR", tmp_path)
    for name, file in [("PLAYERS_PATH", "players_features_current.csv"),
                       ("TEAMS_PATH", "teams_current.csv"),
                       ("FIXTURES_PATH", "fixtures_current.csv"),
                       ("GAMEWEEKS_PATH", "gameweeks_current.csv")]:
        monkeypatch.setattr(predict_gw, name, tmp_path / file)
    # Model selection has separate real artifact/certificate regression tests.
    monkeypatch.setattr(predict_gw.joblib, "load", lambda path: ConstantModel())
    monkeypatch.setattr(predict_gw, "load_prediction_model", lambda *args, **kwargs: (
        ConstantModel(), {"validation_state": "validated"}), raising=False)


def fixture(home=1, away=2, fixture_id=301):
    return {"id": fixture_id, "event": 3, "team_h": home, "team_a": away,
            "team_h_difficulty": 3, "team_a_difficulty": 3}


def test_prediction_keeps_blank_players_and_zeros_unavailable(tmp_path, monkeypatch):
    setup_prediction(tmp_path, monkeypatch,
                     [player(xmins=90, start_probability=1, availability_multiplier=1),
                      player(2, team="Chelsea", xmins=90, start_probability=1, availability_multiplier=1),
                      player(3, status="i", xmins=0, start_probability=0, availability_multiplier=0)],
                     [fixture()])
    predict_gw.main()
    result = pd.read_csv(tmp_path / "gw3_predictions_v11.csv").set_index("player_id")
    assert set(result.index) == {1, 2, 3}
    assert result.loc[2, "predicted_points"] == 0
    assert result.loc[2, "xmins"] == 0
    assert result.loc[3, "predicted_points"] == 0
    assert result.loc[3, "start_probability"] == 0


def test_prediction_minutes_cannot_exceed_official_availability(tmp_path, monkeypatch):
    setup_prediction(tmp_path, monkeypatch,
                     [player(xmins=90, start_probability=1, availability_multiplier=1,
                             chance_of_playing_next_round=50)], [fixture()])
    predict_gw.main()
    result = pd.read_csv(tmp_path / "gw3_predictions_v11.csv").iloc[0]
    assert result.xmins <= 45
    assert result.start_probability <= .5


def test_forecast_season_comes_from_source_gameweeks_not_generation_date(tmp_path, monkeypatch):
    setup_prediction(tmp_path, monkeypatch,
                     [player(xmins=90, start_probability=1, availability_multiplier=1)], [fixture()])
    pd.DataFrame([{"id": 1, "is_next": False, "deadline_time": "2025-08-15T17:30:00Z"},
                  {"id": 3, "is_next": True, "deadline_time": "2025-08-29T17:30:00Z"}]).to_csv(
                      tmp_path / "gameweeks_current.csv", index=False)
    predict_gw.main()
    manifest = data_manifest.load_current_manifest(tmp_path / "manifest.json")
    assert manifest.season == "2025-26"


def test_prediction_aggregates_both_double_gameweek_fixtures(tmp_path, monkeypatch):
    setup_prediction(tmp_path, monkeypatch,
                     [player(xmins=90, start_probability=1, availability_multiplier=1)],
                     [fixture(), fixture(away=3, fixture_id=302)])
    predict_gw.main()
    result = pd.read_csv(tmp_path / "gw3_predictions_v11.csv")
    assert len(result) == 1
    assert result.loc[0, "predicted_points"] == pytest.approx(6.4)
    assert result.loc[0, "xmins"] == 180


def test_prediction_conflict_preserves_certified_csv_and_manifest_bytes(tmp_path, monkeypatch):
    setup_prediction(tmp_path, monkeypatch,
                     [player(xmins=90, start_probability=1, availability_multiplier=1)], [fixture()])
    artifact = tmp_path / "gw3_predictions_v11.csv"
    artifact.write_bytes(b"player_id,predicted_points\n99,9.9\n")
    manifest = publish_prediction_manifest(artifact, season="2026-27", prediction_event=3, player_count=1)
    sidecar = artifact.with_suffix(".csv.manifest.json")
    originals = [path.read_bytes() for path in [artifact, manifest, sidecar]]
    with pytest.raises(ValueError, match="immutable"):
        predict_gw.main()
    assert [path.read_bytes() for path in [artifact, manifest, sidecar]] == originals


def test_prediction_rejects_model_without_matching_feature_provenance(tmp_path, monkeypatch):
    original_loader = getattr(predict_gw, "load_prediction_model", None)
    setup_prediction(tmp_path, monkeypatch,
                     [player(xmins=90, start_probability=1, availability_multiplier=1)], [fixture()])
    if original_loader is None:
        monkeypatch.delattr(predict_gw, "load_prediction_model")
    else:
        monkeypatch.setattr(predict_gw, "load_prediction_model", original_loader)
    model = ConstantModel()
    model.feature_contract_metadata_ = None
    monkeypatch.setattr(predict_gw.joblib, "load", lambda path: model)
    monkeypatch.setattr(predict_gw, "MODEL_PATH", tmp_path / "fpl_model_v1_corrected.pkl")
    with pytest.raises(FeatureContractError, match="provenance"):
        predict_gw.main()


def certified_model(tmp_path, *, train_seasons=None, metrics=None):
    import joblib
    from sklearn.compose import ColumnTransformer
    from sklearn.dummy import DummyRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    path = tmp_path / "fpl_model_v1_corrected.pkl"
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


def test_default_prediction_model_is_corrected_and_hash_linked(tmp_path, monkeypatch):
    path = certified_model(tmp_path)
    monkeypatch.setattr(predict_gw, "MODEL_PATH", path)
    model, provenance = predict_gw.load_prediction_model()
    assert model.predict(pd.DataFrame([feature_row()], columns=FEATURE_COLUMNS)).tolist() == [4]
    assert provenance["model_file"] == "fpl_model_v1_corrected.pkl"
    assert provenance["evaluation"]["production_parity"] is True


def test_tampering_with_certified_model_bytes_rejects_regeneration(tmp_path):
    path = certified_model(tmp_path)
    # joblib permits trailing bytes; the independent digest must still reject it.
    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(FeatureContractError, match="provenance"):
        predict_gw.load_prediction_model(path)
