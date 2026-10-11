"""Publish next-Gameweek forecasts from the certified model.

The forecast for Gameweek G is produced by the shared forecasting path
(`historical_data.forecast`): the season's completed history plus G's
fixtures, through the same feature code as training and validation.

Two stages exist, so managers can plan G while G-1 is still being played:

* final: every Gameweek before G is finished and data-checked - the input the
  model was validated on;
* provisional: G-1 is past its deadline but not final yet. The forecast then
  uses history up to G-2 (each player's last five completed Gameweeks end one
  Gameweek earlier) and is replaced by the final forecast once G-1 is checked.

Each player's row stores the model's points if available (`ml_prediction`)
and minutes if available (`xmins_available`). `predicted_points` applies the
official availability at generation time; the API reapplies the latest
official availability on every request.
"""
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

import sklearn  # noqa: E402

from backend.data_manifest import load_current_manifest, publish_prediction_artifact, season_for_date  # noqa: E402
from engine.feature_contract import FeatureContractError, feature_metadata, validate_model_metadata  # noqa: E402
from historical_data.forecast import live_feature_rows, predict_fixture_points  # noqa: E402
from historical_data.current_data.xmins import availability_label, availability_multiplier, calculate_xmins  # noqa: E402
from historical_data.train_model import BASE_DIR as HISTORY_DIR, MODEL_OUTPUT  # noqa: E402

CURRENT_DIR = Path(__file__).resolve().parent
MODEL_PATH = MODEL_OUTPUT
PLAYERS_PATH = CURRENT_DIR / "players_raw.csv"
TEAMS_PATH = CURRENT_DIR / "teams_current.csv"
GAMEWEEKS_PATH = CURRENT_DIR / "gameweeks_current.csv"
ARTIFACT_VERSION = "v13"
DISPLAY_POSITIONS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


class HistoryIncompleteError(RuntimeError):
    """The next Gameweek cannot be forecast until earlier Gameweeks are final."""


def load_prediction_model(model_path: Path | None = None):
    path = Path(model_path or MODEL_PATH)
    try:
        model = joblib.load(path)
        metadata = validate_model_metadata(model)
    except (OSError, EOFError, ValueError) as exc:
        raise FeatureContractError(f"Model provenance requires honest regeneration/revalidation: {exc}") from exc
    # Column names or a file name do not certify semantics or quality.
    certificate_path = path.with_suffix(path.suffix + ".metadata.json")
    try:
        certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if (certificate.get("validation_state") != "validated"
                or certificate.get("model_sha256") != digest
                or any(certificate.get(k) != v for k, v in feature_metadata().items())):
            raise ValueError("model certificate is incompatible or unverified")
        trained_with = certificate.get("sklearn_version")
        if trained_with is not None and trained_with != sklearn.__version__:
            raise ValueError(f"model was trained with scikit-learn {trained_with}, "
                             f"this environment has {sklearn.__version__}")
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


def _is_true(value) -> bool:
    return value is True or str(value).strip().lower() in {"true", "1", "1.0"}


FINAL, PROVISIONAL = "final", "provisional"


