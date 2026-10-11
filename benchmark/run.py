"""Decision benchmark over recorded real FPL teams.

    python -m benchmark.run [--json OUT]

Each case replays the recorded snapshot just before the pinned forecast's
deadline and summarises the canonical decision the API returns.
"""
from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("FPL_AI_UPSTREAM_MAX_PER_MINUTE", "1000")

from fastapi.testclient import TestClient  # noqa: E402

from benchmark.harness import load_snapshot, pinned_data, replay  # noqa: E402

SNAPSHOT = "gw6_pre_deadline"
EVENT = 6
TEAMS = [895045, 4182037, 5151567, 1, 2, 6658075, 145931, 2312895, 5841371, 1482, 5416316, 639449]
FT_OVERRIDES = {895045: [0, 2, 3]}


def _moves(transfers) -> list[str]:
    return [f"{t['player_out']}>{t['player_in']}" for t in transfers or []]


def summarise(payload: dict) -> dict:
    decision = payload["data"].get("decision")
    if not decision:
        return {"error": payload.get("errors")}
    transfers = decision["transfers"]
    intelligence = decision["intelligence"]
    strategy = intelligence["transfer_strategy"]
    players = {p["player_id"]: p for p in decision["current_team"]["players"]}
    bench_ids = {p["player_id"] for p in decision["bench"]["players"]}
    out_ids = [t["player_out_id"] for t in strategy.get("selected_transfers") or []]
    return {
        "free_transfers": transfers.get("free_transfers"),
        "action": intelligence.get("action"),
        "confidence": intelligence["confidence"].get("label"),
        "engine_transfers": _moves(transfers.get("recommended_transfers")),
        "shown_transfers": _moves(strategy.get("selected_transfers")),
        "consistent": _moves(transfers.get("recommended_transfers")) == _moves(strategy.get("selected_transfers")),
        "hit_cost": transfers.get("hit_cost"),
        "selling_prices_known": transfers.get("selling_prices_known"),
        "sells_bench_gk": any(players[i]["position"] in {"GK", "GKP"} and i in bench_ids for i in out_ids),
        "sells_bench_player": any(i in bench_ids for i in out_ids),
        "captain": decision["captain"]["name"],
        "captain_is_sold": decision["captain"]["player_id"] in {t["player_out_id"] for t in transfers.get("recommended_transfers") or []},
        "lineup_has_sold_player": bool({p["player_id"] for p in decision["starting_xi"]["players"] + decision["bench"]["players"]}
                                       & {t["player_out_id"] for t in transfers.get("recommended_transfers") or []}),
        "vice": decision["vice_captain"]["name"],
        "chip": intelligence["chip_advisor"].get("recommended_chip"),
        "wildcard_advantage": (intelligence.get("wildcard_signal") or {}).get("advantage"),
        "decision_score": transfers.get("decision_score"),
        "next_gw_gain": transfers.get("next_gw_gain"),
        "horizon_gain": transfers.get("gross_gain"),
        "options": [(o["transfers_used"], o["gross_gain"], o["decision_score"]) for o in transfers.get("options_by_transfer_count") or []],
    }


def run() -> list[dict]:
    from backend.main import app

    rows = []
    with pinned_data("gw6"), replay(load_snapshot(SNAPSHOT), pre_deadline_event=EVENT):
        client = TestClient(app)
        for team in TEAMS:
            for ft in [None, *FT_OVERRIDES.get(team, [])]:
                query = "" if ft is None else f"?free_transfers={ft}"
                response = client.get(f"/api/v1/dashboard/{team}{query}")
                rows.append({"team": team, "ft_override": ft, **summarise(response.json())})
    return rows


def main(argv: list[str]) -> None:
    rows = run()
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w", encoding="utf-8") as handle:
            json.dump(rows, handle, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1:])
