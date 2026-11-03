from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


DashboardTimeRange = Literal['24h', '7d', '30d']


class StrictModel(BaseModel):
    class Config:
        extra = 'forbid'


class AdminStatsTrendPayload(StrictModel):
    labels: list[str] = Field(default_factory=list)
    total_requests: list[int] = Field(default_factory=list)
    failed_requests: list[int] = Field(default_factory=list)
    rate_limited_requests: list[int] = Field(default_factory=list)
    model_requests: dict[str, list[int]] = Field(default_factory=dict)
    model_ttfb_times: dict[str, list[float]] = Field(default_factory=dict)
    model_total_times: dict[str, list[float]] = Field(default_factory=dict)


class AdminStatsPayload(StrictModel):
    total_accounts: int
    active_accounts: int
    failed_accounts: int
    rate_limited_accounts: int
    idle_accounts: int
    success_count: int
    failed_count: int
    trend: AdminStatsTrendPayload


for model in (AdminStatsTrendPayload, AdminStatsPayload):
    model.model_rebuild()
