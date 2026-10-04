from pathlib import Path
import json

import pandas as pd
import pytest

from backend.review_service import (
    ReviewDataError,
    build_post_gameweek_review,
    select_review_prediction_file,
)


def _bootstrap():
    return {
        "elements": [
            {"id": 1, "web_name": "Alpha", "team": 1, "element_type": 3},
            {"id": 2, "web_name": "Beta", "team": 2, "element_type": 4},
            {"id": 3, "web_name": "Gamma", "team": 1, "element_type": 2},
            {"id": 4, "web_name": "Delta", "team": 2, "element_type": 3},
        ],
        "teams": [
            {"id": 1, "name": "North FC", "short_name": "NOR"},
            {"id": 2, "name": "South FC", "short_name": "SOU"},
        ],
    }


def _predictions():
    return pd.DataFrame(
        [
            {"player_id": 1, "predicted_points": 6.0, "xmins": 80.0},
            {"player_id": 2, "predicted_points": 5.0, "xmins": 90.0},
            {"player_id": 3, "predicted_points": 4.0, "xmins": 60.0},
            {"player_id": 4, "predicted_points": 7.0, "xmins": 75.0},
        ]
    )


def _picks_payload():
    return {
        "picks": [
            {
                "element": 1,
                "position": 1,
                "multiplier": 2,
                "is_captain": True,
                "is_vice_captain": False,
            },
            {
                "element": 2,
                "position": 2,
                "multiplier": 1,
                "is_captain": False,
                "is_vice_captain": True,
            },
            {
                "element": 3,
                "position": 12,
                "multiplier": 0,
                "is_captain": False,
                "is_vice_captain": False,
            },
        ],
        "entry_history": {
            "event": 2,
            "points": 20,
            "event_transfers_cost": 4,
            "points_on_bench": 8,
        },
    }


def _live_payload():
    return {
        "elements": [
            {"id": 1, "stats": {"total_points": 4, "minutes": 30}},
            {"id": 2, "stats": {"total_points": 12, "minutes": 90}},
            {"id": 3, "stats": {"total_points": 8, "minutes": 0}},
            {"id": 4, "stats": {"total_points": 2, "minutes": 90}},
        ]
    }


def test_review_projection_uses_selected_captain_before_vice_fallback():
    picks = _picks_payload()
    picks['picks'][0]['multiplier'] = 0
    picks['picks'][1]['multiplier'] = 2
    result = build_post_gameweek_review(
        team_id=123, event=2, picks_payload=picks, transfers=[],
        bootstrap=_bootstrap(), live_payload=_live_payload(),
        predictions=_predictions(), prediction_version='gw2.csv',
    )
    # Chosen captain Alpha 6x2 plus starter Beta 5, unaffected by realized DNP.
    assert result['summary']['projected_points'] == 17.0
    assert result['captain']['projected_contribution'] == 12.0
    assert result['captain']['actual_contribution'] == 0


def test_review_projection_reverses_actual_automatic_substitution():
    picks = _picks_payload()
    # Final scoring order, after Gamma entered for Alpha.
    picks['picks'][0].update(position=12, multiplier=0)
    picks['picks'][1]['multiplier'] = 2
    picks['picks'][2].update(position=1, multiplier=1)
    picks['automatic_subs'] = [{'element_out': 1, 'element_in': 3, 'event': 2}]
    result = build_post_gameweek_review(
        team_id=123, event=2, picks_payload=picks, transfers=[],
        bootstrap=_bootstrap(), live_payload=_live_payload(),
        predictions=_predictions(), prediction_version='gw2.csv',
    )
    assert result['summary']['projected_points'] == 17.0
    assert result['bench']['projected_points'] == 4.0


