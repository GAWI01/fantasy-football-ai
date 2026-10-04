import pandas as pd
import pytest
from optimizer.chip_optimizer import evaluate_chip_scenarios

def squad():
    rows=[]
    for pos,n in [("GK",2),("DEF",5),("MID",5),("FWD",3)]:
        for i in range(n):
            rows.append({"player_id":len(rows)+1,"name":f"{pos}{i}","position":pos,"team":f"T{len(rows)%6}","price":5.0,"predicted_points":4.0})
    return pd.DataFrame(rows)

def pool():
    rows=squad().to_dict("records")
    for i in range(16,21):
        rows.append({"player_id":i,"name":f"Elite{i}","position":"MID","team":f"Z{i}","price":5.0,"predicted_points":10.0})
    return pd.DataFrame(rows)

def test_blank_gameweek_prefers_free_hit_when_available():
    out=evaluate_chip_scenarios(squad(),pool(),available_chips={"FREE_HIT":True,"WILDCARD":False,"BENCH_BOOST":False,"TRIPLE_CAPTAIN":False},blank_gameweek=True)
    assert out["recommended_chip"]=="FREE_HIT"

def test_double_gameweek_exposes_bench_and_triple_captain_scenarios():
    out=evaluate_chip_scenarios(squad(),pool(),available_chips={"FREE_HIT":False,"WILDCARD":False,"BENCH_BOOST":True,"TRIPLE_CAPTAIN":True},double_gameweek=True)
    assert {x["chip"] for x in out["scenarios"]}=={"BENCH_BOOST","TRIPLE_CAPTAIN"}

def test_no_available_chip_returns_none():
    out=evaluate_chip_scenarios(squad(),pool(),available_chips={c:False for c in ["WILDCARD","FREE_HIT","BENCH_BOOST","TRIPLE_CAPTAIN"]})
    assert out["recommended_chip"] is None


def test_rebuild_chips_cannot_buy_unaffordable_market_players():
    expensive = pool()
    expensive.loc[expensive.player_id >= 16, "price"] = 20.0
    out = evaluate_chip_scenarios(squad(), expensive, available_chips={"WILDCARD": True, "FREE_HIT": True}, blank_gameweek=True)
    assert out["score"] == 0
    assert out["budget"] == 75.0
    assert out["selling_prices_known"] is False


def test_bench_boost_counts_only_the_four_owned_bench_players():
    out = evaluate_chip_scenarios(squad(), pool(), available_chips={"BENCH_BOOST": True}, double_gameweek=True)
    assert out["scenarios"][0]["score"] == 16.0


def test_triple_captain_adds_one_owned_captain_multiple():
    owned = squad()
    owned.loc[owned.player_id == 8, "predicted_points"] = 7.0
    market = pd.concat([owned, pool().query("player_id >= 16")])
    out = evaluate_chip_scenarios(owned, market, available_chips={"TRIPLE_CAPTAIN": True}, double_gameweek=True)
    assert out["scenarios"][0]["score"] == 7.0
    assert out["baseline_value"] == 54.0


def test_wildcard_and_free_hit_use_the_same_xi_and_captain_baseline():
    out = evaluate_chip_scenarios(squad(), pool(), available_chips={"WILDCARD": True, "FREE_HIT": True}, blank_gameweek=True)
    scores = {s["chip"]: s["score"] for s in out["scenarios"]}
    assert scores == {"WILDCARD": 36.0, "FREE_HIT": 36.0}
    assert out["baseline_value"] == 48.0


def test_owned_explicit_lineup_and_captain_are_used_for_chip_gains():
    owned = squad()
    owned.loc[owned.player_id == 8, "predicted_points"] = 9.0
    # 1 GK, 5 DEF, 2 MID and 3 FWD; MID 8 is deliberately on the bench.
    xi_ids = [1, 3, 4, 5, 6, 7, 9, 10, 13, 14, 15]
    out = evaluate_chip_scenarios(owned, pool(), available_chips={"TRIPLE_CAPTAIN": True, "BENCH_BOOST": True},
                                  double_gameweek=True, starting_xi_ids=xi_ids, captain_id=9)
    assert {s["chip"]: s["score"] for s in out["scenarios"]} == {"BENCH_BOOST": 21.0, "TRIPLE_CAPTAIN": 4.0}
    assert out["baseline_value"] == 48.0


def test_verified_selling_value_and_bank_determine_chip_budget():
    owned = squad()
    owned["selling_price"] = 4.0
    out = evaluate_chip_scenarios(owned, pool(), available_chips={"WILDCARD": True}, bank=3.0)
    assert out["budget"] == 63.0
    assert out["selling_prices_known"] is True
    # Owned players can be retained without buying them at their market price.
    assert out["scenarios"][0]["score"] == 24.0


def test_no_available_chips_still_labels_unknown_budget():
    out = evaluate_chip_scenarios(squad(), pool(), available_chips={})
    assert out["budget_is_estimate"] is True
    assert out["selling_prices_known"] is False
