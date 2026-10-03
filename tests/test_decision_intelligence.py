import pandas as pd
from decision_intelligence import build_intelligence

def test_hold_when_no_positive_transfer():
    p = pd.DataFrame([
        {"player_id":1,"name":"A","predicted_points":5,"xmins":90,"start_probability":1,"availability":"AVAILABLE","difficulty":2},
        {"player_id":2,"name":"B","predicted_points":4,"xmins":90,"start_probability":1,"availability":"AVAILABLE","difficulty":2},
    ])
    team={"players":[dict(p.iloc[0]),dict(p.iloc[1])]}
    out=build_intelligence(
        current_team=team,predictions=p,starting_xi=p,
        transfer_result={"net_gain":0,"gross_gain":0,"transfers_used":0,"hit_cost":0}
    )
    assert out["action"]=="HOLD"

def test_risky_captain_is_downgraded():
    p=pd.DataFrame([
        {"player_id":1,"name":"Risky","predicted_points":10,"xmins":45,"start_probability":.5,"availability":"RISK","difficulty":3},
        {"player_id":2,"name":"Safe","predicted_points":8,"xmins":90,"start_probability":1,"availability":"AVAILABLE","difficulty":2},
    ])
    team={"players":[
        {**dict(p.iloc[0]),"rotation_risk":"HIGH"},
        {**dict(p.iloc[1]),"rotation_risk":"LOW"},
    ]}
    out=build_intelligence(current_team=team,predictions=p,starting_xi=p,transfer_result={"net_gain":0,"gross_gain":0,"transfers_used":0,"hit_cost":0})
    assert out["captain_decision"]["captain"]["player_id"]==2

def test_three_gameweek_transfer_horizon():
    p1=pd.DataFrame([{"player_id":1,"predicted_points":4},{"player_id":2,"predicted_points":5}])
    p2=pd.DataFrame([{"player_id":1,"predicted_points":4},{"player_id":2,"predicted_points":8}])
    p3=pd.DataFrame([{"player_id":1,"predicted_points":4},{"player_id":2,"predicted_points":8}])
    team={"players":[{"player_id":1,"name":"A","predicted_points":4,"xmins":90,"availability":"AVAILABLE"}]+[
        {"player_id":i,"name":str(i),"predicted_points":1,"xmins":90,"availability":"AVAILABLE"} for i in range(3,17)
    ]}
    xi=pd.DataFrame([{"player_id":1,"name":"A","predicted_points":4,"xmins":90,"start_probability":1,"availability":"AVAILABLE","difficulty":2},{"player_id":2,"name":"B","predicted_points":5,"xmins":90,"start_probability":1,"availability":"AVAILABLE","difficulty":2}])
    tr={"net_gain":1,"gross_gain":1,"transfers_used":1,"hit_cost":0,"recommended_transfers":[{"player_out_id":1,"player_in_id":2}],"alternatives":[]}
    out=build_intelligence(current_team=team,predictions=p1,starting_xi=xi,transfer_result=tr,horizon_predictions={2:p2,3:p3},horizon=3)
    assert out["transfer_strategy"]["horizon_gain"]==9


