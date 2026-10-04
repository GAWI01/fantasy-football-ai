from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import os

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .api_contract import api_envelope, source_meta
from .api_models import (
    DashboardEnvelopeModel,
    FixtureEnvelopeModel,
    FixtureMatrixEnvelopeModel,
    PlanEnvelopeModel,
    PlayerEnvelopeModel,
    ReviewEnvelopeModel,
    StatusEnvelopeModel,
)
from .data_loader import (
    DataLoaderError,
    load_fixtures as load_current_fixtures,
    load_players,
    load_teams as load_current_teams,
)
from .data_manifest import load_current_manifest, model_validation_state, season_for_date
from .runtime_artifacts import validate_runtime_artifacts
from .dashboard_service import DashboardDependencies, build_dashboard
from .fpl_gateway import (
    FplGatewayError,
    begin_gateway_trace,
    default_gateway,
    end_gateway_trace,
)
from .team_service import TeamServiceError, fetch_public_team
from .fixture_service import (
    FixtureServiceError,
    get_fixture_matrix,
    get_team_fixtures,
    get_upcoming_team_fixtures,
)
from .overview_service import build_top_players
from .observability import request_logging_middleware
from .settings import parse_cors_origins
from .live_service import (
    LiveDataServiceError,
    get_bootstrap_data,
    get_event_live,
    get_event_fixtures,
    get_event_picks,
    get_live_players,
    get_manager_chip_state,
    get_manager_transfers,
    get_manager_transfer_state,
    get_team_history,
    latest_finished_event,
    normalize_manager_chip_state,
)
from .planning_service import build_fixture_scaled_horizon, gameweek_flags
from .planning_state import build_planning_state
from .review_service import (
    ReviewDataError,
    build_post_gameweek_review,
    select_review_prediction_file,
)

from decision_engine import build_decision