def target_gameweek(gameweeks: pd.DataFrame) -> tuple[int, str, int, str]:
    """The next Gameweek, its season, the history cutoff and the forecast stage.

    Final when every earlier Gameweek is final. Provisional when only the
    Gameweek directly before the target is still pending (being played or
    awaiting its data check): the cutoff is then the Gameweek before that.
    """
    upcoming = gameweeks[gameweeks["is_next"].map(_is_true)]
    if len(upcoming) != 1:
        raise RuntimeError("Exactly one next Gameweek is required")
    gw = int(upcoming.iloc[0]["id"])
    first = gameweeks[pd.to_numeric(gameweeks["id"], errors="raise") == 1]
    if len(first) != 1 or "deadline_time" not in gameweeks:
        raise FeatureContractError("Source season requires the GW1 deadline")
    try:
        first_deadline = datetime.fromisoformat(str(first.iloc[0]["deadline_time"]).replace("Z", "+00:00"))
        next_deadline = datetime.fromisoformat(str(upcoming.iloc[0]["deadline_time"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise FeatureContractError("Source Gameweek deadlines are invalid") from exc
    if first_deadline.tzinfo is None or next_deadline.tzinfo is None:
        raise FeatureContractError("Source Gameweek deadlines must be timezone-aware")
    season = season_for_date(first_deadline)
    if season_for_date(next_deadline) != season:
        raise FeatureContractError("Source Gameweeks span incompatible seasons")
    earlier = gameweeks[pd.to_numeric(gameweeks["id"], errors="raise") < gw]
    pending = sorted(int(row["id"]) for _, row in earlier.iterrows()
                     if not (_is_true(row.get("finished")) and _is_true(row.get("data_checked"))))
    if not pending:
        return gw, season, gw - 1, FINAL
    if pending == [gw - 1] and gw >= 2:
        return gw, season, gw - 2, PROVISIONAL
    raise HistoryIncompleteError(
        f"GW{gw} forecasts wait for final scores in GW{', GW'.join(map(str, pending))}")


def _rounded(value: float, digits: int = 3) -> float:
    return float(round(float(value), digits))


def _neutral_fixture_points(model, rows: pd.DataFrame) -> pd.Series:
    """Per-player points for an average fixture (difficulty 3, home and away averaged).

    Lets the planning horizon project a player whose club blanks in the
    target Gameweek; it is never served as that Gameweek's forecast.
    """
    summaries = rows.drop_duplicates("player_id").reset_index(drop=True)
    if summaries.empty:
        return pd.Series(dtype=float)
    home = predict_fixture_points(model, summaries.assign(fixture_difficulty=3.0, was_home=1.0))
    away = predict_fixture_points(model, summaries.assign(fixture_difficulty=3.0, was_home=0.0))
    return pd.Series((home + away) / 2.0, index=summaries["player_id"].to_numpy())


def generate_predictions(players: pd.DataFrame, teams: pd.DataFrame, fixtures: pd.DataFrame,
                         history: pd.DataFrame, gw: int, model, *, history_cutoff: int | None = None) -> pd.DataFrame:
    """One row per current player: fixtures in `gw` summed, blanks scored zero.

    `history_cutoff` (default gw - 1) is the last completed Gameweek used; a
    provisional forecast uses gw - 2 while gw - 1 is still being played.
    """
    if players.empty or players["id"].duplicated().any():
        raise ValueError("A nonempty, unique current player pool is required")
    cutoff = gw - 1 if history_cutoff is None else int(history_cutoff)
    if not 0 <= cutoff < gw:
        raise ValueError("history_cutoff must precede the target Gameweek")
    rounds = pd.to_numeric(history["GW"], errors="raise") if len(history) else pd.Series(dtype=float)
    history = history[rounds <= cutoff] if len(history) else history
    missing = set(range(1, cutoff + 1)) - set(rounds[rounds <= cutoff]) if cutoff >= 1 else set()
    if missing:
        raise HistoryIncompleteError(f"Season history lacks GW{sorted(missing)}")
    fixture_rows, blank_rows = live_feature_rows(history, players, fixtures, gw)
    fixture_rows = fixture_rows.assign(fixture_points=predict_fixture_points(model, fixture_rows))
    neutral = _neutral_fixture_points(model, pd.concat([fixture_rows, blank_rows], ignore_index=True))
    team_names = dict(zip(pd.to_numeric(teams["id"]).astype(int), teams["name"]))
    summaries = pd.concat([fixture_rows, blank_rows], ignore_index=True).drop_duplicates("player_id")
    summaries = summaries.set_index("player_id")
    by_player = {pid: group for pid, group in fixture_rows.groupby("player_id")}

    rows = []
    for player in players.to_dict("records"):
        player_id = int(player["id"])
        matches = by_player.get(player_id)
        summary = summaries.loc[player_id]
        count = 0 if matches is None else len(matches)
        ml = 0.0 if matches is None else float(matches["fixture_points"].sum())
        official = pd.Series({"status": player.get("status", "a"),
                              "chance_of_playing_next_round": player.get("chance_of_playing_next_round"),
                              "news": player.get("news", "")})
        multiplier = float(availability_multiplier(official))
        minutes_input = pd.Series({"minutes_last_5": summary["minutes_last_5"],
                                   "starts_last_5": summary["starts_last_5"],
                                   "history_gw_count": summary["history_gw_count"],
                                   "status": "a", "chance_of_playing_next_round": np.nan})
        per_fixture_minutes = float(calculate_xmins(minutes_input)) if count else 0.0
        xmins_available = per_fixture_minutes * count
        start_available = min(1.0, per_fixture_minutes / 90.0)
        price = float(player["now_cost"]) / 10.0
        predicted = ml * multiplier
        rows.append({
            "player_id": player_id,
            "name": str(player.get("web_name") or player.get("second_name") or f"Player {player_id}"),
            "position": DISPLAY_POSITIONS[int(player["element_type"])],
            "team": team_names.get(int(player["team"]), str(player["team"])),
            "price": price,
            "opponent": " / ".join(team_names.get(int(o), str(o)) for o in matches["opponent_team"]) if count else "",
            "home": bool(matches["was_home"].iloc[0]) if count == 1 else None,
            "difficulty": _rounded(matches["fixture_difficulty"].mean(), 2) if count else None,
            "fixture_count": count,
            "xmins": _rounded(xmins_available * multiplier, 1),
            "xmins_available": _rounded(xmins_available, 1),
            "start_probability": _rounded(start_available * multiplier),
            "start_probability_available": _rounded(start_available),
            "availability_multiplier": _rounded(multiplier),
            "availability": availability_label(official),
            "status": official["status"],
            "chance_of_playing_next_round": official["chance_of_playing_next_round"],
            "ml_prediction": _rounded(ml),
            "ml_per_fixture": _rounded(neutral.get(player_id, 0.0)),
            "predicted_points": _rounded(predicted),
            "value": _rounded(predicted / price) if price > 0 else 0.0,
            "history_gw_count": int(summary["history_gw_count"]),
            "history_cutoff_gw": int(summary["history_cutoff_gw"]),
            "feature_contract_version": int(summary["feature_contract_version"]),
            "xp_source": summary["xp_source"],
            "history_complete": cutoff == gw - 1,
            "prediction_event": gw,
        })
    result = pd.DataFrame(rows)
    return result.sort_values(["predicted_points", "player_id"], ascending=[False, True],
                              kind="mergesort").reset_index(drop=True)


def artifact_path(directory: Path, gw: int, content: bytes) -> Path:
    """Immutable file name: reuse an identical artifact, otherwise add a revision."""
    revision = 1
    while True:
        suffix = "" if revision == 1 else f"_r{revision}"
        path = directory / f"gw{gw}_predictions_{ARTIFACT_VERSION}{suffix}.csv"
        if not path.exists() or path.read_bytes() == content:
            return path
        revision += 1


def _digest(paths: list[Path]) -> str:
    return hashlib.sha256(b"".join(path.read_bytes() for path in paths)).hexdigest()


def _schedule_digest(fixtures: pd.DataFrame, gw: int, line_end: str) -> str:
    events = pd.to_numeric(fixtures["event"], errors="coerce")
    table = fixtures.loc[events == gw, ["id", "team_h", "team_a"]].astype(int).sort_values("id")
    return hashlib.sha256(table.to_csv(index=False, lineterminator=line_end).encode("utf-8")).hexdigest()


def target_schedule_digest(fixtures: pd.DataFrame, gw: int) -> str:
    """What the forecast depends on in the target Gameweek's schedule: its fixtures and clubs.

    LF line endings make the digest identical on every platform.
    """
    return _schedule_digest(fixtures, gw, "\n")


def published_forecast(gw: int, model_sha256: str | None, fixtures: pd.DataFrame,
                       history_cutoff: int | None = None) -> Path | None:
    """The served artifact if it already forecasts `gw` with this model, schedule and history."""
    try:
        manifest = load_current_manifest(CURRENT_DIR / "manifest.json")
    except ValueError:
        return None
    provenance = manifest.model_provenance or {}
    # GW6 v12 was published on Windows, where the digest used CRLF line endings.
    schedules = {target_schedule_digest(fixtures, gw), _schedule_digest(fixtures, gw, "\r\n")}
    # Forecasts published before stages existed used all earlier Gameweeks.
    served_cutoff = provenance.get("history_cutoff_gw", gw - 1)
    cutoff = gw - 1 if history_cutoff is None else history_cutoff
    if (manifest.prediction_event == gw and provenance.get("model_sha256") == model_sha256
            and provenance.get("target_schedule_sha256") in schedules and served_cutoff == cutoff):
        return manifest.prediction_path
    return None


def served_identical(content: bytes) -> Path | None:
    """The served artifact if it already has exactly these bytes."""
    try:
        manifest = load_current_manifest(CURRENT_DIR / "manifest.json")
    except ValueError:
        return None
    path = manifest.prediction_path
    return path if path.is_file() and path.read_bytes() == content else None


def main(force: bool = False) -> Path:
    """Publish the next forecast once per Gameweek (again only if its fixtures change).

    Prices and ownership move daily; the API reapplies current prices and
    availability, so they alone never cause a new artifact.
    """
    model, provenance = load_prediction_model()
    gameweeks = pd.read_csv(GAMEWEEKS_PATH)
    gw, season, cutoff, stage = target_gameweek(gameweeks)
    season_dir = HISTORY_DIR / season
    history_path, fixtures_path = season_dir / "merged_gw.csv", season_dir / "fixtures.csv"
    if history_path.is_file():
        history = pd.read_csv(history_path)
    elif cutoff == 0:
        history = pd.DataFrame(columns=["element", "fixture", "GW", "value", "position", "was_home",
                                        "opponent_team", "minutes", "total_points"])
    else:
        raise HistoryIncompleteError(f"Fetch {season} history before forecasting GW{gw}")
    players, teams = pd.read_csv(PLAYERS_PATH), pd.read_csv(TEAMS_PATH)
    fixtures = pd.read_csv(fixtures_path)
    schedule = target_schedule_digest(fixtures, gw)
    existing = None if force else published_forecast(gw, provenance.get("model_sha256"), fixtures, cutoff)
    if existing is not None:
        print(f"GW{gw}: already published as {existing.name}")
        return existing
    result = generate_predictions(players, teams, fixtures, history, gw, model, history_cutoff=cutoff)
    result["prediction_season"] = season
    inputs = [path for path in (PLAYERS_PATH, TEAMS_PATH, GAMEWEEKS_PATH, history_path, fixtures_path)
              if path.is_file()]
    provenance["prediction_season"] = season
    provenance["target_schedule_sha256"] = schedule
    provenance["forecast_stage"] = stage
    provenance["history_cutoff_gw"] = cutoff
    provenance["input_sha256"] = _digest(inputs)
    provenance["input_files"] = {path.name if path.parent == CURRENT_DIR else f"{season}/{path.name}":
                                 hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    sources = [Path(__file__), PROJECT_ROOT / "engine" / "feature_contract.py",
               PROJECT_ROOT / "historical_data" / "build_features.py",
               PROJECT_ROOT / "historical_data" / "forecast.py", CURRENT_DIR / "xmins.py"]
    # Content-address the actual generator sources, including local changes.
    provenance["code_revision"] = "sha256:" + _digest([path for path in sources if path.is_file()])
    content = result.to_csv(index=False, lineterminator="\n").encode("utf-8")
    unchanged = served_identical(content)
    if unchanged is not None:
        print(f"GW{gw}: already served with identical content as {unchanged.name}")
        return unchanged
    output_path = artifact_path(CURRENT_DIR, gw, content)
    manifest = publish_prediction_artifact(
        output_path, content, season=season, prediction_event=gw,
        player_count=len(result), model_provenance=provenance)
    print(f"GW{gw} ({stage}, history to GW{cutoff}): {len(result)} players published to "
          f"{output_path.name}; manifest: {manifest}")
    return output_path


if __name__ == "__main__":
    main(force="--force" in sys.argv[1:])
