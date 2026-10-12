import pandas as pd
from engine.decision_intelligence import build_intelligence

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

def test_captain_availability_is_not_discounted_twice():
    # Risky's 6.0 already includes his 60% chance of playing (10 x 0.6).
    p=pd.DataFrame([
        {"player_id":1,"name":"Risky","predicted_points":6.0,"xmins":54,"start_probability":.6,"availability":"RISK","difficulty":3},
        {"player_id":2,"name":"Safe","predicted_points":5.5,"xmins":90,"start_probability":1,"availability":"AVAILABLE","difficulty":2},
    ])
    team={"players":[dict(p.iloc[0]),dict(p.iloc[1])]}
    out=build_intelligence(current_team=team,predictions=p,starting_xi=p,transfer_result={"net_gain":0,"gross_gain":0,"transfers_used":0,"hit_cost":0})
    assert out["captain_decision"]["captain"]["player_id"]==1
    assert out["captain_decision"]["captain"]["captain_score"]==6.0


def test_equal_captain_values_prefer_the_surer_starter():
    p=pd.DataFrame([
        {"player_id":1,"name":"Doubt","predicted_points":5.0,"start_probability":.7,"availability":"RISK"},
        {"player_id":2,"name":"Nailed","predicted_points":5.0,"start_probability":1.0,"availability":"AVAILABLE"},
    ])
    team={"players":[dict(p.iloc[0]),dict(p.iloc[1])]}
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
    tr={"net_gain":3.5,"gross_gain":3.5,"transfers_used":1,"hit_cost":0,"decision_score":1.5,"recommended_transfers":[{"player_out_id":1,"player_in_id":2}],"alternatives":[]}
    out=build_intelligence(current_team=team,predictions=p1,starting_xi=xi,transfer_result=tr,horizon_predictions={2:p2,3:p3},horizon=3)
    strategy=out["transfer_strategy"]
    # The canonical lineup gain is reported, never recomputed or re-ranked.
    assert strategy["horizon_gain"]==3.5
    assert strategy["decision_score"]==1.5
    # Per-player detail explains it: player 2 outscores player 1 by 9 points.
    assert strategy["selected_transfers"][0]["player_horizon_difference"]==9
    assert out["action"]=="SINGLE_TRANSFER"


def test_horizon_selection_keeps_transfer_names_and_prices():
    p1=pd.DataFrame([{"player_id":1,"predicted_points":4},{"player_id":2,"predicted_points":5}])
    p2=pd.DataFrame([{"player_id":1,"predicted_points":4},{"player_id":2,"predicted_points":8}])
    team={"players":[{"player_id":1,"name":"A","predicted_points":4,"xmins":90,"availability":"AVAILABLE"}]+[
        {"player_id":i,"name":str(i),"predicted_points":1,"xmins":90,"availability":"AVAILABLE"} for i in range(3,17)
    ]}
    xi=pd.DataFrame([{"player_id":1,"name":"A","predicted_points":4,"xmins":90,"start_probability":1,"availability":"AVAILABLE","difficulty":2},{"player_id":3,"name":"3","predicted_points":1,"xmins":90,"start_probability":1,"availability":"AVAILABLE","difficulty":2}])
    named={"player_out_id":1,"player_out":"A","player_in_id":2,"player_in":"Gakpo","price":7.0,"position":"MID"}
    other={**named,"player_in_id":4,"player_in":"Other"}
    tr={"net_gain":1,"gross_gain":1,"transfers_used":1,"hit_cost":0,"recommended_transfers":[named],"alternatives":[{"transfers":[other],"net_gain":0.5,"transfers_used":1}]}
    out=build_intelligence(current_team=team,predictions=p1,starting_xi=xi,transfer_result=tr,horizon_predictions={2:p2},horizon=2)
    selected=out["transfer_strategy"]["selected_transfers"][0]
    assert selected["player_in"]=="Gakpo"
    assert selected["price"]==7.0
    assert selected["player_out"]=="A"
    assert "in_projection" in selected
    assert out["transfer_strategy"]["alternatives"][0]["transfers"][0]["player_in"]=="Other"


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


