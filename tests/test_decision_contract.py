import pandas as pd
import pytest

from engine.decision_contract import DecisionContractError, DecisionInput, validate_decision_output


def predictions():
    return pd.DataFrame([{"player_id": i, "predicted_points": float(i)} for i in range(1, 18)])


def team():
    return {"team_id": 123, "name": "Test FC", "picks": [{"player_id": i} for i in range(1, 16)]}


def test_input_contract_normalizes_runtime_types():
    result = DecisionInput(team(), predictions(), "100", "1", "1").normalized()
    assert result.budget == 100.0
    assert result.free_transfers == 1
    assert result.max_transfers == 1


def test_input_contract_rejects_wrong_squad_size():
    value = team()
    value["picks"] = value["picks"][:14]
    with pytest.raises(DecisionContractError, match="exactly 15"):
        DecisionInput(value, predictions(), 100, 1, 1).validate()


def test_input_contract_rejects_missing_player_id():
    value = team()
    value["picks"][0].pop("player_id")
    with pytest.raises(DecisionContractError, match="missing player_id"):
        DecisionInput(value, predictions(), 100, 1, 1).validate()


def test_input_contract_rejects_duplicate_player_id():
    value = team()
    value["picks"][-1]["player_id"] = 1
    with pytest.raises(DecisionContractError, match="unique"):
        DecisionInput(value, predictions(), 100, 1, 1).validate()


def test_input_contract_rejects_bad_predictions():
    value = predictions().drop(columns=["predicted_points"])
    with pytest.raises(DecisionContractError, match="missing"):
        DecisionInput(team(), value, 100, 1, 1).validate()


def test_output_contract_accepts_existing_decision_shape():
    players = [{"player_id": i} for i in range(1, 16)]
    result = {
        "current_team": {"players": players},
        "optimal_squad": {"players": players},
        "starting_xi": {"players": players[:11]},
        "bench": {"players": players[11:]},
        "captain": {"player_id": 1},
        "vice_captain": {"player_id": 2},
        "transfers": {},
    }
    assert validate_decision_output(result) == result


def test_output_contract_rejects_duplicate_captain():
    players = [{"player_id": i} for i in range(1, 16)]
    result = {
        "current_team": {"players": players},
        "optimal_squad": {"players": players},
        "starting_xi": {"players": players[:11]},
        "bench": {"players": players[11:]},
        "captain": {"player_id": 1},
        "vice_captain": {"player_id": 1},
        "transfers": {},
    }
    with pytest.raises(DecisionContractError, match="different"):
        validate_decision_output(result)
