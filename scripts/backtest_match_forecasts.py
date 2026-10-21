"""Walk-forward check of the match forecasts on past seasons.

For every Gameweek, club strengths are rebuilt from matches before it only,
exactly as the live service does from the season so far, and each fixture's
probabilities are scored against the result. Baselines: the league's long-run
base rates (home win/draw/away win, both teams score, over 2.5), which a
forecast must beat to carry information.

    python -m scripts.backtest_match_forecasts            # print the report
    python -m scripts.backtest_match_forecasts --write    # also update the JSON
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import pandas as pd

from backend.match_forecast import expected_goals, match_probabilities
from backend.fixture_service import team_strengths

ROOT = Path(__file__).resolve().parent.parent
SEASONS = ("2023-24", "2024-25", "2025-26")
OUTPUT = ROOT / "backend" / "data" / "match_forecast_backtest.json"
EPS = 1e-12


def season_matches(season: str) -> list[dict]:
    folder = ROOT / "historical_data" / season
    fixtures = pd.read_csv(folder / "fixtures.csv")
    gws = pd.read_csv(folder / "merged_gw.csv", low_memory=False)
    teams = pd.read_csv(folder / "teams.csv")
    team_id = dict(zip(teams["name"], teams["id"]))
    gws["team_id"] = gws["team"].map(team_id)
    per_fixture = defaultdict(lambda: {"xg": 0.0, "xgc": 0.0})
    for row in gws.itertuples(index=False):
        if pd.isna(row.team_id):
            continue
        key = (int(row.fixture), int(row.team_id))
        per_fixture[key]["xg"] += float(row.expected_goals or 0)
        if row.position in ("GK", "GKP"):
            per_fixture[key]["xgc"] += float(row.expected_goals_conceded or 0)
    matches = []
    for f in fixtures.itertuples(index=False):
        if not bool(f.finished) or pd.isna(f.event) or pd.isna(f.team_h_score):
            continue
        matches.append({
            "id": int(f.id), "event": int(f.event), "home": int(f.team_h), "away": int(f.team_a),
            "home_goals": int(f.team_h_score), "away_goals": int(f.team_a_score),
            "home_xg": per_fixture[(int(f.id), int(f.team_h))]["xg"], "home_xgc": per_fixture[(int(f.id), int(f.team_h))]["xgc"],
            "away_xg": per_fixture[(int(f.id), int(f.team_a))]["xg"], "away_xgc": per_fixture[(int(f.id), int(f.team_a))]["xgc"],
        })
    return matches, [int(t) for t in teams["id"]]


def strengths_before(matches: list[dict], team_ids: list[int], event: int) -> dict:
    """The live inputs (season-to-date player xG, GK xGC, matches played) before `event`."""
    xg, xgc = defaultdict(float), defaultdict(float)
    played = [m for m in matches if m["event"] < event]
    for m in played:
        xg[m["home"]] += m["home_xg"]; xgc[m["home"]] += m["home_xgc"]
        xg[m["away"]] += m["away_xg"]; xgc[m["away"]] += m["away_xgc"]
    # One synthetic player per club and side carries the totals.
    elements = [{"team": t, "element_type": 4, "expected_goals": xg[t]} for t in team_ids]
    elements += [{"team": t, "element_type": 1, "expected_goals_conceded": xgc[t]} for t in team_ids]
    bootstrap = {"teams": [{"id": t} for t in team_ids], "elements": elements}
    raw = [{"team_h": m["home"], "team_a": m["away"], "finished": True} for m in played]
    return team_strengths(bootstrap, raw)


def evaluate() -> dict:
    rows = []
    for season in SEASONS:
        matches, team_ids = season_matches(season)
        for event in sorted({m["event"] for m in matches}):
            strengths = strengths_before(matches, team_ids, event)
            for m in (m for m in matches if m["event"] == event):
                rates = expected_goals(strengths, m["home"], m["away"])
                p = match_probabilities(*rates)
                rows.append({"season": season, "event": event, "p": p,
                             "outcome": "home" if m["home_goals"] > m["away_goals"] else "draw" if m["home_goals"] == m["away_goals"] else "away",
                             "btts": m["home_goals"] > 0 and m["away_goals"] > 0,
                             "over25": m["home_goals"] + m["away_goals"] > 2.5})
    n = len(rows)
    base = {k: sum(r["outcome"] == k for r in rows) / n for k in ("home", "draw", "away")}
    btts_rate = sum(r["btts"] for r in rows) / n
    over_rate = sum(r["over25"] for r in rows) / n

    def logloss_1x2(probs):
        return -sum(math.log(max(EPS, pr[r["outcome"]])) for r, pr in zip(rows, probs)) / n

    def brier_binary(probs, key):
        return sum((pr - (1.0 if r[key] else 0.0)) ** 2 for r, pr in zip(rows, probs)) / n

    model_1x2 = [r["p"]["result"] for r in rows]
    report = {
        "matches": n,
        "seasons": list(SEASONS),
        "result": {"log_loss_model": round(logloss_1x2(model_1x2), 4), "log_loss_base_rates": round(logloss_1x2([base] * n), 4),
                   "hit_rate_model": round(sum(max(pr, key=pr.get) == r["outcome"] for r, pr in zip(rows, model_1x2)) / n, 3),
                   "draws_actual": round(base["draw"], 3), "draws_predicted": round(sum(pr["draw"] for pr in model_1x2) / n, 3)},
        "both_teams_score": {"brier_model": round(brier_binary([r["p"]["both_teams_score"] for r in rows], "btts"), 4),
                             "brier_base_rate": round(brier_binary([btts_rate] * n, "btts"), 4)},
        "over_2_5": {"brier_model": round(brier_binary([r["p"]["total_goals_over"]["2.5"] for r in rows], "over25"), 4),
                     "brier_base_rate": round(brier_binary([over_rate] * n, "over25"), 4)},
    }
    # Calibration of the favourite: how often a side the model gives X% wins.
    buckets = defaultdict(lambda: [0, 0.0, 0])
    for r, pr in zip(rows, model_1x2):
        for side in ("home", "away"):
            b = min(9, int(pr[side] * 10))
            buckets[b][0] += 1; buckets[b][1] += pr[side]; buckets[b][2] += r["outcome"] == side
    report["calibration"] = [{"predicted": round(v[1] / v[0], 3), "actual": round(v[2] / v[0], 3), "count": v[0]}
                             for b, v in sorted(buckets.items()) if v[0] >= 20]
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    report = evaluate()
    print(json.dumps(report, indent=2))
    if parser.parse_args().write:
        OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
