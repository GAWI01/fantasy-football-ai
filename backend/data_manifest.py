from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import tempfile
import re
import csv
import io
import math


@dataclass(frozen=True)
class PredictionManifest:
    season: str
    prediction_event: int
    prediction_file: str
    prediction_path: Path
    generated_at: datetime
    player_count: int
    schema_version: int
    model_provenance: dict | None = None
    artifact_sha256: str | None = None


def season_for_date(moment: datetime) -> str:
    start_year = moment.year if moment.month >= 7 else moment.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def model_validation_state(manifest: PredictionManifest | None) -> str:
    """A label alone is insufficient to make a serving artifact validated.

    The generator verifies linked model/report bytes before publication. The
    serving loader retains legacy readability while requiring its recorded
    recipe, inputs, code and evaluation evidence for a validated status.
    """
    provenance = manifest.model_provenance if manifest is not None else None
    if not isinstance(provenance, dict):
        return "unverified"
    evaluation = provenance.get("evaluation")
    if (provenance.get("validation_state") != "validated"
            or provenance.get("feature_contract_version") != 2
            or provenance.get("xp_source") != "previous_completed_gw_points_mean_v1"
            or provenance.get("target") != "same_fixture_total_points"
            or not provenance.get("code_revision")
            or not isinstance(evaluation, dict)
            or evaluation.get("leakage_safe") is not True
            or evaluation.get("production_parity") is not True
            or not evaluation.get("report_id")):
        return "unverified"
    for digest in [provenance.get("model_sha256"), provenance.get("input_sha256"),
                   evaluation.get("report_sha256")]:
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            return "unverified"
    return "validated"


def _validate_publication_metadata(season: str, event: int, player_count: int) -> None:
    match = re.fullmatch(r"(\d{4})-(\d{2})", season)
    if not match or (int(match[1]) + 1) % 100 != int(match[2]):
        raise ValueError("season must use consecutive YYYY-YY years")
    if not 1 <= event <= 38:
        raise ValueError("prediction_event must be between 1 and 38")
    if player_count <= 0:
        raise ValueError("player_count must be positive")


def _validate_prediction_bytes(content: bytes, player_count: int) -> None:
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), strict=True)
        if not {"player_id", "predicted_points"}.issubset(reader.fieldnames or []):
            raise ValueError("Prediction CSV lacks required columns")
        seen = set()
        for row in reader:
            player_id, points = float(row["player_id"]), float(row["predicted_points"])
            if (not math.isfinite(player_id) or player_id <= 0 or player_id != int(player_id)
                    or not math.isfinite(points) or points < 0 or player_id in seen):
                raise ValueError("Prediction CSV contains invalid or duplicate player rows")
            seen.add(player_id)
        if len(seen) != player_count:
            raise ValueError("Prediction CSV row count differs from player_count")
    except (UnicodeError, csv.Error, TypeError, KeyError) as exc:
        raise ValueError(f"Prediction CSV is invalid: {exc}") from exc


def publish_prediction_manifest(
    prediction_path: Path,
    *,
    season: str,
    prediction_event: int,
    player_count: int,
    model_provenance: dict | None = None,
) -> Path:
    artifact = prediction_path.resolve()
    if not artifact.is_file():
        raise ValueError(f"prediction file does not exist: {artifact.name}")

    return publish_prediction_artifact(
        artifact, artifact.read_bytes(), season=season, prediction_event=prediction_event,
        player_count=player_count, model_provenance=model_provenance,
    )


def publish_prediction_artifact(
    prediction_path: Path,
    content: bytes,
    *,
    season: str,
    prediction_event: int,
    player_count: int,
    model_provenance: dict | None = None,
) -> Path:
    lock = prediction_path.resolve().parent / ".prediction-publication.lock"
    try:
        with lock.open("x", encoding="utf-8") as handle:
            handle.write("Prediction publication in progress\n")
    except FileExistsError as exc:
        raise ValueError("Prediction publication is already in progress") from exc
    try:
        return _publish_prediction_artifact_locked(
            prediction_path, content, season=season, prediction_event=prediction_event,
            player_count=player_count, model_provenance=model_provenance)
    finally:
        lock.unlink(missing_ok=True)