def test_build_review_explains_points_captain_bench_transfers_and_model_miss():
    result = build_post_gameweek_review(
        team_id=123,
        event=2,
        picks_payload=_picks_payload(),
        transfers=[{"event": 2, "element_in": 2, "element_out": 4}],
        bootstrap=_bootstrap(),
        live_payload=_live_payload(),
        predictions=_predictions(),
        prediction_version="gw2_predictions_v5.csv",
    )

    assert result["available"] is True
    assert result["team_id"] == 123
    assert result["event"] == 2
    assert result["prediction_version"] == "gw2_predictions_v5.csv"
    assert result["summary"] == {
        "projected_points": 17.0,
        "official_points": 20,
        "hit_cost": 4,
        "net_points_after_hits": 16,
        "actual_vs_projected": 3.0,
        "outcome": "IN_LINE",
    }
    assert result["captain"] == {
        "player_id": 1,
        "name": "Alpha",
        "multiplier": 2,
        "projected_points": 6.0,
        "actual_points": 4,
        "projected_contribution": 12.0,
        "actual_contribution": 8,
        "contribution_delta": -4.0,
    }
    assert result["bench"] == {
        "official_points": 8,
        "projected_points": 4.0,
        "player_count": 1,
    }
    assert result["transfers"] == [
        {
            "player_in": {"player_id": 2, "name": "Beta"},
            "player_out": {"player_id": 4, "name": "Delta"},
            "projected_delta": -2.0,
            "actual_delta": 10,
        }
    ]
    assert result["largest_model_miss"] == {
        "player_id": 1,
        "name": "Alpha",
        "predicted_points": 6.0,
        "actual_points": 4,
        "residual": -2.0,
    }
    assert result["largest_xmins_miss"] == {
        "player_id": 3,
        "name": "Gamma",
        "predicted_xmins": 60.0,
        "actual_minutes": 0,
        "residual": -60.0,
    }
    assert result["decision_quality"] == {
        "label": "QUESTIONABLE",
        "projected_decision_value": -6.0,
        "projected_transfer_value": -6.0,
        "captain_opportunity_cost": 0.0,
        "basis": "pre_deadline_projection",
    }
    assert [signal["type"] for signal in result["next_signals"]] == [
        "MINUTES_REVIEW",
        "TRANSFER_DISCIPLINE",
    ]


def test_decision_quality_is_independent_of_actual_points_outcome():
    baseline = build_post_gameweek_review(
        team_id=123,
        event=2,
        picks_payload=_picks_payload(),
        transfers=[{"event": 2, "element_in": 2, "element_out": 4}],
        bootstrap=_bootstrap(),
        live_payload=_live_payload(),
        predictions=_predictions(),
        prediction_version="gw2_predictions_v5.csv",
    )
    noisy_outcome = _live_payload()
    for player in noisy_outcome["elements"]:
        player["stats"]["total_points"] += 20
    picks = _picks_payload()
    picks["entry_history"]["points"] = 80

    changed = build_post_gameweek_review(
        team_id=123,
        event=2,
        picks_payload=picks,
        transfers=[{"event": 2, "element_in": 2, "element_out": 4}],
        bootstrap=_bootstrap(),
        live_payload=noisy_outcome,
        predictions=_predictions(),
        prediction_version="gw2_predictions_v5.csv",
    )

    assert changed["summary"]["outcome"] != baseline["summary"]["outcome"]
    assert changed["decision_quality"] == baseline["decision_quality"]


def test_review_keeps_xmins_audit_explicitly_unavailable_for_legacy_artifacts():
    legacy_predictions = _predictions().drop(columns=["xmins"])

    result = build_post_gameweek_review(
        team_id=123,
        event=2,
        picks_payload=_picks_payload(),
        transfers=[],
        bootstrap=_bootstrap(),
        live_payload=_live_payload(),
        predictions=legacy_predictions,
        prediction_version="gw2_predictions_v1.csv",
    )

    assert result["largest_xmins_miss"] is None
    assert all(signal["type"] != "MINUTES_REVIEW" for signal in result["next_signals"])


@pytest.mark.parametrize(
    ("official_points", "expected"),
    [(23, "ABOVE_EXPECTATION"), (22, "ABOVE_EXPECTATION"), (13, "IN_LINE"), (12, "BELOW_EXPECTATION")],
)
def test_review_outcome_uses_deterministic_five_point_band(official_points, expected):
    payload = _picks_payload()
    payload["entry_history"]["points"] = official_points

    result = build_post_gameweek_review(
        team_id=123,
        event=2,
        picks_payload=payload,
        transfers=[],
        bootstrap=_bootstrap(),
        live_payload=_live_payload(),
        predictions=_predictions(),
        prediction_version="gw2_predictions_v5.csv",
    )

    assert result["summary"]["outcome"] == expected


