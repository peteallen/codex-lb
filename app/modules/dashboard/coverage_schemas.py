from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.modules.dashboard.coverage_types import (
    CoverageAccountStatus,
    CoverageIntervalState,
    CoverageQuotaPaceStatus,
)
from app.modules.shared.schemas import DashboardModel

CoverageForecastStatus = Literal["ready", "learning", "limited", "no_eligible_accounts"]
CoveragePaceBasis = Literal["current_window_average"]


class CoverageInterval(DashboardModel):
    start_at: datetime = Field(alias="startAt")
    end_at: datetime = Field(alias="endAt")
    state: CoverageIntervalState


class CoverageAccountDiagnostics(DashboardModel):
    discarded_interval_count: int = Field(default=0, alias="discardedIntervalCount")
    # Compatibility field; measured token work no longer depends on pricing.
    unpriced_models: list[str] = Field(default_factory=list, alias="unpricedModels")


class CoverageAccountResponse(DashboardModel):
    account_id: str = Field(alias="accountId")
    label: str
    plan_type: str = Field(alias="planType")
    status: CoverageAccountStatus
    reason: str | None = None
    remaining_percent: float | None = Field(default=None, alias="remainingPercent")
    reset_at: datetime | None = Field(default=None, alias="resetAt")
    capacity_work_units: float | None = Field(default=None, alias="capacityWorkUnits")
    sample_count: int = Field(default=0, alias="sampleCount")
    observed_drop_percent: float = Field(default=0.0, alias="observedDropPercent")
    quota_pace_status: CoverageQuotaPaceStatus = Field(default="unavailable", alias="quotaPaceStatus")
    used_percent_per_day: float | None = Field(default=None, alias="usedPercentPerDay")
    projected_exhaustion_at: datetime | None = Field(default=None, alias="projectedExhaustionAt")
    projected_remaining_at_reset: float | None = Field(default=None, alias="projectedRemainingAtReset")
    diagnostics: CoverageAccountDiagnostics = Field(default_factory=CoverageAccountDiagnostics)
    intervals: list[CoverageInterval] = Field(default_factory=list)


class WeeklyCoverageResponse(DashboardModel):
    status: CoverageForecastStatus
    generated_at: datetime = Field(alias="generatedAt")
    horizon_at: datetime = Field(alias="horizonAt")
    pace_basis: CoveragePaceBasis = Field(alias="paceBasis")
    routing_strategy: str = Field(alias="routingStrategy")
    warnings: list[str] = Field(default_factory=list)
    accounts: list[CoverageAccountResponse] = Field(default_factory=list)
    intervals: list[CoverageInterval] = Field(default_factory=list)
    minimum_reserve_hours: float | None = Field(default=None, alias="minimumReserveHours")
    minimum_reserve_at: datetime | None = Field(default=None, alias="minimumReserveAt")