def test_strategy_never_selects_a_different_plan_than_the_planner():
    p1=pd.DataFrame([{"player_id":i,"predicted_points":float(i)} for i in range(1,20)])
    team={"players":[{"player_id":i,"name":str(i),"predicted_points":float(i),"xmins":90,"availability":"AVAILABLE"} for i in range(1,16)]}
    xi=pd.DataFrame([{"player_id":i,"name":str(i),"predicted_points":float(i),"xmins":90,"start_probability":1,"availability":"AVAILABLE","difficulty":3} for i in range(1,12)])
    chosen={"player_out_id":1,"player_in_id":16}
    # A raw per-player comparison would prefer 19 for 1; the planner chose 16.
    tr={"action":"SINGLE_TRANSFER","net_gain":2.0,"gross_gain":2.0,"decision_score":0.5,"transfers_used":1,"hit_cost":0,
        "recommended_transfers":[chosen],
        "alternatives":[{"transfers":[{"player_out_id":1,"player_in_id":19}],"transfers_used":1,"gross_gain":1.0,"net_gain":1.0,"decision_score":-1.0}]}
    out=build_intelligence(current_team=team,predictions=p1,starting_xi=xi,transfer_result=tr)
    assert [(m["player_out_id"],m["player_in_id"]) for m in out["transfer_strategy"]["selected_transfers"]]==[(1,16)]
    assert out["transfer_strategy"]["action"]=="SINGLE_TRANSFER"


def test_hold_insight_names_the_rejected_move_and_reports_real_numbers():
    p1=pd.DataFrame([{"player_id":i,"predicted_points":float(i)} for i in range(1,20)])
    team={"players":[{"player_id":i,"name":str(i),"predicted_points":float(i),"xmins":90,"availability":"AVAILABLE"} for i in range(1,16)]}
    xi=pd.DataFrame([{"player_id":i,"name":str(i),"predicted_points":float(i),"xmins":90,"start_probability":1,"availability":"AVAILABLE","difficulty":3} for i in range(1,12)])
    rejected={"player_out_id":1,"player_out":"One","player_in_id":16,"player_in":"Sixteen"}
    tr={"action":"HOLD","net_gain":0.0,"gross_gain":0.0,"decision_score":0.0,"transfers_used":0,"hit_cost":0,"recommended_transfers":[],
        "alternatives":[{"transfers":[rejected],"transfers_used":1,"gross_gain":1.2,"net_gain":1.2,"roll_value_forgone":2.0,"decision_score":-0.8}]}
    out=build_intelligence(current_team=team,predictions=p1,starting_xi=xi,transfer_result=tr)
    transfer=next(i for i in out["insights"] if i["type"]=="TRANSFER")
    assert out["action"]=="HOLD"
    assert "One → Sixteen" in transfer["reason"] and "+1.2" in transfer["reason"]
    assert transfer["evidence"]["net_gain"]==0.0


def test_captain_within_the_tie_band_goes_to_the_surer_starter():
    p=pd.DataFrame([
        {"player_id":1,"name":"Doubt","predicted_points":5.6,"start_probability":.79,"availability":"AVAILABLE"},
        {"player_id":2,"name":"Nailed","predicted_points":5.5,"start_probability":1.0,"availability":"AVAILABLE"},
        {"player_id":3,"name":"Other","predicted_points":4.0,"start_probability":1.0,"availability":"AVAILABLE"},
    ])
    team={"players":[dict(p.iloc[i]) for i in range(3)]}
    out=build_intelligence(current_team=team,predictions=p,starting_xi=p,transfer_result={"net_gain":0,"gross_gain":0,"transfers_used":0,"hit_cost":0})
    assert out["captain_decision"]["captain"]["player_id"]==2
    assert out["captain_decision"]["vice_captain"]["player_id"]==1
    # A clear expected-value lead still wins.
    p.loc[p.player_id==1,"predicted_points"]=6.5
    out=build_intelligence(current_team=team,predictions=p,starting_xi=p,transfer_result={"net_gain":0,"gross_gain":0,"transfers_used":0,"hit_cost":0})
    assert out["captain_decision"]["captain"]["player_id"]==1


def test_strategy_preserves_projected_points_without_relabelling_legacy_scores():
    predictions = pd.DataFrame([
        {"player_id": 1, "name": "A", "predicted_points": 5.0, "xmins": 90,
         "start_probability": 1, "availability": "AVAILABLE", "difficulty": 2},
        {"player_id": 2, "name": "B", "predicted_points": 4.0, "xmins": 90,
         "start_probability": 1, "availability": "AVAILABLE", "difficulty": 2},
    ])
    legacy = {"net_gain": 2.0, "gross_gain": 6.0, "transfers_used": 0, "hit_cost": 4.0}
    projected = {**legacy, "projected_gain": 10.0, "projected_net_gain": 6.0}
    for source in (legacy, projected):
        result = build_intelligence(
            current_team={"players": predictions.to_dict("records")}, predictions=predictions,
            starting_xi=predictions,
            transfer_result={**source, "alternatives": [source], "options_by_transfer_count": [source]},
        )
        strategy = result["transfer_strategy"]
        for option in (strategy, strategy["alternatives"][0], strategy["options_by_transfer_count"][0]):
            assert option["projected_gain"] == source.get("projected_gain")
            assert option["projected_net_gain"] == source.get("projected_net_gain")
            assert option["horizon_gain"] == 6.0
            assert option["net_gain"] == 2.0