app = FastAPI(
    title="FPL-AI API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(os.getenv("FPL_AI_CORS_ORIGINS")),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(request_logging_middleware)

BASE_DIR = Path(__file__).resolve().parent.parent
PREDICTIONS_DIR = BASE_DIR / "historical_data" / "current_data"


def _gateway_source_meta(source: str, trace: list) -> dict:
    if not trace:
        return source_meta(source, datetime.now(timezone.utc))
    return source_meta(
        source,
        min(result.fetched_at for result in trace),
        stale=any(result.stale for result in trace),
    )


@app.get("/health")
def health():
    return {"status": "ok"}


def _validate_prediction_target(manifest, bootstrap: dict) -> None:
    """Reject forecasts for another Gameweek/season before enriching or optimizing."""
    events = bootstrap.get("events") or []
    target = next((event for event in events if event.get("is_next")), None)
    target = target or next((event for event in events if event.get("is_current")), None)
    if not target or not isinstance(target.get("id"), int):
        raise DataLoaderError("Official target Gameweek is unknown")
    if manifest.prediction_event != target["id"]:
        raise DataLoaderError(
            f"Prediction GW{manifest.prediction_event} does not match official target GW{target['id']}"
        )
    opening = next((event for event in events if event.get("id") == 1), None)
    if opening and opening.get("deadline_time"):
        try:
            deadline = datetime.fromisoformat(opening["deadline_time"].replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise DataLoaderError("Official season deadline is invalid") from exc
        expected_season = season_for_date(deadline)
        if manifest.season != expected_season:
            raise DataLoaderError(
                f"Prediction season {manifest.season} does not match official season {expected_season}"
            )


def _model_validation_state(manifest) -> str:
    return model_validation_state(manifest)


def _apply_official_player_state(predictions: pd.DataFrame, bootstrap: dict) -> pd.DataFrame:
    """Availability is runtime official state, not an assumption in an older CSV."""
    official = {int(player["id"]): player for player in bootstrap.get("elements") or []}
    if not official:
        raise DataLoaderError("Official player data is unavailable")
    teams = {int(team["id"]): team for team in bootstrap.get("teams") or []}
    # A player the official game no longer lists cannot be selected; drop the
    # row instead of failing every prediction consumer for one stale entry.
    result = predictions[predictions["player_id"].astype(int).isin(official)].copy()
    # Artifacts from the v12 generator store the model's output if available;
    # the latest official availability is applied here on every request.
    if_available = {"ml_prediction", "xmins_available", "start_probability_available"}.issubset(result.columns)
    for index, row in result.iterrows():
        player = official[int(row["player_id"])]
        result.at[index, "name"] = str(player.get("web_name") or player.get("second_name") or f"Player {player['id']}")
        if player.get("now_cost") is not None:
            result.at[index, "price"] = float(player["now_cost"]) / 10
        if player.get("element_type") in {1, 2, 3, 4}:
            result.at[index, "position"] = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}[player["element_type"]]
        club = teams.get(player.get("team"), {})
        if club.get("name"):
            result.at[index, "team"] = club["name"]
        status = player.get("status")
        chance = player.get("chance_of_playing_next_round")
        unavailable = status in {"s", "u", "n"} or chance == 0 or (status == "i" and chance is None)
        if if_available:
            multiplier = 0.0 if unavailable else min(1.0, max(0.0, float(chance) / 100)) if chance is not None else 1.0
            result.at[index, "availability_multiplier"] = multiplier
            result.at[index, "predicted_points"] = float(row["ml_prediction"]) * multiplier
            result.at[index, "xmins"] = float(row["xmins_available"]) * multiplier
            result.at[index, "start_probability"] = float(row["start_probability_available"]) * multiplier
        if unavailable:
            result.at[index, "availability"] = "UNAVAILABLE"
            result.at[index, "predicted_points"] = 0.0
            result.at[index, "xmins"] = 0.0
            result.at[index, "start_probability"] = 0.0
        elif status == "a" and chance in (None, 100):
            result.at[index, "availability"] = "AVAILABLE"
        else:
            result.at[index, "availability"] = "RISK"
        # Legacy artifacts only: the validated v12 model scores low-minute
        # players itself, so its output is not overridden by a minutes rule.
        if not if_available and row.get("xmins") is not None and pd.notna(row.get("xmins")) and float(row["xmins"]) <= 0:
            result.at[index, "predicted_points"] = 0.0
            result.at[index, "start_probability"] = 0.0
        result.at[index, "status"] = status
        result.at[index, "chance_of_playing_next_round"] = chance
        if "price" in result.columns and pd.notna(result.at[index, "price"]):
            price = float(result.at[index, "price"])
            result.at[index, "value"] = float(result.at[index, "predicted_points"]) / price if price > 0 else 0.0
    return result


def _live_event_expectations(event: int) -> dict[int, float] | None:
    """Pre-deadline forecasts for the Gameweek being played, if that is the served artifact.

    While a Gameweek is live the next forecast is not published yet, so the
    manifest still names the live Gameweek's artifact. Any other event (or any
    unreadable artifact) gives no expectation rather than a mismatched one.
    """
    try:
        manifest = load_current_manifest(PREDICTIONS_DIR / "manifest.json")
        if manifest.prediction_event != event:
            return None
        predictions = _apply_official_player_state(load_predictions(), get_bootstrap_data())
    except Exception:  # Optional context: live points must never fail because of it.
        return None
    return {int(row.player_id): float(row.predicted_points) for row in predictions.itertuples(index=False)}


@app.get("/api/v1/status", response_model=StatusEnvelopeModel)
def get_status_v1():
    errors: list[dict[str, str]] = []
    data: dict = {
        "official": None,
        "model": None,
        "service_state": "unavailable",
        "artifacts": {"loaded": False, "files": []},
    }
    meta: dict = {}
    target_event = None

    try:
        official_result = default_gateway.get_json(
            "bootstrap-static/",
            ttl_seconds=300,
        )
        bootstrap = official_result.data
        events = bootstrap.get("events") or []
        current = next((event for event in events if event.get("is_current")), None)
        upcoming = next((event for event in events if event.get("is_next")), None)
        target = upcoming or current
        target_event = target.get("id") if target else None
        data["official"] = {
            "current_event": current.get("id") if current else None,
            "next_event": upcoming.get("id") if upcoming else None,
            "player_count": len(bootstrap.get("elements") or []),
            "team_count": len(bootstrap.get("teams") or []),
        }
        meta["official"] = source_meta(
            "official",
            official_result.fetched_at,
            stale=official_result.stale,
        )
        if official_result.stale:
            errors.append({"area": "official", "message": "Official data is cached/stale"})
    except (FplGatewayError, AttributeError, TypeError) as exc:
        errors.append({"area": "official", "message": str(exc)})

    try:
        manifest = load_current_manifest(PREDICTIONS_DIR / "manifest.json")
        data["model"] = {
            "season": manifest.season,
            "prediction_event": manifest.prediction_event,
            "prediction_file": manifest.prediction_file,
            "player_count": manifest.player_count,
            "schema_version": manifest.schema_version,
            "generated_at": manifest.generated_at.isoformat(),
            "target_event": target_event,
            "matches_target_event": (
                manifest.prediction_event == target_event if target_event is not None else None
            ),
            "validation_state": _model_validation_state(manifest),
        }
        meta["model"] = source_meta(
            "model",
            manifest.generated_at,
            version=manifest.prediction_file,
        )
        if target_event is None:
            errors.append({"area": "model", "message": "Official target Gameweek is unknown"})
        elif manifest.prediction_event != target_event:
            errors.append({
                "area": "model",
                "message": f"Prediction GW{manifest.prediction_event} does not match official target GW{target_event}",
            })
        if data["official"] is not None:
            try:
                _validate_prediction_target(manifest, bootstrap)
            except DataLoaderError as exc:
                if not any(error["message"] == str(exc) for error in errors):
                    errors.append({"area": "model", "message": str(exc)})
        if _model_validation_state(manifest) != "validated":
            errors.append({"area": "model", "message": "Model provenance and production validation are unverified"})
    except ValueError as exc:
        errors.append({"area": "model", "message": str(exc)})

    try:
        data["artifacts"] = validate_runtime_artifacts(PREDICTIONS_DIR)
    except ValueError as exc:
        errors.append({"area": "artifacts", "message": str(exc)})

    if data["official"] is not None and data["model"] is not None:
        data["service_state"] = "ready" if not errors else "degraded"
    elif data["official"] is not None or data["model"] is not None:
        data["service_state"] = "degraded"

    return api_envelope(data, meta, errors)


def _get_prediction_event(
    current_event: int,
    next_event: int | None,
) -> int:
    if next_event is not None:
        return next_event

    return current_event


def _select_prediction_file(
    predictions_dir: Path,
    current_event: int,
) -> Path:
    manifest = load_current_manifest(predictions_dir / "manifest.json")
    if manifest.prediction_event != current_event:
        raise ValueError(f"No prediction file found for GW{current_event}")
    return manifest.prediction_path


def _load_predictions(
    current_event: int,
) -> tuple[pd.DataFrame, str]:
    path = _select_prediction_file(
        PREDICTIONS_DIR,
        current_event,
    )

    filename = path.name
    df = pd.read_csv(path)

    required = {"player_id", "predicted_points"}
    missing = required - set(df.columns)

    if missing:
        raise DataLoaderError(
            f"{filename} is missing required columns: "
            + ", ".join(sorted(missing))
        )

    df["player_id"] = pd.to_numeric(
        df["player_id"],
        errors="coerce",
    )

    df["predicted_points"] = pd.to_numeric(
        df["predicted_points"],
        errors="coerce",
    )

    df = df.dropna(
        subset=["player_id", "predicted_points"]
    ).copy()

    return df, filename


def _load_review_predictions(
    event: int,
    deadline_time: str | None = None,
) -> tuple[pd.DataFrame, str]:
    path = select_review_prediction_file(
        PREDICTIONS_DIR,
        event,
        deadline_time=deadline_time,
    )
    try:
        return pd.read_csv(path), path.name
    except (OSError, pd.errors.ParserError) as exc:
        raise ReviewDataError(
            f"Could not read prediction artifact for GW{event}: {exc}"
        ) from exc


def _prediction_by_id(
    df: pd.DataFrame,
) -> dict[int, dict]:
    result = {}

    for _, row in df.iterrows():
        player_id = int(row["player_id"])

        result[player_id] = {
            "predicted_points": float(
                row["predicted_points"]
            ),
        }

        for column in (
            "opponent",
            "home",
            "difficulty",
            "xmins",
            "start_probability",
            "availability",
            "rotation_risk",
            "ml_prediction",
            "xP",
            "value",
        ):
            if column in df.columns:
                value = row[column]

                if pd.isna(value):
                    value = None
                elif hasattr(value, "item"):
                    value = value.item()

                result[player_id][column] = value

    return result



@app.get("/live/players")
def get_live_player_rankings(
    limit: int = 20,
    position: str | None = None,
):
    try:
        return get_live_players(limit=limit, position=position)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LiveDataServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/team/{team_id}/history")
def get_team_history_endpoint(team_id: int):
    try:
        return get_team_history(team_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LiveDataServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/fixtures/team/{team_id}/upcoming")
def get_upcoming_fixtures(
    team_id: int,
    limit: int = 10,
):
    try:
        return get_upcoming_team_fixtures(team_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FixtureServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

@app.get("/fixtures/team/{team_id}")
def get_fixtures(
    team_id: int,
    limit: int = 5,
):
    try:
        return get_team_fixtures(
            team_id,
            limit=limit,
        )
    except FixtureServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc



@app.get("/team/{team_id}/live")
def get_live_team(team_id: int):
    try:
        team = get_team_data(team_id)
        live = get_live_players(limit=700)
        event_fixtures = get_event_fixtures(int(live["current_event"]))
        by_id = {int(p["player_id"]): p for p in live["players"]}
        picks = []
        for pick in team.get("picks", []):
            player_id = int(pick["player_id"])
            live_player = by_id.get(player_id, {})
            event_points = int(live_player.get("event_points", 0) or 0)
            raw_multiplier = pick.get("multiplier")
            multiplier = 1 if raw_multiplier is None else int(raw_multiplier)
            picks.append({
                **pick,
                "multiplier": multiplier,
                "team_id": live_player.get("team_id"),
                "name": pick.get("name") or live_player.get("name") or f"Player {player_id}",
                "team_short": pick.get("team_short") or live_player.get("team_short") or "—",
                "event_points": event_points,
                "multiplied_points": event_points * multiplier,
                "live_minutes": int(live_player.get("minutes", 0) or 0),
                "live_bps": int(live_player.get("bps", 0) or 0),
                "goals": int(live_player.get("goals", 0) or 0),
                "assists": int(live_player.get("assists", 0) or 0),
                "bonus": int(live_player.get("bonus", 0) or 0),
                "saves": int(live_player.get("saves", 0) or 0),
                "penalties_saved": int(live_player.get("penalties_saved", 0) or 0),
                "penalties_missed": int(live_player.get("penalties_missed", 0) or 0),
                "yellow_cards": int(live_player.get("yellow_cards", 0) or 0),
                "red_cards": int(live_player.get("red_cards", 0) or 0),
                "own_goals": int(live_player.get("own_goals", 0) or 0),
            })
        expected = _live_event_expectations(int(live["current_event"]))
        if expected is not None:
            for pick in picks:
                pick["expected_points"] = expected.get(int(pick["player_id"]))
        owned_team_ids = {
            int(pick["team_id"])
            for pick in picks
            if pick.get("team_id") is not None
        }
        relevant_fixtures = [
            fixture
            for fixture in event_fixtures.get("fixtures", [])
            if fixture.get("home_team_id") in owned_team_ids
            or fixture.get("away_team_id") in owned_team_ids
        ]
        fixtures_by_team: dict[int, list[dict]] = {}
        for fixture in relevant_fixtures:
            for club_id in (fixture.get("home_team_id"), fixture.get("away_team_id")):
                if club_id is not None:
                    fixtures_by_team.setdefault(int(club_id), []).append(fixture)
        active_picks = [
            pick for pick in picks if int(pick.get("multiplier", 0) or 0) > 0
        ]
        players_finished = 0
        players_live = 0
        players_remaining = 0
        players_without_fixture = 0
        for pick in active_picks:
            club_id = pick.get("team_id")
            matches = fixtures_by_team.get(int(club_id), []) if club_id is not None else []
            if not matches:
                players_without_fixture += 1
            elif all(fixture.get("finished") for fixture in matches):
                players_finished += 1
            elif any(fixture.get("started") and not fixture.get("finished") for fixture in matches):
                players_live += 1
            else:
                players_remaining += 1
        summary = {
            "live_points": sum(int(pick["multiplied_points"]) for pick in active_picks),
            "captain_contribution": sum(
                int(pick["multiplied_points"])
                for pick in active_picks
                if int(pick.get("multiplier", 0) or 0) > 1
            ),
            "players_finished": players_finished,
            "players_live": players_live,
            "players_remaining": players_remaining,
            "players_without_fixture": players_without_fixture,
        }
        event_fields = (
            ("goals", "GOAL"),
            ("assists", "ASSIST"),
            ("penalties_saved", "PENALTY_SAVE"),
            ("saves", "SAVE"),
            ("bonus", "BONUS"),
            ("yellow_cards", "YELLOW_CARD"),
            ("red_cards", "RED_CARD"),
            ("own_goals", "OWN_GOAL"),
            ("penalties_missed", "PENALTY_MISS"),
        )
        events = []
        for pick in picks:
            for field, event_type in event_fields:
                count = int(pick.get(field, 0) or 0)
                if count <= 0:
                    continue
                events.append({
                    "player_id": int(pick["player_id"]),
                    "player_name": pick["name"],
                    "team_short": pick["team_short"],
                    "event_type": event_type,
                    "count": count,
                    "active": int(pick.get("multiplier", 0) or 0) > 0,
                    "provisional": event_type == "BONUS" and live["status"] == "LIVE",
                })
        return {
            "team_id": team_id,
            "name": team.get("name"),
            "current_event": live["current_event"],
            "gameweek_name": live["gameweek_name"],
            "status": live["status"],
            "finished": bool(live.get("finished")),
            "next_event": live.get("next_event"),
            "next_deadline_time": live.get("next_deadline_time"),
            "picks": picks,
            "summary": summary,
            "fixtures": relevant_fixtures,
            "events": events,
        }
    except (TeamServiceError, LiveDataServiceError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

def get_official_team(team_id: int) -> dict:
    """Return a display-ready public team using only official FPL sources."""
    team = fetch_public_team(team_id)
    bootstrap = get_bootstrap_data()
    elements = bootstrap.get("elements") or []
    teams = bootstrap.get("teams") or []
    if not isinstance(elements, list) or not isinstance(teams, list):
        raise LiveDataServiceError("FPL bootstrap player data is invalid")
    player_by_id = {
        int(player["id"]): player
        for player in elements
        if isinstance(player, dict) and player.get("id") is not None
    }
    team_by_id = {
        int(item["id"]): item
        for item in teams
        if isinstance(item, dict) and item.get("id") is not None
    }
    position_names = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
    picks = []
    for pick in team.get("picks") or []:
        player_id = int(pick["player_id"])
        player = player_by_id.get(player_id)
        if player is None:
            raise LiveDataServiceError(
                f"Player {player_id} was not found in official FPL data"
            )
        club = team_by_id.get(int(player.get("team", 0) or 0), {})
        now_cost = player.get("now_cost")
        picks.append(
            {
                **pick,
                "name": str(player.get("web_name") or player.get("second_name") or f"Player {player_id}"),
                "position_name": position_names.get(int(player.get("element_type", 0) or 0), "UNK"),
                "team": str(club.get("name") or "Unknown"),
                "team_short": str(club.get("short_name") or "UNK"),
                "price": float(now_cost) / 10 if now_cost is not None else None,
                "form": float(player["form"]) if player.get("form") not in (None, "") else None,
                "ownership": float(player["selected_by_percent"]) if player.get("selected_by_percent") not in (None, "") else None,
                "season_points": int(player["total_points"]) if player.get("total_points") is not None else None,
                "starts": int(player["starts"]) if player.get("starts") is not None else None,
                "season_goals": int(player["goals_scored"]) if player.get("goals_scored") is not None else None,
                "season_assists": int(player["assists"]) if player.get("assists") is not None else None,
                "season_bonus": int(player["bonus"]) if player.get("bonus") is not None else None,
                "expected_goals": float(player["expected_goals"]) if player.get("expected_goals") not in (None, "") else None,
                "expected_assists": float(player["expected_assists"]) if player.get("expected_assists") not in (None, "") else None,
                "ict_index": float(player["ict_index"]) if player.get("ict_index") not in (None, "") else None,
                "status": str(player.get("status") or "u"),
                "chance_of_playing_next_round": player.get("chance_of_playing_next_round"),
                "news": str(player.get("news") or ""),
                "news_added": player.get("news_added"),
            }
        )
    return {**team, "picks": picks}


@app.get("/team/{team_id}")
def get_team(team_id: int):
    try:
        team = get_official_team(team_id)

        fixture_data = get_team_fixtures(
            team_id,
            limit=1,
        )

        current_event = fixture_data.get(
            "current_event"
        )

        next_event = fixture_data.get(
            "next_event"
        )

        if (
            not isinstance(current_event, int)
            or current_event <= 0
        ):
            raise DataLoaderError(
                "Could not determine current gameweek"
            )

        if (
            next_event is not None
            and (
                not isinstance(next_event, int)
                or next_event <= 0
            )
        ):
            next_event = None

        prediction_event = _get_prediction_event(
            current_event,
            next_event,
        )

        predictions, prediction_file = _load_predictions(
            prediction_event
        )

        manifest = load_current_manifest(PREDICTIONS_DIR / "manifest.json")
        bootstrap = get_bootstrap_data()
        _validate_prediction_target(manifest, bootstrap)
        predictions = _apply_official_player_state(predictions, bootstrap)

        prediction_by_id = _prediction_by_id(
            predictions
        )

        enriched_picks = []

        for pick in team["picks"]:
            player_id = int(
                pick["player_id"]
            )

            enriched_picks.append(
                {
                    **pick,
                    "prediction": prediction_by_id.get(
                        player_id
                    ),
                }
            )

        return {
            **team,
            "prediction_event": prediction_event,
            "prediction_file": prediction_file,
            "model_validation_state": _model_validation_state(manifest),
            "picks": enriched_picks,
        }

    except HTTPException:
        raise

    except TeamServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except FixtureServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except DataLoaderError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    except (
        TypeError,
        KeyError,
    ) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not build team data: {exc}",
        ) from exc


@app.get("/players/top")
def get_top_players(
    limit: int = 5,
    position: str | None = None,
):
    if limit < 1 or limit > 50:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 50",
        )

    try:
        players = load_players()

        fixture_data = get_team_fixtures(
            1,
            limit=1,
        )

        current_event = fixture_data.get(
            "current_event"
        )

        next_event = fixture_data.get(
            "next_event"
        )

        if (
            not isinstance(current_event, int)
            or current_event <= 0
        ):
            raise DataLoaderError(
                "Could not determine current gameweek"
            )

        if (
            next_event is not None
            and (
                not isinstance(next_event, int)
                or next_event <= 0
            )
        ):
            next_event = None

        prediction_event = _get_prediction_event(
            current_event,
            next_event,
        )

        predictions, prediction_file = _load_predictions(
            prediction_event
        )

        manifest = load_current_manifest(PREDICTIONS_DIR / "manifest.json")
        bootstrap = get_bootstrap_data()
        _validate_prediction_target(manifest, bootstrap)
        predictions = _apply_official_player_state(predictions, bootstrap)
        players = pd.DataFrame(bootstrap.get("elements") or []).rename(columns={"id": "player_id"})

        teams = pd.DataFrame(bootstrap.get("teams") or [])

        return {
            "prediction_event": prediction_event,
            "prediction_file": prediction_file,
            "model_validation_state": _model_validation_state(manifest),
            "players": build_top_players(
                predictions,
                players,
                teams,
                limit=limit,
                position=position,
            ),
        }

    except DataLoaderError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    except FixtureServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    except (
        OSError,
        pd.errors.ParserError,
        TypeError,
    ) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not build player rankings: {exc}",
        ) from exc

def get_team_data(team_id: int) -> dict:
    """Compatibility wrapper for the decision endpoint and future API layers."""
    return fetch_public_team(team_id)


def load_predictions() -> pd.DataFrame:
    """Load the one production artifact selected by the validated manifest."""
    try:
        manifest = load_current_manifest(PREDICTIONS_DIR / "manifest.json")
    except ValueError as exc:
        raise DataLoaderError(str(exc)) from exc
    df = pd.read_csv(manifest.prediction_path)
    required = {
        "player_id", "name", "position", "team",
        "price", "predicted_points",
    }
    missing = required - set(df.columns)
    if missing:
        raise DataLoaderError(
            "Prediction file is missing required columns: "
            + ", ".join(sorted(missing))
        )
    return df


@app.get("/api/decision/{team_id}")
def get_decision(
    team_id: int,
    budget: float = 100.0,
    free_transfers: int | None = None,
    max_transfers: int | None = None,
):
    """Return the unified standard-mode FPL decision result."""
    if budget <= 0:
        raise HTTPException(
            status_code=400,
            detail="budget must be greater than 0",
        )
    if free_transfers is not None and not 0 <= free_transfers <= 5:
        raise HTTPException(
            status_code=400,
            detail="free_transfers must be between 0 and 5",
        )
    if max_transfers is not None and max_transfers < 0:
        raise HTTPException(
            status_code=400,
            detail="max_transfers cannot be negative",
        )

    try:
        team = get_team_data(team_id)
        predictions = load_predictions()
        manifest = load_current_manifest(PREDICTIONS_DIR / "manifest.json")
        bootstrap = get_bootstrap_data()
        try:
            _validate_prediction_target(manifest, bootstrap)
        except DataLoaderError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        predictions = _apply_official_player_state(predictions, bootstrap)
        fixtures = load_current_fixtures()
        teams = load_current_teams()
        try:
            transfer_state = get_manager_transfer_state(
                team_id,
                manifest.prediction_event,
                int(team.get("started_event") or 1),
            )
        except LiveDataServiceError:
            transfer_state = {"known": False, "free_transfers": 0}
        effective_free_transfers = (
            free_transfers
            if free_transfers is not None
            else int(transfer_state["free_transfers"])
        )
        effective_max_transfers = (
            max_transfers
            if max_transfers is not None
            else min(5, max(1, effective_free_transfers))
        )
        effective_horizon = min(5, 39 - manifest.prediction_event)
        horizon_predictions = build_fixture_scaled_horizon(
            predictions,
            fixtures,
            teams,
            prediction_event=manifest.prediction_event,
            horizon=effective_horizon,
        )
        try:
            chip_state = get_manager_chip_state(
                team_id,
                manifest.prediction_event,
                started_event=team.get("started_event"),
            )
        except LiveDataServiceError:
            chip_state = normalize_manager_chip_state(
                manifest.prediction_event,
                {},
                started_event=team.get("started_event"),
            )
        chip_state.update(
            gameweek_flags(fixtures, teams, manifest.prediction_event)
        )
        chip_state["free_transfers"] = effective_free_transfers
        chip_state["free_transfers_known"] = bool(transfer_state["known"])

        decision = build_decision(
            team,
            predictions,
            budget=budget,
            free_transfers=effective_free_transfers,
            max_transfers=effective_max_transfers,
            horizon_predictions=horizon_predictions,
            horizon=effective_horizon,
            chip_state=chip_state,
        )
        # Public FPL data cannot see every transfer rule, so tell clients
        # whether the count came from the user or was derived.
        decision["transfers"]["free_transfers_source"] = (
            "user"
            if free_transfers is not None
            else "derived" if transfer_state["known"] else "unknown"
        )
        return decision

    except HTTPException:
        raise
    except (TeamServiceError, FixtureServiceError, LiveDataServiceError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (DataLoaderError, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/dashboard/{team_id}", response_model=DashboardEnvelopeModel)
def get_dashboard_v1(team_id: int, free_transfers: int | None = None):
    if team_id <= 0:
        raise HTTPException(status_code=400, detail="team_id must be positive")
    if free_transfers is not None and not 0 <= free_transfers <= 5:
        raise HTTPException(
            status_code=400,
            detail="free_transfers must be between 0 and 5",
        )

    trace_token = begin_gateway_trace()
    dependencies = DashboardDependencies(
        team=get_official_team,
        live=get_live_team,
        history=get_team_history_endpoint,
        fixtures=lambda value: get_upcoming_fixtures(value, limit=10),
        players=lambda: get_enriched_player_rankings(limit=50),
        decision=lambda value: get_decision(value, free_transfers=free_transfers),
    )
    try:
        payload = build_dashboard(team_id, dependencies)
        try:
            manifest = load_current_manifest(PREDICTIONS_DIR / "manifest.json")
            bootstrap = get_bootstrap_data()
            _validate_prediction_target(manifest, bootstrap)
            planning_state = build_planning_state(
                bootstrap,
                prediction_event=manifest.prediction_event,
            )
            payload["meta"].update(planning_state)
            payload["meta"]["prediction_version"] = manifest.prediction_file
            payload["meta"]["model_validation_state"] = _model_validation_state(manifest)
            if _model_validation_state(manifest) != "validated":
                payload["meta"]["degraded"] = True
                payload["errors"].append({
                    "area": "model", "message": "Model provenance and production validation are unverified",
                })
        except (DataLoaderError, LiveDataServiceError, ValueError, OSError) as exc:
            payload["meta"].update(
                {
                    "current_event": payload["meta"].get("event"),
                    "prediction_event": None,
                    "target_deadline_time": None,
                    "actions_locked": True,
                    "prediction_version": None,
                }
            )
            payload["meta"]["degraded"] = True
            payload["errors"].append(
                {"area": "planning_state", "message": f"Planning is unavailable: {exc}"}
            )
    finally:
        official_trace = end_gateway_trace(trace_token)

    if official_trace:
        official_stale = any(result.stale for result in official_trace)
        payload["meta"]["official"] = source_meta(
            "official",
            min(result.fetched_at for result in official_trace),
            stale=official_stale,
        )
        payload["meta"]["stale"] = official_stale
        if official_stale:
            payload["meta"]["degraded"] = True
            payload["errors"].append(
                {"area": "official", "message": "Showing cached official FPL data"}
            )
    return payload


@app.get("/api/v1/plan/{team_id}", response_model=PlanEnvelopeModel)
def get_plan_v1(team_id: int):
    if team_id <= 0:
        raise HTTPException(status_code=400, detail="team_id must be positive")
    manifest = load_current_manifest(PREDICTIONS_DIR / "manifest.json")
    meta = source_meta(
        "model",
        manifest.generated_at,
        version=manifest.prediction_file,
    )
    meta["event"] = manifest.prediction_event
    return api_envelope(get_decision(team_id), meta)


def get_enriched_player_rankings(
    limit: int = 20,
    position: str | None = None,
) -> dict:
    data = get_live_player_rankings(limit=limit, position=position)
    try:
        manifest = load_current_manifest(PREDICTIONS_DIR / "manifest.json")
        bootstrap = get_bootstrap_data()
        _validate_prediction_target(manifest, bootstrap)
        prediction_by_id = _prediction_by_id(_apply_official_player_state(load_predictions(), bootstrap))
        for player in data.get("players") or []:
            if not isinstance(player, dict) or player.get("player_id") is None:
                continue
            prediction = prediction_by_id.get(int(player["player_id"]))
            if prediction:
                player.update(prediction)
        data["model_version"] = manifest.prediction_file
        data["prediction_event"] = manifest.prediction_event
        data["model_validation_state"] = _model_validation_state(manifest)
    except (DataLoaderError, LiveDataServiceError, ValueError, OSError, pd.errors.ParserError) as exc:
        data["model_version"] = None
        data["prediction_event"] = None
        data["model_error"] = str(exc)
    return data


@app.get("/api/v1/players", response_model=PlayerEnvelopeModel)
def get_players_v1(limit: int = 20, position: str | None = None):
    if limit < 1 or limit > 700:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 700")
    trace_token = begin_gateway_trace()
    try:
        data = get_enriched_player_rankings(limit=limit, position=position)
    finally:
        official_trace = end_gateway_trace(trace_token)
    meta = _gateway_source_meta("live", official_trace)
    meta["model_version"] = data.get("model_version")
    errors = []
    if data.get("model_error"):
        errors.append({"area": "model", "message": data["model_error"]})
    return api_envelope(data, meta, errors)


@app.get("/api/v1/fixtures", response_model=FixtureEnvelopeModel)
def get_fixtures_v1(team_id: int, limit: int = 10):
    if team_id <= 0:
        raise HTTPException(status_code=400, detail="team_id must be positive")
    trace_token = begin_gateway_trace()
    try:
        data = get_upcoming_fixtures(team_id, limit=limit)
    finally:
        official_trace = end_gateway_trace(trace_token)
    return api_envelope(
        data,
        _gateway_source_meta("official", official_trace),
    )


@app.get("/api/v1/fixture-matrix", response_model=FixtureMatrixEnvelopeModel)
def get_fixture_matrix_v1(start_event: int | None = None, horizon: int = 5):
    if start_event is not None and not 1 <= start_event <= 38:
        raise HTTPException(
            status_code=400,
            detail="start_event must be between 1 and 38",
        )
    if not 1 <= horizon <= 8:
        raise HTTPException(status_code=400, detail="horizon must be between 1 and 8")
    trace_token = begin_gateway_trace()
    try:
        data = get_fixture_matrix(start_event=start_event, horizon=horizon)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FixtureServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        official_trace = end_gateway_trace(trace_token)
    return api_envelope(
        data,
        _gateway_source_meta("official", official_trace),
    )


@app.get("/api/v1/review/{team_id}", response_model=ReviewEnvelopeModel)
def get_review_v1(team_id: int, event: int | None = None):
    if team_id <= 0:
        raise HTTPException(status_code=400, detail="team_id must be positive")
    if event is not None and not 1 <= event <= 38:
        raise HTTPException(status_code=400, detail="event must be between 1 and 38")

    meta = source_meta("derived", datetime.now(timezone.utc))
    trace_token = begin_gateway_trace()
    try:
        bootstrap = get_bootstrap_data()
        events = bootstrap.get("events") or []
        if event is None:
            target_event = latest_finished_event(bootstrap)
        else:
            target_event = next(
                (
                    item
                    for item in events
                    if isinstance(item, dict) and int(item.get("id", 0) or 0) == event
                ),
                None,
            )
            if target_event is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Gameweek {event} was not found",
                )
        event_id = int(target_event["id"])
        meta["event"] = event_id

        if not target_event.get("finished"):
            return api_envelope(
                {
                    "available": False,
                    "team_id": team_id,
                    "event": event_id,
                    "reason": f"Gameweek {event_id} is not finished",
                },
                meta,
            )

        try:
            predictions, prediction_version = _load_review_predictions(
                event_id,
                deadline_time=target_event.get("deadline_time"),
            )
        except ReviewDataError as exc:
            return api_envelope(
                {
                    "available": False,
                    "team_id": team_id,
                    "event": event_id,
                    "reason": str(exc),
                },
                meta,
                [{"area": "model", "message": str(exc)}],
            )

        meta["version"] = prediction_version
        try:
            review = build_post_gameweek_review(
                team_id=team_id,
                event=event_id,
                picks_payload=get_event_picks(team_id, event_id),
                transfers=get_manager_transfers(team_id),
                bootstrap=bootstrap,
                live_payload=get_event_live(event_id),
                predictions=predictions,
                prediction_version=prediction_version,
            )
        except ReviewDataError as exc:
            return api_envelope(
                {
                    "available": False,
                    "team_id": team_id,
                    "event": event_id,
                    "reason": str(exc),
                },
                meta,
                [{"area": "review", "message": str(exc)}],
            )
        return api_envelope(review, meta)
    except HTTPException:
        raise
    except LiveDataServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        official_trace = end_gateway_trace(trace_token)
        if official_trace:
            official_meta = _gateway_source_meta("official", official_trace)
            meta["official"] = official_meta
            meta["stale"] = official_meta["stale"]
