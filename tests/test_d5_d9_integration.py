import pandas as pd
from engine.decision_engine import build_decision

def predictions():
    rows=[]
    for pos,n in [("GK",2),("DEF",5),("MID",5),("FWD",3)]:
        for i in range(n):
            rows.append({"player_id":len(rows)+1,"name":f"{pos}{i}","position":pos,"team":f"T{len(rows)%6}","price":5.0,"predicted_points":5.0,"xmins":90,"availability":"AVAILABLE","rotation_risk":"LOW"})
    rows.append({"player_id":16,"name":"Elite","position":"MID","team":"Z","price":5.0,"predicted_points":10.0,"xmins":90,"availability":"AVAILABLE","rotation_risk":"LOW"})
    return pd.DataFrame(rows)

def test_decision_contains_risk_and_chip_scenario_blocks():
    team={"picks":[{"player_id":i} for i in range(1,16)],"bank":0.0}
    out=build_decision(team,predictions(),budget=100,free_transfers=1,max_transfers=1,chip_state={"double_gameweek":True})
    assert "chip_advisor" in out["intelligence"]
    assert "risk_summary" in out["intelligence"]
    assert "chip_scenarios" in out["intelligence"]