def test_review_rejects_missing_prediction_coverage_for_a_selected_player():
    predictions = _predictions().query("player_id != 3")

    with pytest.raises(ReviewDataError, match="missing predictions for selected players: 3"):
        build_post_gameweek_review(
            team_id=123,
            event=2,
            picks_payload=_picks_payload(),
            transfers=[],
            bootstrap=_bootstrap(),
            live_payload=_live_payload(),
            predictions=predictions,
            prediction_version="gw2_predictions_v5.csv",
        )


def test_review_rejects_duplicate_prediction_ids():
    predictions = pd.concat([_predictions(), _predictions().iloc[[0]]], ignore_index=True)

    with pytest.raises(ReviewDataError, match="duplicate player_id values"):
        build_post_gameweek_review(
            team_id=123,
            event=2,
            picks_payload=_picks_payload(),
            transfers=[],
            bootstrap=_bootstrap(),
            live_payload=_live_payload(),
            predictions=predictions,
            prediction_version="gw2_predictions_v5.csv",
        )


def _certify(path: Path, *, event: int, generated_at: str):
    sidecar = path.with_suffix(path.suffix + ".manifest.json")
    sidecar.write_text(json.dumps({
        "prediction_event": event,
        "prediction_file": path.name,
        "generated_at": generated_at,
        "schema_version": 1,
    }), encoding="utf-8")


def test_select_review_prediction_file_prefers_latest_certified_pre_deadline_version(tmp_path: Path):
    (tmp_path / "gw2_predictions.csv").write_text("base", encoding="utf-8")
    previous = tmp_path / "gw2_predictions_v4.csv"
    previous.write_text("v4", encoding="utf-8")
    _certify(previous, event=2, generated_at="2026-08-20T10:00:00+00:00")
    latest = tmp_path / "gw2_predictions_v11.csv"
    latest.write_text("v11", encoding="utf-8")
    _certify(latest, event=2, generated_at="2026-08-21T10:00:00+00:00")

    assert select_review_prediction_file(
        tmp_path,
        2,
        deadline_time="2026-08-22T17:30:00Z",
    ) == latest


def test_select_review_prediction_file_uses_a_republished_revision(tmp_path: Path):
    original = tmp_path / "gw7_predictions_v12.csv"
    original.write_text("v12", encoding="utf-8")
    _certify(original, event=7, generated_at="2026-10-14T10:00:00+00:00")
    revision = tmp_path / "gw7_predictions_v12_r2.csv"
    revision.write_text("v12 r2", encoding="utf-8")
    _certify(revision, event=7, generated_at="2026-10-15T10:00:00+00:00")
    late = tmp_path / "gw7_predictions_v12_r3.csv"
    late.write_text("after deadline", encoding="utf-8")
    _certify(late, event=7, generated_at="2026-10-17T12:00:00+00:00")

    assert select_review_prediction_file(
        tmp_path,
        7,
        deadline_time="2026-10-17T10:00:00Z",
    ) == revision


def test_select_review_prediction_file_rejects_uncertified_artifact(tmp_path: Path):
    base = tmp_path / "gw2_predictions.csv"
    base.write_text("base", encoding="utf-8")

    with pytest.raises(ReviewDataError, match="certified pre-deadline"):
        select_review_prediction_file(
            tmp_path,
            2,
            deadline_time="2026-08-22T17:30:00Z",
        )


def test_select_review_prediction_file_rejects_post_deadline_generation(tmp_path: Path):
    artifact = tmp_path / "gw2_predictions_v5.csv"
    artifact.write_text("v5", encoding="utf-8")
    _certify(artifact, event=2, generated_at="2026-08-22T18:00:00+00:00")

    with pytest.raises(ReviewDataError, match="certified pre-deadline"):
        select_review_prediction_file(
            tmp_path,
            2,
            deadline_time="2026-08-22T17:30:00Z",
        )
