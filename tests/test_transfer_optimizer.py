import pandas as pd
from optimizer.transfer_optimizer import TransferOptimizationConfig, calculate_transfer_value, optimize_transfers

def data():
    rows=[]
    for pos,n in [("GK",2),("DEF",5),("MID",5),("FWD",3)]:
        for i in range(n):
            rows.append({"player_id":len(rows)+1,"name":f"{pos}{i}","position":pos,"team":f"T{len(rows)%6}","price":5.0,"predicted_points":5.0})
    rows.append({"player_id":16,"name":"Elite","position":"MID","team":"Z","price":5.0,"predicted_points":10.0})
    return pd.DataFrame(rows)

def team():
    return {"picks":[{"player_id":i} for i in range(1,16)],"bank":0.0}

def test_transfer_value_applies_hit_cost():
    cur=data().iloc[:15].copy(); new=cur.copy()
    new.loc[new.player_id.eq(15),"predicted_points"]=10
    assert calculate_transfer_value(cur,new,hit_cost=4)==1.0

def test_optimizer_returns_feasible_transfer_plan():
    result=optimize_transfers(team(),data(),TransferOptimizationConfig(max_transfers=1))
    assert result["transfers_used"]==1
    assert result["recommended_transfers"][0]["player_in_id"]==16
    # +5 in the XI and +5 as the new captain.
    assert result["net_gain"]==10.0


def test_transfer_optimizer_accepts_multi_gw_predictions():
    horizon = data().copy()
    horizon["GW"] = 2
    horizon2 = data().copy()
    horizon2["GW"] = 3
    horizon2["predicted_points"] = horizon2["predicted_points"] + 1.0
    horizon = pd.concat([horizon, horizon2], ignore_index=True)
    result = optimize_transfers(
        team(),
        data(),
        TransferOptimizationConfig(max_transfers=1),
        horizon_predictions=horizon,
    )
    assert result["transfers_used"] == 1
    assert result["recommended_transfers"][0]["player_in_id"] == 16
