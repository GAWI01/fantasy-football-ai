import pandas as pd
from engine.decision_engine import build_decision

def make_data():
    rows=[]
    for pos,n in [("GK",2),("DEF",5),("MID",5),("FWD",3)]:
        for i in range(n):
            rows.append({"player_id":len(rows)+1,"name":f"{pos}{i}","position":pos,"team":f"T{len(rows)%6}","price":5.0,"predicted_points":5.0})
    rows.append({"player_id":16,"name":"Elite","position":"MID","team":"Z","price":5.0,"predicted_points":10.0})
    return pd.DataFrame(rows)

def test_prediction_to_decision_path_remains_valid():
    df=make_data(); team={"picks":[{"player_id":i} for i in range(1,16)],"bank":0.0}
    result=build_decision(team,df,budget=100,free_transfers=1,max_transfers=1)
    assert len(result["optimal_squad"]["players"])==15
    assert len(result["transfers"]["post_transfer_squad"])==15