def test_horizon_selection_keeps_transfer_names_and_prices():
    p1=pd.DataFrame([{"player_id":1,"predicted_points":4},{"player_id":2,"predicted_points":5}])
    p2=pd.DataFrame([{"player_id":1,"predicted_points":4},{"player_id":2,"predicted_points":8}])
    team={"players":[{"player_id":1,"name":"A","predicted_points":4,"xmins":90,"availability":"AVAILABLE"}]+[
        {"player_id":i,"name":str(i),"predicted_points":1,"xmins":90,"availability":"AVAILABLE"} for i in range(3,17)
    ]}
    xi=pd.DataFrame([{"player_id":1,"name":"A","predicted_points":4,"xmins":90,"start_probability":1,"availability":"AVAILABLE","difficulty":2},{"player_id":3,"name":"3","predicted_points":1,"xmins":90,"start_probability":1,"availability":"AVAILABLE","difficulty":2}])
    named={"player_out_id":1,"player_out":"A","player_in_id":2,"player_in":"Gakpo","price":7.0,"position":"MID"}
    tr={"net_gain":1,"gross_gain":1,"transfers_used":1,"hit_cost":0,"recommended_transfers":[named],"alternatives":[{"transfers":[named],"net_gain":0.5}]}
    out=build_intelligence(current_team=team,predictions=p1,starting_xi=xi,transfer_result=tr,horizon_predictions={2:p2},horizon=2)
    selected=out["transfer_strategy"]["selected_transfers"][0]
    assert selected["player_in"]=="Gakpo"
    assert selected["price"]==7.0
    assert selected["player_out"]=="A"
    assert "in_projection" in selected
    assert out["transfer_strategy"]["alternatives"][0]["transfers"][0]["player_in"]=="Gakpo"


def test_unknown_chip_state_never_invents_availability():
    p = pd.DataFrame([
        {"player_id": 1, "name": "A", "position": "MID", "team": "A", "price": 5, "predicted_points": 5, "xmins": 90, "start_probability": 1, "availability": "AVAILABLE", "difficulty": 2},
        {"player_id": 2, "name": "B", "position": "MID", "team": "B", "price": 5, "predicted_points": 4, "xmins": 90, "start_probability": 1, "availability": "AVAILABLE", "difficulty": 2},
    ])
    team = {"players": [dict(p.iloc[0]), dict(p.iloc[1])]}

    out = build_intelligence(
        current_team=team,
        predictions=p,
        starting_xi=p,
        transfer_result={"net_gain": 0, "gross_gain": 0, "transfers_used": 0, "hit_cost": 0},
        chip_state=None,
    )

    assert out["chip_state"]["known"] is False
    assert out["chip_advisor"]["recommended_chip"] is None
    assert out["chip_scenarios"]["scenarios"] == []


def test_horizon_exposes_projection_for_recommended_captain():
    predictions = pd.DataFrame([
        {"player_id": 1, "name": "Current", "predicted_points": 4, "xmins": 90, "start_probability": 1, "availability": "AVAILABLE", "difficulty": 3},
        {"player_id": 2, "name": "Captain", "predicted_points": 8, "xmins": 90, "start_probability": 1, "availability": "AVAILABLE", "difficulty": 2},
    ])
    team = {"players": [dict(predictions.iloc[0])]}

    out = build_intelligence(
        current_team=team,
        predictions=predictions,
        starting_xi=predictions,
        transfer_result={"net_gain": 0, "gross_gain": 0, "transfers_used": 0, "hit_cost": 0},
        horizon=1,
    )

    assert out["captain_decision"]["captain"]["player_id"] == 2
    assert out["horizon"]["captain_projection"]["player_id"] == 2
    assert out["horizon"]["captain_projection"]["gameweeks"][0]["predicted_points"] == 8


def test_horizon_summary_uses_actual_gameweek_numbers():
    native = pd.DataFrame([
        {
            "player_id": 1, "name": "Captain", "predicted_points": 8,
            "xmins": 90, "start_probability": 1, "availability": "AVAILABLE",
            "difficulty": 2, "gameweek": 3,
        },
        {
            "player_id": 2, "name": "Vice", "predicted_points": 6,
            "xmins": 90, "start_probability": 1, "availability": "AVAILABLE",
            "difficulty": 3, "gameweek": 3,
        },
    ])
    future = native.assign(predicted_points=7, gameweek=4)
    team = {"players": [dict(native.iloc[0])]}

    out = build_intelligence(
        current_team=team,
        predictions=native,
        starting_xi=native,
        transfer_result={"net_gain": 0, "gross_gain": 0, "transfers_used": 0, "hit_cost": 0},
        horizon_predictions={1: native, 2: future},
        horizon=2,
    )

    assert out["horizon"]["gameweeks"] == [3, 4]
