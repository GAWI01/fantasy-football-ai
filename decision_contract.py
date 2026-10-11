"""Canonical contracts for the FPL-AI Decision Engine."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
import pandas as pd

class DecisionContractError(ValueError):
    """Raised when Decision Engine input/output violates its contract."""

@dataclass(frozen=True)
class DecisionInput:
    team: Mapping[str, Any]
    predictions: pd.DataFrame
    budget: float
    free_transfers: int
    max_transfers: int

    def validate(self) -> None:
        if not isinstance(self.team, Mapping):
            raise DecisionContractError("team must be a mapping")
        picks = self.team.get("picks")
        if not isinstance(picks, Sequence) or isinstance(picks, (str, bytes)):
            raise DecisionContractError("team.picks must be a sequence")
        if len(picks) != 15:
            raise DecisionContractError(f"team.picks must contain exactly 15 players; got {len(picks)}")
        ids = []
        for i, pick in enumerate(picks):
            if not isinstance(pick, Mapping):
                raise DecisionContractError(f"team.picks[{i}] must be a mapping")
            if pick.get("player_id") is None:
                raise DecisionContractError(f"team.picks[{i}] is missing player_id")
            try:
                ids.append(int(pick["player_id"]))
            except (TypeError, ValueError) as exc:
                raise DecisionContractError(f"team.picks[{i}].player_id must be an integer") from exc
        if len(set(ids)) != 15:
            raise DecisionContractError("team.picks must contain 15 unique player IDs")
        if not isinstance(self.predictions, pd.DataFrame):
            raise DecisionContractError("predictions must be a pandas DataFrame")
        missing = {"player_id", "predicted_points"} - set(self.predictions.columns)
        if missing:
            raise DecisionContractError("predictions missing required columns: " + ", ".join(sorted(missing)))
        pred_ids = pd.to_numeric(self.predictions["player_id"], errors="coerce")
        points = pd.to_numeric(self.predictions["predicted_points"], errors="coerce")
        if pred_ids.isna().any() or points.isna().any():
            raise DecisionContractError("predictions.player_id and predicted_points must contain only numeric values")
        if self.predictions["player_id"].duplicated().any():
            raise DecisionContractError("predictions.player_id must be unique")
        if float(self.budget) <= 0:
            raise DecisionContractError("budget must be greater than 0")
        if int(self.free_transfers) < 0:
            raise DecisionContractError("free_transfers cannot be negative")
        if int(self.max_transfers) < 0:
            raise DecisionContractError("max_transfers cannot be negative")

    def normalized(self) -> "DecisionInput":
        self.validate()
        return DecisionInput(
            team=self.team,
            predictions=self.predictions.copy(),
            budget=float(self.budget),
            free_transfers=int(self.free_transfers),
            max_transfers=int(self.max_transfers),
        )

REQUIRED_DECISION_SECTIONS = frozenset({
    "current_team", "optimal_squad", "starting_xi",
    "bench", "captain", "vice_captain", "transfers",
})

OPTIONAL_INTELLIGENCE_SECTIONS = frozenset({
    "action", "confidence", "captain_decision", "squad_health",
    "horizon", "transfer_strategy", "chip_advisor", "wildcard_pressure",
    "insights", "chip_scenarios", "risk_summary",
})

def validate_decision_output(result: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise DecisionContractError("decision result must be a mapping")
    missing = REQUIRED_DECISION_SECTIONS - set(result)
    if missing:
        raise DecisionContractError("decision result missing required sections: " + ", ".join(sorted(missing)))
    for section in REQUIRED_DECISION_SECTIONS:
        if not isinstance(result[section], Mapping):
            raise DecisionContractError(f"decision result section '{section}' must be a mapping")
    groups = {
        "current_team.players": result["current_team"].get("players"),
        "optimal_squad.players": result["optimal_squad"].get("players"),
        "starting_xi.players": result["starting_xi"].get("players"),
        "bench.players": result["bench"].get("players"),
    }
    for name, players in groups.items():
        if not isinstance(players, list):
            raise DecisionContractError(f"{name} must be a list")
    if len(groups["current_team.players"]) != 15:
        raise DecisionContractError("current_team.players must contain 15 players")
    if len(groups["optimal_squad.players"]) != 15:
        raise DecisionContractError("optimal_squad.players must contain 15 players")
    if len(groups["starting_xi.players"]) != 11:
        raise DecisionContractError("starting_xi.players must contain 11 players")
    if len(groups["bench.players"]) != 4:
        raise DecisionContractError("bench.players must contain 4 players")
    xi_ids = {int(p["player_id"]) for p in groups["starting_xi.players"]}
    captain = result["captain"].get("player_id")
    vice = result["vice_captain"].get("player_id")
    if captain is None or vice is None:
        raise DecisionContractError("captain and vice_captain require player_id")
    if int(captain) == int(vice):
        raise DecisionContractError("captain and vice_captain must be different players")
    if int(captain) not in xi_ids or int(vice) not in xi_ids:
        raise DecisionContractError("captain and vice_captain must be in starting_xi")
    if "intelligence" in result:
        intelligence = result["intelligence"]
        if not isinstance(intelligence, Mapping):
            raise DecisionContractError("intelligence must be a mapping")
        if intelligence.get("action") not in {"HOLD","SINGLE_TRANSFER","TRANSFER","MULTI_TRANSFER","HIT","WILDCARD","FREE_HIT","BENCH_BOOST","TRIPLE_CAPTAIN"}:
            raise DecisionContractError("intelligence.action is invalid")
        confidence = intelligence.get("confidence")
        if not isinstance(confidence, Mapping):
            raise DecisionContractError("intelligence.confidence must be a mapping")
        score = confidence.get("score")
        if confidence.get("label") not in {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}:
            raise DecisionContractError("intelligence.confidence.label is invalid")
        # An unknown confidence has no score; a known one is in [0, 1].
        if score is None:
            if confidence.get("label") != "UNKNOWN":
                raise DecisionContractError("intelligence.confidence.score is required unless UNKNOWN")
        elif not 0 <= float(score) <= 1:
            raise DecisionContractError("intelligence.confidence.score must be between 0 and 1")
    return dict(result)
