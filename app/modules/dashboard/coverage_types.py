from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

CoverageAccountStatus = Literal["ready", "learning", "limited", "excluded"]
CoverageIntervalState = Literal["available", "exhausted"]
CoverageQuotaPaceStatus = Literal[
    "unavailable",
    "no_usage",
    "lasts_until_reset",
    "exhausts_before_reset",
    "exhausted",
]


@dataclass(frozen=True, slots=True)
class WeeklyQuotaSample:
    """One observed sample of an account's weekly quota window.

    ``reset_at`` and ``recorded_at`` are kept as datetimes at this boundary so
    the estimator does not need to know how the usage repository stores epoch
    values.  Callers should pass the weekly (secondary) window only.
    """

    recorded_at: datetime
    used_percent: float
    reset_at: datetime | None
    window_minutes: int | None


@dataclass(frozen=True, slots=True)
class CoverageWorkBucket:
    """Hourly measured token work that can be matched to a quota sample interval.

    ``started_at`` is the UTC start of a one-hour bucket.  The repository may
    return multiple rows for the same account/hour when request metadata
    differs.  The estimator sums their additive ``(input + output)`` work;
    model, tier and context metadata do not change the unit.
    """

    account_id: str
    started_at: datetime
    model: str
    service_tier: str | None
    input_tokens: int | None
    output_tokens: int | None
    cached_input_tokens: int | None
    request_count: int
    missing_usage_count: int = 0
    # Retained as nullable compatibility metadata for older callers.  Empirical
    # coverage work does not classify or weight requests by context.
    context_long: bool | None = None
    cache_write_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class WeeklyCoverageAccountInput:
    """Quota and request evidence for one account.

    The service supplies a bounded history covering the current weekly reset
    regime and, when available, a preceding regime for guarded corroboration.
    Older windows are never mixed into calibration unless their capacity scale
    agrees with clean current evidence across an ordinary scheduled reset.
    """

    account_id: str
    label: str
    plan_type: str
    status: str
    quota_history: tuple[WeeklyQuotaSample, ...] = ()
    work_buckets: tuple[CoverageWorkBucket, ...] = ()
    routing_policy: str = "normal"
    weekly_unavailable_reason: str | None = None


@dataclass(frozen=True, slots=True)
class CapacityObservation:
    """One robustly-calibrated work-per-full-window observation."""

    start_at: datetime
    end_at: datetime
    work_units: float
    observed_drop_percent: float
    capacity_work_units: float


@dataclass(frozen=True, slots=True)
class AccountCalibration:
    """Calibration evidence retained for account-level presentation/testing."""

    account_id: str
    state: CoverageAccountStatus
    capacity_work_units: float | None
    sample_count: int
    observed_drop_percent: float
    latest_observation_at: datetime | None
    dispersion: float | None
    external_drawdown_suspected: bool = False
    incomplete_work_history: bool = False
    censored_at_limit: bool = False
    quota_regression_detected: bool = False
    current_sample: WeeklyQuotaSample | None = None
    current_window_start: datetime | None = None
    demand_work_units_per_hour: float | None = None
    remaining_work_units: float | None = None
    reason: str | None = None
    observations: tuple[CapacityObservation, ...] = field(default_factory=tuple)
    discarded_interval_count: int = 0
    # Kept for response compatibility; measured-token work no longer has a
    # pricing-dependent model diagnostic.
    reused_prior_observation_count: int = 0
