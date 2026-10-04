from __future__ import annotations
from typing import Any, Mapping
import pandas as pd

from decision_contract import DecisionInput, validate_decision_output
from optimizer.starting_xi import select_starting_xi
from optimizer.squad_optimizer import optimize_squad
from optimizer.transfer_optimizer import TransferOptimizationConfig, optimize_transfers
from optimizer.multi_gw import MultiGWConfig
from decision_intelligence import build_intelligence

def _player_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    records=[]
    for _, row in df.iterrows():
        record=row.to_dict()
        if "player_id" in record:
            record["player_id"]=int(record["player_id"])
        for key in ("price","predicted_points"):
            if key in record and pd.notna(record[key]):
                record[key]=float(record[key])
        records.append(record)
    return records

def _validate_current_team(team: dict[str, Any]) -> None:
    if not isinstance(team, dict):
        raise ValueError("team must be a dictionary")
    picks=team.get("picks")
    if not isinstance(picks,list) or len(picks)!=15:
        raise ValueError("team must contain exactly 15 picks")
    ids=[p.get("player_id") for p in picks if isinstance(p,dict)]
    if len(ids)!=15 or any(x is None for x in ids):
        raise ValueError("team picks must contain player_id")

def _current_team_view(team: dict[str, Any], predictions: pd.DataFrame) -> dict[str, Any]:
    _validate_current_team(team)
    ids=[int(p["player_id"]) for p in team["picks"]]
    data=predictions[predictions["player_id"].isin(ids)].copy()
    if len(data)!=15:
        missing=sorted(set(ids)-set(int(x) for x in data["player_id"]))
        raise ValueError("current team players missing from predictions: "+", ".join(map(str,missing)))
    data=data.set_index("player_id").loc[ids].reset_index()
    return {
        "team_id": team.get("team_id",team.get("id")),
        "name": team.get("name"),
        "bank": float(team.get("bank")) if team.get("bank") is not None else 0.0,
        "value": team.get("value"),
        "transfers": team.get("transfers"),
        "players": _player_records(data),
    }

def build_decision(
    team: dict[str, Any],
    predictions: pd.DataFrame,
    budget: float=100.0,
    free_transfers: int=1,
    max_transfers: int=1,
    *,
    horizon_predictions: Mapping[int,pd.DataFrame] | None=None,
    horizon: int=3,
    chip_state: Mapping[str,Any] | None=None,
) -> dict[str, Any]:
    contract_input=DecisionInput(team,predictions,budget,free_transfers,max_transfers).normalized()
    team=contract_input.team
    predictions=contract_input.predictions
    budget=contract_input.budget
    free_transfers=contract_input.free_transfers
    max_transfers=contract_input.max_transfers

    current=_current_team_view(team,predictions)
    owned_ids=[int(pick["player_id"]) for pick in team["picks"]]
    current_squad=(
        predictions.set_index("player_id")
        .loc[owned_ids]
        .reset_index()
    )
    optimal=optimize_squad(predictions.copy(),budget=budget)
    xi=select_starting_xi(current_squad)
    transfers=optimize_transfers(
        team,
        predictions,
        TransferOptimizationConfig(
            max_transfers=max_transfers,
            free_transfers=free_transfers,
            bank=float(team.get("bank")) if team.get("bank") is not None else 0.0,
        ),
        horizon_predictions=(
            pd.concat(
                [
                    frame.assign(GW=int(gw))
                    for gw, frame in (horizon_predictions or {}).items()
                ],
                ignore_index=True,
            )
            if horizon_predictions
            else None
        ),
        horizon_config=MultiGWConfig(
            horizon=horizon,
            gw_weights=tuple(max(0.4, 1.0 - 0.15 * index) for index in range(horizon)),
        ),
    )

    # The intelligence layer is additive. Existing callers remain compatible:
    # horizon_predictions/chip_state are optional.
    intelligence=build_intelligence(
        current_team=current,
        predictions=predictions,
        starting_xi=current_squad.loc[
            current_squad["player_id"].isin([int(p["player_id"]) for p in xi["starting_xi"]])
        ].copy(),
        transfer_result=transfers,
        optimal_squad=optimal,
        horizon_predictions=horizon_predictions,
        horizon=horizon,
        chip_state=chip_state,
        manager_picks=team["picks"],
    )

    # Use the intelligence captain/vice only when both are valid XI members.
    intelligent_captain=intelligence["captain_decision"]["captain"]
    intelligent_vice=intelligence["captain_decision"]["vice_captain"]
    xi_ids={int(p["player_id"]) for p in xi["starting_xi"]}
    if int(intelligent_captain["player_id"]) not in xi_ids or int(intelligent_vice["player_id"]) not in xi_ids:
        intelligent_captain=xi["captain"]
        intelligent_vice=xi["vice_captain"]

    result={
        "current_team":current,
        "optimal_squad":{
            "players":_player_records(optimal),
            "total_cost":float(optimal["price"].sum()),
            "projected_points":float(optimal["predicted_points"].sum()),
        },
        "starting_xi":{
            "formation":xi["formation"],
            "players":xi["starting_xi"],
            "projected_points":float(xi["starting_xi_base_points"]),
        },
        "bench":{"players":xi["bench"]},
        "captain":{
            "player_id":int(intelligent_captain["player_id"]),
            "name":str(intelligent_captain["name"]),
            "predicted_points":float(intelligent_captain["predicted_points"]),
            "team": intelligent_captain.get("team"),
            "xmins": intelligent_captain.get("xmins"),
            "start_probability": intelligent_captain.get("start_probability"),
            "availability": intelligent_captain.get("availability"),
            "difficulty": intelligent_captain.get("difficulty"),
            "captain_score": intelligent_captain.get("captain_score"),
        },
        "vice_captain":{
            "player_id":int(intelligent_vice["player_id"]),
            "name":str(intelligent_vice["name"]),
            "predicted_points":float(intelligent_vice["predicted_points"]),
            "team": intelligent_vice.get("team"),
            "xmins": intelligent_vice.get("xmins"),
            "start_probability": intelligent_vice.get("start_probability"),
            "availability": intelligent_vice.get("availability"),
            "difficulty": intelligent_vice.get("difficulty"),
            "captain_score": intelligent_vice.get("captain_score"),
        },
        "transfers":transfers,
        "intelligence":intelligence,
    }
    return validate_decision_output(result)
