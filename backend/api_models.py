from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class AreaErrorModel(BaseModel):
    area: str
    message: str


class EnvelopeMetaModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    event: int | None = None
    generated_at: str | None = None
    degraded: bool | None = None
    source: Literal["live", "official", "model", "derived"] | None = None
    fetched_at: str | None = None
    stale: bool | None = None
    version: str | None = None


class DashboardTeamModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    team_id: int
    name: str
    manager_name: str | None = None
    bank: float | None = None
    event: int | None = None
    transfers: int | None = None
    picks: list[dict[str, Any]]


class DashboardDataModel(BaseModel):
    team: DashboardTeamModel
    live: dict[str, Any] | None
    history: dict[str, Any] | None
    fixtures: dict[str, Any] | None
    players: dict[str, Any] | None
    decision: dict[str, Any] | None


class DashboardEnvelopeModel(BaseModel):
    data: DashboardDataModel
    meta: EnvelopeMetaModel
    errors: list[AreaErrorModel]


class StatusDataModel(BaseModel):
    official: dict[str, Any] | None
    model: dict[str, Any] | None
    service_state: Literal["ready", "degraded", "unavailable"]
    artifacts: dict[str, Any]


class StatusEnvelopeModel(BaseModel):
    data: StatusDataModel
    meta: dict[str, EnvelopeMetaModel]
    errors: list[AreaErrorModel]


class FlexibleEnvelopeModel(BaseModel):
    data: dict[str, Any]
    meta: EnvelopeMetaModel
    errors: list[AreaErrorModel]


class PlanEnvelopeModel(FlexibleEnvelopeModel):
    pass


class PlayerEnvelopeModel(FlexibleEnvelopeModel):
    pass


class FixtureEnvelopeModel(FlexibleEnvelopeModel):
    pass


class FixtureMatrixEnvelopeModel(FlexibleEnvelopeModel):
    pass


class ReviewEnvelopeModel(FlexibleEnvelopeModel):
    pass