def _publish_prediction_artifact_locked(
    prediction_path: Path,
    content: bytes,
    *,
    season: str,
    prediction_event: int,
    player_count: int,
    model_provenance: dict | None = None,
) -> Path:
    """Publish immutable bytes first, then atomically switch the current pointer.

    Validate conflicts before touching any destination. Identical reruns reuse
    the certified timestamp. Failed writes restore prior bytes, including the
    serving pointer; fresh orphan artifacts are removed.
    """
    artifact = prediction_path.resolve()
    _validate_publication_metadata(season, prediction_event, player_count)
    _validate_prediction_bytes(content, player_count)
    event_name = re.match(r"gw(\d+)(?:_|\.)", artifact.name)
    if event_name and int(event_name[1]) != prediction_event:
        raise ValueError("Prediction filename differs from prediction_event")
    payload = {
        "season": season,
        "prediction_event": prediction_event,
        "prediction_file": artifact.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "player_count": player_count,
        "schema_version": 1,
        "artifact_sha256": hashlib.sha256(content).hexdigest(),
    }
    if model_provenance is not None:
        payload["model_provenance"] = model_provenance
    sidecar_path = artifact.with_suffix(artifact.suffix + ".manifest.json")
    manifest_path = artifact.parent / "manifest.json"
    metadata_bytes = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    pointer_bytes = metadata_bytes
    if sidecar_path.exists():
        try:
            metadata_bytes = sidecar_path.read_bytes()
            existing_sidecar = json.loads(metadata_bytes.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not read immutable artifact manifest: {exc}") from exc
        comparable = {key: value for key, value in payload.items() if key != "generated_at"}
        # Legacy sidecars have no digest; byte comparison still protects them.
        if (not artifact.is_file() or artifact.read_bytes() != content
                or any(existing_sidecar.get(key) != value for key, value in comparable.items()
                       if key != "artifact_sha256" or key in existing_sidecar)):
            raise ValueError(f"Artifact manifest is immutable: {sidecar_path.name}")
        # Reuse the certified sidecar bytes; keep an equivalent pointer untouched.
        pointer_bytes = metadata_bytes
        try:
            if json.loads(manifest_path.read_text(encoding="utf-8")) == existing_sidecar:
                pointer_bytes = manifest_path.read_bytes()
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
    elif artifact.exists() and artifact.read_bytes() != content:
        raise ValueError(f"Prediction artifact is immutable: {artifact.name}")
    replacements = [(artifact, content), (sidecar_path, metadata_bytes), (manifest_path, pointer_bytes)]
    originals = {path: path.read_bytes() if path.exists() else None for path, _ in replacements}
    staged, changed = [], []
    try:
        for path, data in replacements:
            if originals[path] == data:
                continue
            with tempfile.NamedTemporaryFile(dir=artifact.parent, prefix=f".{path.name}.",
                                             suffix=".tmp", delete=False) as temporary:
                temporary.write(data)
                temporary.flush()
                staged.append((Path(temporary.name), path))
        for temporary, path in staged:
            temporary.replace(path)
            changed.append(path)
        load_current_manifest(manifest_path)
    except Exception:
        for path in reversed(changed):
            previous = originals[path]
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(previous)
        raise
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
    return manifest_path


def load_current_manifest(path: Path) -> PredictionManifest:
    manifest_path = path.resolve()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read prediction manifest: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("prediction manifest must be a JSON object")

    try:
        season = str(payload["season"]).strip()
        prediction_event = int(payload["prediction_event"])
        prediction_file = str(payload["prediction_file"]).strip()
        generated_at = datetime.fromisoformat(str(payload["generated_at"]))
        player_count = int(payload["player_count"])
        schema_version = int(payload["schema_version"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"prediction manifest has invalid fields: {exc}") from exc

    _validate_publication_metadata(season, prediction_event, player_count)
    if not prediction_file:
        raise ValueError("prediction_file cannot be empty")
    if generated_at.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    if player_count <= 0:
        raise ValueError("player_count must be positive")
    if schema_version != 1:
        raise ValueError("schema_version must be 1")

    artifact = (manifest_path.parent / prediction_file).resolve()
    try:
        artifact.relative_to(manifest_path.parent)
    except ValueError as exc:
        raise ValueError("prediction file must stay inside manifest directory") from exc

    if not artifact.is_file():
        raise ValueError(f"prediction file does not exist: {prediction_file}")
    artifact_sha256 = payload.get("artifact_sha256")
    if artifact_sha256 is not None and artifact_sha256 != hashlib.sha256(artifact.read_bytes()).hexdigest():
        raise ValueError("Prediction artifact digest does not match its manifest")
    model_provenance = payload.get("model_provenance")
    if model_provenance is not None and not isinstance(model_provenance, dict):
        raise ValueError("model_provenance must be a JSON object")

    return PredictionManifest(
        season=season,
        prediction_event=prediction_event,
        prediction_file=prediction_file,
        prediction_path=artifact,
        generated_at=generated_at,
        player_count=player_count,
        schema_version=schema_version,
        model_provenance=model_provenance,
        artifact_sha256=artifact_sha256,
    )
