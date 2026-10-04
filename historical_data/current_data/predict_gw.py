"""Regenerate a full current player pool only with compatible, validated provenance."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from feature_contract import (FEATURE_COLUMNS, FeatureContractError, build_feature_row,
                              feature_metadata, validate_feature_provenance, validate_model_metadata)
from player_validation import filter_current_fpl_players
from backend.data_manifest import publish_prediction_artifact, season_for_date
from historical_data.current_data.xmins import availability_label, availability_multiplier

CURRENT_DIR = Path(__file__).resolve().parent
MODEL_PATH = PROJECT_ROOT / "models" / "fpl_model_v1_corrected.pkl"
PLAYERS_PATH = CURRENT_DIR / "players_features_current.csv"
TEAMS_PATH = CURRENT_DIR / "teams_current.csv"
FIXTURES_PATH = CURRENT_DIR / "fixtures_current.csv"
GAMEWEEKS_PATH = CURRENT_DIR / "gameweeks_current.csv"


def num(value, default: float = 0.0) -> float:
    value = pd.to_numeric(value, errors="coerce")
    return default if pd.isna(value) else float(value)


def calculate_xp(form, points_per_game, minutes, expected_goals, expected_assists) -> float:
    """Legacy helper retained for callers; regeneration uses canonical row xP.

    Season cumulative attacking totals are unsuitable for a fixture forecast.
    The compatible recipe uses completed-GW rolling means instead.
    """
    return float(max(0, points_per_game) * np.clip(minutes / 90, 0, 1))


def load_prediction_model(model_path: Path | None = None):
    path = Path(model_path or MODEL_PATH)
    model = joblib.load(path)
    metadata = validate_model_metadata(model)
    # Column names or the word "corrected" do not certify semantics or quality.
    certificate_path = path.with_suffix(path.suffix + ".metadata.json")
    try:
        certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if (certificate.get("validation_state") != "validated"
                or certificate.get("model_sha256") != digest
                or any(certificate.get(k) != v for k, v in feature_metadata().items())):
            raise ValueError("model certificate is incompatible or unverified")
        report_path = (path.parent / certificate["validation_report_file"]).resolve()
        report_path.relative_to(path.parent.resolve())
        report_bytes = report_path.read_bytes()
        if hashlib.sha256(report_bytes).hexdigest() != certificate["validation_report_sha256"]:
            raise ValueError("validation report digest mismatch")
        report = json.loads(report_bytes)
        if (report.get("model_sha256") != digest
                or report.get("validation_state") != "validated"
                or any(report.get(k) != v for k, v in feature_metadata().items())
                or report.get("production_parity_verified") is not True
                or report.get("xp_timing_verified") is not True
                or not report.get("held_out_season")
                or not report.get("train_seasons")
                or report["held_out_season"] in report["train_seasons"]):
            raise ValueError("validation report lacks honest temporal and production parity evidence")
        metrics = report["metrics"]
        seasons = [*report["train_seasons"], report["held_out_season"]]
        if (not all(isinstance(s, str) and re.fullmatch(r"\d{4}-\d{2}", s) for s in seasons)
                or any(int(s[:4]) >= int(report["held_out_season"][:4]) for s in report["train_seasons"])):
            raise ValueError("validation report has an invalid temporal split")
        if metrics["rows"] <= 0 or not all(np.isfinite(metrics[k]) and metrics[k] >= 0 for k in ["mae", "rmse"]):
            raise ValueError("validation metrics are invalid")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise FeatureContractError(f"Model provenance requires honest regeneration/revalidation: {exc}") from exc
    return model, {**metadata, **certificate, "model_file": path.name,
                   "evaluation": {"leakage_safe": report["xp_timing_verified"],
                                  "production_parity": report["production_parity_verified"],
                                  "report_id": certificate["validation_report_file"],
                                  "report_sha256": certificate["validation_report_sha256"]}}


def generate_predictions(players, teams, fixtures, gw, model):
    players = filter_current_fpl_players(players, teams)
    if players.empty or players.player_id.duplicated().any():
        raise ValueError("A nonempty, unique current player pool is required")
    names = dict(zip(teams.id.astype(int), teams.name))
    name_to_id = {name: team_id for team_id, name in names.items()}
    team_data = {int(team.id): team.to_dict() for _, team in teams.iterrows()}
    fixture_lookup = {}
    for _, f in fixtures[pd.to_numeric(fixtures.event, errors="raise").eq(gw)].iterrows():
        for team_id, opponent_id, home, difficulty in [
            (int(f.team_h), int(f.team_a), True, num(f.get("team_h_difficulty", 0))),
            (int(f.team_a), int(f.team_h), False, num(f.get("team_a_difficulty", 0)))]:
            fixture_lookup.setdefault(team_id, []).append(
                {"opponent_id": opponent_id, "home": home, "difficulty": difficulty})
    results = []
    for _, player in players.iterrows():
        validate_feature_provenance(player.to_dict(), gw)
        if str(player.get("history_complete", False)).lower() != "true":
            raise FeatureContractError("Completed history coverage is incomplete; regeneration required")
        if "prediction_event" in player and num(player.prediction_event) != gw:
            raise FeatureContractError("Features target a different prediction Gameweek")
        if any(column not in player for column in ["xmins", "availability_multiplier", "start_probability"]):
            raise FeatureContractError("Prediction inputs lack explicit availability/xMins")
        team_id = name_to_id.get(str(player.team))
        if team_id is None:
            team_id = int(player.team)
        team_fixtures = fixture_lookup.get(team_id, [])
        available = min(availability_multiplier(player), np.clip(num(player.availability_multiplier), 0, 1))
        per_fixture_minutes = np.clip(num(player.xmins), 0, 90 * available) if available > 0 else 0
        probability = min(available, np.clip(num(player.start_probability), 0, 1)) if per_fixture_minutes > 0 else 0
        predicted, raw, xp_total = 0.0, 0.0, 0.0
        opponents, homes, difficulties = [], [], []
        for f in team_fixtures:
            payload = player.to_dict()
            payload.update(was_home=f["home"], opponent_team=f["opponent_id"],
                           position=str(player.position).upper().replace("GKP", "GK"))
            matrix = pd.DataFrame([build_feature_row(payload)], columns=FEATURE_COLUMNS)
            ml = float(model.predict(matrix)[0])
            if not np.isfinite(ml):
                raise FeatureContractError("Model returned nonfinite prediction")
            own, opponent = team_data.get(team_id, {}), team_data.get(f["opponent_id"], {})
            advantage = .015 * (num(own.get("strength_attack_home" if f["home"] else "strength_attack_away", 0))
                               - num(opponent.get("strength_defence_away" if f["home"] else "strength_defence_home", 0)))
            difficulty_factor = np.clip(1 - ((f["difficulty"] - 1) / 10), .70, 1.10)
            adjusted = max(0, ml) * np.clip((1 + advantage) * difficulty_factor, .75, 1.25)
            # Hard zero for absent/zero-minute players; retain established partial
            # start scaling until this postprocessing is honestly revalidated.
            adjusted = adjusted * (.75 + .25 * probability) if per_fixture_minutes > 0 and available > 0 else 0
            predicted += float(np.clip(adjusted, 0, 15))
            raw += ml if per_fixture_minutes > 0 and available > 0 else 0
            xp_total += num(player.xP) if per_fixture_minutes > 0 and available > 0 else 0
            opponents.append(names.get(f["opponent_id"], str(f["opponent_id"])))
            homes.append(f["home"])
            difficulties.append(f["difficulty"])
        price = num(player.get("price", 0))
        display = player.get("web_name") or player.get("second_name") or str(player.player_id)
        results.append({"player_id": int(player.player_id), "name": str(display),
                        "position": player.position, "team": names.get(team_id, str(player.team)),
                        "price": price, "opponent": " / ".join(opponents),
                        "home": homes[0] if len(homes) == 1 else None,
                        "difficulty": np.mean(difficulties) if difficulties else 0,
                        "fixture_count": len(team_fixtures), "form": num(player.get("form", 0)),
                        "minutes": num(player.get("minutes", 0)), "xP": round(xp_total, 3),
                        "xmins": round(per_fixture_minutes * len(team_fixtures), 1),
                        "start_probability": round(probability if team_fixtures else 0, 3),
                        "availability_multiplier": round(available, 3),
                        "availability": availability_label(player), "status": player.get("status", "a"),
                        "chance_of_playing_next_round": player.get("chance_of_playing_next_round"),
                        "ml_prediction": round(raw, 3), "predicted_points": round(predicted, 3),
                        "value": round(predicted / price, 3) if price > 0 else 0,
                        "feature_contract_version": player.feature_contract_version,
                        "xp_source": player.xp_source, "history_cutoff_gw": player.history_cutoff_gw,
                        "history_complete": player.history_complete, "prediction_event": gw})
    return pd.DataFrame(results).sort_values("predicted_points", ascending=False, kind="mergesort")


def main() -> None:
    model, provenance = load_prediction_model()
    players, teams = pd.read_csv(PLAYERS_PATH), pd.read_csv(TEAMS_PATH)
    fixtures, gameweeks = pd.read_csv(FIXTURES_PATH), pd.read_csv(GAMEWEEKS_PATH)
    upcoming = gameweeks[gameweeks.is_next.astype(str).str.lower().eq("true")]
    if len(upcoming) != 1:
        raise RuntimeError("Exactly one next Gameweek is required")
    gw = int(upcoming.iloc[0].id)
    first_gw = gameweeks[pd.to_numeric(gameweeks.id, errors="raise").eq(1)]
    if len(first_gw) != 1 or "deadline_time" not in gameweeks:
        raise FeatureContractError("Source season requires the GW1 deadline")
    try:
        first_deadline = datetime.fromisoformat(str(first_gw.iloc[0].deadline_time))
        next_deadline = datetime.fromisoformat(str(upcoming.iloc[0].deadline_time))
    except ValueError as exc:
        raise FeatureContractError("Source Gameweek deadlines are invalid") from exc
    if first_deadline.tzinfo is None or next_deadline.tzinfo is None:
        raise FeatureContractError("Source Gameweek deadlines must be timezone-aware")
    source_season = season_for_date(first_deadline)
    if season_for_date(next_deadline) != source_season:
        raise FeatureContractError("Source Gameweeks span incompatible seasons")
    result = generate_predictions(players, teams, fixtures, gw, model)
    result["prediction_season"] = source_season
    provenance["prediction_season"] = source_season
    input_paths = [PLAYERS_PATH, TEAMS_PATH, FIXTURES_PATH, GAMEWEEKS_PATH]
    provenance["input_sha256"] = hashlib.sha256(b"".join(path.read_bytes() for path in input_paths)).hexdigest()
    provenance["input_files"] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths}
    source_directory = Path(__file__).resolve().parent
    source_paths = [Path(__file__), PROJECT_ROOT / "feature_contract.py",
                    source_directory / "xmins.py", source_directory / "build_player_features.py"]
    # Content-address the actual generator sources, including local changes.
    provenance["code_revision"] = "sha256:" + hashlib.sha256(
        b"".join(path.read_bytes() for path in source_paths if path.is_file())).hexdigest()
    output_path = CURRENT_DIR / f"gw{gw}_predictions_v11.csv"
    manifest = publish_prediction_artifact(
        output_path, result.to_csv(index=False, lineterminator="\n").encode("utf-8"),
        season=source_season, prediction_event=gw,
        player_count=len(result), model_provenance=provenance)
    print(f"GW{gw}: {len(result)} players published to {output_path}; manifest: {manifest}")


if __name__ == "__main__":
    main()
