from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from math import isfinite
from statistics import median
from typing import Iterable

from app.core.plan_types import is_pro_family_plan
from app.modules.dashboard import coverage_work as _coverage_work
from app.modules.dashboard.coverage_schemas import (
    CoverageAccountResponse,
    CoverageInterval,
    WeeklyCoverageResponse,
)
from app.modules.dashboard.coverage_types import (
    AccountCalibration,
    CapacityObservation,
    CoverageAccountStatus,
    CoverageIntervalState,
    CoverageQuotaPaceStatus,
    CoverageWorkBucket,
    WeeklyCoverageAccountInput,
    WeeklyQuotaSample,
)

estimate_work_units = _coverage_work.estimate_work_units

WEEKLY_WINDOW_MINUTES = 7 * 24 * 60
DEFAULT_HORIZON = timedelta(days=14)
MIN_PERCENT_DROP = 2.0
MIN_INTERVAL = timedelta(hours=2)
MIN_EVIDENCE_SPAN = timedelta(hours=6)
MIN_CALIBRATION_ESTIMATES = 3
CALIBRATION_DISPERSION_LIMIT = 0.75
LIMIT_CENSOR_PERCENT = 99.5
RESET_HORIZON_JUMP = timedelta(hours=6)
MIN_REGRESSION_PERCENT = 0.5
MAX_QUOTA_INTERPOLATION_GAP = timedelta(hours=2)
MAX_SIMULATION_STEP_HOURS = 1.0
DEFAULT_RELATIVE_AVAILABILITY_POWER = 2.0
DEFAULT_RELATIVE_AVAILABILITY_TOP_K = 5
RELATIVE_AVAILABILITY_MIN_WEIGHT_FRACTION = 0.1
EPSILON = 1e-9

ELIGIBLE_STATUSES = frozenset({"active", "rate_limited", "quota_exceeded"})
SUPPORTED_ROUTING_STRATEGIES = frozenset(
    {
        "reset_drain",
        "capacity_weighted",
        "relative_availability",
        "round_robin",
        "sequential_drain",
        "single_account",
    }
)

WARNING_STICKY_MODEL_APPROXIMATION = "sticky_and_model_eligibility_approximation"
WARNING_ROUTING_APPROXIMATION = "routing_allocation_approximation"
WARNING_UNSUPPORTED_ROUTING = "unsupported_routing_strategy"
WARNING_INSUFFICIENT_CALIBRATION = "insufficient_calibration"
WARNING_UNSTABLE_CALIBRATION = "unstable_calibration"
WARNING_STALE_USAGE = "stale_usage"
WARNING_EXTERNAL_DRAWDOWN = "external_or_unexplained_drawdown"
WARNING_INCOMPLETE_WORK = "incomplete_work_history"
WARNING_CENSORED_LIMIT = "quota_limit_censoring"
WARNING_QUOTA_REGRESSION = "quota_regression_reset"
WARNING_PRIMARY_RESET_PREFERENCE = "primary_reset_preference_not_supported_for_weekly_forecast"
WARNING_WEEKLY_WINDOW_SUPERSEDED = "weekly_window_superseded"
WARNING_INVALID_SINGLE_ACCOUNT = "invalid_single_account_selection"
WARNING_PRIOR_CAPACITY_REUSED = "prior_capacity_reused"


@dataclass(slots=True)
class _PreparedAccount:
    account: WeeklyCoverageAccountInput
    calibration: AccountCalibration
    remaining_percent: float | None
    reset_at: datetime | None
    quota_pace_status: CoverageQuotaPaceStatus = "unavailable"
    used_percent_per_day: float | None = None
    projected_exhaustion_at: datetime | None = None
    projected_remaining_at_reset: float | None = None
    included: bool = True
    simulation: _SimulationAccount | None = None


@dataclass(slots=True)
class _SimulationAccount:
    account_id: str
    capacity_work_units: float
    balance_work_units: float
    next_reset: datetime
    window: timedelta
    routing_policy: str
    transitions: list[tuple[datetime, CoverageIntervalState]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _WorkTotal:
    work_units: float
    incomplete: bool


@dataclass(frozen=True, slots=True)
class _SimulationResult:
    account_intervals: dict[str, list[CoverageInterval]]
    pool_intervals: list[CoverageInterval]
    minimum_balance: float
    minimum_at: datetime


def build_weekly_coverage(
    accounts: list[WeeklyCoverageAccountInput],
    now: datetime,
    routing_strategy: str,
    freshness_seconds: float,
    *,
    prefer_earlier_reset_accounts: bool = False,
    single_account_id: str | None = None,
    prefer_earlier_reset_window: str = "secondary",
    relative_availability_power: float = DEFAULT_RELATIVE_AVAILABILITY_POWER,
    relative_availability_top_k: int = DEFAULT_RELATIVE_AVAILABILITY_TOP_K,
) -> WeeklyCoverageResponse:
    """Build an observational weekly-quota coverage forecast.

    The function is intentionally pure. Repository code supplies bounded quota
    samples and hourly request buckets; this function calibrates each account,
    estimates current-window demand from the observed percentage, and simulates
    future staggered resets. It never changes routing or persists a learned
    capacity.
    """

    now_utc = _utc_naive(now)
    horizon_at = now_utc + DEFAULT_HORIZON
    warnings: list[str] = [WARNING_STICKY_MODEL_APPROXIMATION, WARNING_ROUTING_APPROXIMATION]
    if routing_strategy not in SUPPORTED_ROUTING_STRATEGIES:
        _append_warning(warnings, WARNING_UNSUPPORTED_ROUTING)
    weekly_reset_preference_supported = (
        routing_strategy != "capacity_weighted" or prefer_earlier_reset_window == "secondary"
    )
    if prefer_earlier_reset_accounts and not weekly_reset_preference_supported:
        _append_warning(warnings, WARNING_PRIMARY_RESET_PREFERENCE)

    selected_account_id: str | None = None
    invalid_single_account_selection = False
    if routing_strategy == "single_account":
        candidate = (single_account_id or "").strip()
        if candidate and any(_eligible_for_single_account(account, candidate) for account in accounts):
            selected_account_id = candidate
        else:
            # The proxy fails closed when single-account routing is not
            # configured or points at an unavailable account. The forecast
            # must not quietly simulate the whole pool in that situation.
            invalid_single_account_selection = True
            _append_warning(warnings, WARNING_INVALID_SINGLE_ACCOUNT)
    prepared: list[_PreparedAccount] = []
    for account in accounts:
        exclusion_reason = _excluded_reason(account, selected_account_id)
        if exclusion_reason is not None:
            prepared.append(
                _PreparedAccount(
                    account=account,
                    calibration=_empty_calibration(account.account_id, "excluded", exclusion_reason),
                    remaining_percent=None,
                    reset_at=None,
                    included=False,
                )
            )
            continue

        calibration = _calibrate_account(account, now_utc, freshness_seconds)
        if calibration.external_drawdown_suspected:
            _append_warning(warnings, WARNING_EXTERNAL_DRAWDOWN)
        if calibration.incomplete_work_history:
            _append_warning(warnings, WARNING_INCOMPLETE_WORK)
        if calibration.quota_regression_detected:
            _append_warning(warnings, WARNING_QUOTA_REGRESSION)
        if calibration.reused_prior_observation_count > 0:
            _append_warning(warnings, WARNING_PRIOR_CAPACITY_REUSED)
        if calibration.reason == WARNING_STALE_USAGE:
            _append_warning(warnings, WARNING_STALE_USAGE)
        elif calibration.reason == WARNING_INSUFFICIENT_CALIBRATION:
            _append_warning(warnings, WARNING_INSUFFICIENT_CALIBRATION)
        elif calibration.reason == WARNING_UNSTABLE_CALIBRATION:
            _append_warning(warnings, WARNING_UNSTABLE_CALIBRATION)
        if calibration.censored_at_limit:
            _append_warning(warnings, WARNING_CENSORED_LIMIT)

        latest = calibration.current_sample
        remaining_percent = None
        reset_at = None
        if latest is not None:
            remaining_percent = _clamp(100.0 - latest.used_percent, 0.0, 100.0)
            reset_at = _utc_naive(latest.reset_at) if latest.reset_at is not None else None
        pace_status, used_percent_per_day, projected_exhaustion_at, projected_remaining_at_reset = (
            _independent_quota_pace(calibration, now_utc, freshness_seconds)
        )
        prepared.append(
            _PreparedAccount(
                account=account,
                calibration=calibration,
                remaining_percent=remaining_percent,
                reset_at=reset_at,
                quota_pace_status=pace_status,
                used_percent_per_day=used_percent_per_day,
                projected_exhaustion_at=projected_exhaustion_at,
                projected_remaining_at_reset=projected_remaining_at_reset,
            )
        )

    included = [entry for entry in prepared if entry.included]
    if not included:
        _append_warning(warnings, "no_eligible_accounts")
        return WeeklyCoverageResponse(
            status="no_eligible_accounts",
            generated_at=now_utc,
            horizon_at=horizon_at,
            pace_basis="current_window_average",
            routing_strategy=routing_strategy,
            warnings=warnings,
            accounts=[_account_response(entry) for entry in prepared],
            intervals=[],
            minimum_reserve_hours=None,
            minimum_reserve_at=None,
        )

    if invalid_single_account_selection:
        overall_status = "limited"
    elif routing_strategy not in SUPPORTED_ROUTING_STRATEGIES or (
        prefer_earlier_reset_accounts and not weekly_reset_preference_supported
    ):
        overall_status = "limited"
    elif all(entry.calibration.state == "learning" for entry in included):
        overall_status = "learning"
    elif any(entry.calibration.state in {"learning", "limited"} for entry in included):
        overall_status = "limited"
    else:
        overall_status = "ready"

    # A whole-pool result cannot be safely simulated from a partial set of
    # capacities. We still expose each account's evidence, but withhold the
    # timeline until every included account has a current-regime estimate.
    can_simulate = (
        not invalid_single_account_selection
        and overall_status == "ready"
        and all(
            entry.calibration.capacity_work_units is not None
            and entry.calibration.current_sample is not None
            and entry.calibration.current_window_start is not None
            and entry.calibration.demand_work_units_per_hour is not None
            for entry in included
        )
    )
    simulation_result: _SimulationResult | None = None
    if can_simulate and routing_strategy in SUPPORTED_ROUTING_STRATEGIES:
        simulation_accounts = _build_simulation_accounts(included, now_utc)
        if simulation_accounts:
            simulation_result = _simulate(
                simulation_accounts,
                now=now_utc,
                horizon=horizon_at,
                demand_work_units_per_hour=sum(
                    entry.calibration.demand_work_units_per_hour or 0.0 for entry in included
                ),
                routing_strategy=routing_strategy,
                prefer_earlier_reset_accounts=prefer_earlier_reset_accounts and weekly_reset_preference_supported,
                relative_availability_power=relative_availability_power,
                relative_availability_top_k=relative_availability_top_k,
            )

    responses: list[CoverageAccountResponse] = []
    for entry in prepared:
        intervals = []
        if simulation_result is not None:
            intervals = simulation_result.account_intervals.get(entry.account.account_id, [])
        responses.append(_account_response(entry, intervals=intervals))

    minimum_reserve_hours = None
    minimum_reserve_at = None
    pool_intervals: list[CoverageInterval] = []
    if simulation_result is not None:
        pool_intervals = simulation_result.pool_intervals
        minimum_reserve_at = simulation_result.minimum_at
        demand_rate = sum(entry.calibration.demand_work_units_per_hour or 0.0 for entry in included)
        if demand_rate > EPSILON:
            minimum_reserve_hours = max(0.0, simulation_result.minimum_balance / demand_rate)
        elif simulation_result.minimum_balance <= EPSILON:
            # An all-empty pool is an immediate gap even when the measured
            # current-window pace is zero.
            minimum_reserve_hours = 0.0

    return WeeklyCoverageResponse(
        status=overall_status,
        generated_at=now_utc,
        horizon_at=horizon_at,
        pace_basis="current_window_average",
        routing_strategy=routing_strategy,
        warnings=warnings,
        accounts=responses,
        intervals=pool_intervals,
        minimum_reserve_hours=minimum_reserve_hours,
        minimum_reserve_at=minimum_reserve_at,
    )


def _calibrate_account(
    account: WeeklyCoverageAccountInput,
    now: datetime,
    freshness_seconds: float,
) -> AccountCalibration:
    samples = sorted(
        (_normalized_sample(sample) for sample in account.quota_history),
        key=lambda sample: sample.recorded_at,
    )
    samples = [sample for sample in samples if sample.recorded_at <= now]
    if account.weekly_unavailable_reason:
        return _empty_calibration(account.account_id, "limited", account.weekly_unavailable_reason)
    if not samples:
        return _empty_calibration(account.account_id, "learning", WARNING_INSUFFICIENT_CALIBRATION)

    latest = samples[-1]
    if latest.reset_at is None or latest.window_minutes != WEEKLY_WINDOW_MINUTES:
        return _calibration_without_capacity(account.account_id, latest, "limited", "missing_weekly_window")

    reset_at = _utc_naive(latest.reset_at)
    window = timedelta(minutes=latest.window_minutes)
    if reset_at <= now:
        return _calibration_without_capacity(account.account_id, latest, "limited", "weekly_reset_elapsed")
    current_window_start = reset_at - window
    if latest.recorded_at <= current_window_start:
        return _calibration_without_capacity(account.account_id, latest, "limited", "invalid_weekly_window")

    # Keep the latest window separate from older scheduled windows. A reset or
    # quota-counter regression may discard an interval, but it must not erase
    # clean observations from the same or a compatible earlier regime.
    current_samples = [
        sample
        for sample in samples
        if sample.recorded_at >= current_window_start and sample.window_minutes == WEEKLY_WINDOW_MINUTES
    ]
    current_samples, quota_regression_detected = _current_regime_samples(current_samples)
    prior_samples = [
        sample
        for sample in samples
        if sample.recorded_at < current_window_start and sample.window_minutes == WEEKLY_WINDOW_MINUTES
    ]
    prior_segments = _calibration_segments(prior_samples)

    fresh = (now - latest.recorded_at).total_seconds() <= max(0.0, freshness_seconds)
    current_observations: list[CapacityObservation] = []
    prior_segment_observations: list[tuple[list[WeeklyQuotaSample], list[CapacityObservation]]] = []
    external_drawdown = False
    incomplete_work = False
    censored = any(sample.used_percent >= LIMIT_CENSOR_PERCENT for sample in current_samples)
    discarded_interval_count = 0

    def collect_segment(segment: list[WeeklyQuotaSample], *, is_current: bool) -> None:
        nonlocal censored, discarded_interval_count, external_drawdown, incomplete_work
        segment_observations: list[CapacityObservation] = []
        for start_edge, end_edge, start_percent, end_percent in _calibration_blocks(segment):
            delta_percent = end_percent - start_percent
            if end_percent >= LIMIT_CENSOR_PERCENT:
                censored = True
                discarded_interval_count += 1
                continue

            total = _work_between(account.work_buckets, start_edge, end_edge)
            if total.incomplete:
                incomplete_work = True
                discarded_interval_count += 1
                continue
            if total.work_units <= EPSILON:
                # Positive quota movement with no attributable work is evidence
                # outside this proxy. It is a discarded interval, not a zero
                # demand estimate and not a veto when other clean evidence is
                # sufficient.
                external_drawdown = True
                discarded_interval_count += 1
                continue
            capacity_value = total.work_units * 100.0 / delta_percent
            if not isfinite(capacity_value) or capacity_value <= EPSILON:
                discarded_interval_count += 1
                continue
            segment_observations.append(
                CapacityObservation(
                    start_at=start_edge,
                    end_at=end_edge,
                    work_units=total.work_units,
                    observed_drop_percent=delta_percent,
                    capacity_work_units=capacity_value,
                )
            )
        if is_current:
            current_observations.extend(segment_observations)
        else:
            prior_segment_observations.append((segment, segment_observations))

    for segment in prior_segments:
        collect_segment(segment, is_current=False)
    if current_samples:
        collect_segment(current_samples, is_current=True)

    capacities = [observation.capacity_work_units for observation in current_observations]
    current_anchor = float(median(capacities)) if capacities else None
    compatible_prior: list[CapacityObservation] = []
    if current_anchor is not None and not quota_regression_detected and not _has_unexpected_regression(prior_samples):
        for segment, segment_observations in reversed(prior_segment_observations):
            if not _ordinary_scheduled_reset(segment, current_samples, current_window_start):
                continue
            prior_capacities = [observation.capacity_work_units for observation in segment_observations]
            if len(prior_capacities) < MIN_CALIBRATION_ESTIMATES:
                continue
            prior_capacity = float(median(prior_capacities))
            prior_dispersion = _robust_dispersion(prior_capacities, prior_capacity)
            if prior_dispersion is None or prior_dispersion > CALIBRATION_DISPERSION_LIMIT:
                continue
            if abs(prior_capacity - current_anchor) / current_anchor > 0.25:
                continue
            compatible_prior = segment_observations
            break
    usable_observations = [*current_observations, *compatible_prior] if current_observations else []
    capacity_values = [observation.capacity_work_units for observation in usable_observations]
    capacity = float(median(capacity_values)) if capacity_values else None
    dispersion = _robust_dispersion(capacity_values, capacity) if capacity is not None else None
    evidence_span = (
        max(observation.end_at for observation in usable_observations)
        - min(observation.start_at for observation in usable_observations)
        if usable_observations
        else timedelta(0)
    )
    observed_drop = _observed_drop(current_samples)
    if not fresh:
        state = "limited"
        reason = WARNING_STALE_USAGE
    elif capacity is None:
        state = "limited" if (external_drawdown or incomplete_work) else "learning"
        reason = (
            WARNING_EXTERNAL_DRAWDOWN
            if external_drawdown
            else WARNING_INCOMPLETE_WORK
            if incomplete_work
            else WARNING_INSUFFICIENT_CALIBRATION
        )
    elif len(usable_observations) < MIN_CALIBRATION_ESTIMATES or evidence_span < MIN_EVIDENCE_SPAN:
        state = "learning"
        reason = WARNING_INSUFFICIENT_CALIBRATION
    elif dispersion is not None and dispersion > CALIBRATION_DISPERSION_LIMIT:
        state = "limited"
        reason = WARNING_UNSTABLE_CALIBRATION
    else:
        # Discarded intervals remain visible through diagnostics/warnings, but
        # clean, stable evidence is sufficient to calibrate the account.
        state = "ready"
        reason = None

    elapsed_hours = (latest.recorded_at - current_window_start).total_seconds() / 3600.0
    demand = None
    remaining = None
    if capacity is not None and elapsed_hours > EPSILON:
        demand = capacity * _clamp(latest.used_percent, 0.0, 100.0) / 100.0 / elapsed_hours
        remaining = capacity * _clamp(100.0 - latest.used_percent, 0.0, 100.0) / 100.0

    return AccountCalibration(
        account_id=account.account_id,
        state=state,
        capacity_work_units=capacity,
        sample_count=len(usable_observations),
        observed_drop_percent=observed_drop,
        latest_observation_at=latest.recorded_at,
        dispersion=dispersion,
        external_drawdown_suspected=external_drawdown,
        incomplete_work_history=incomplete_work,
        censored_at_limit=censored,
        quota_regression_detected=quota_regression_detected,
        current_sample=latest,
        current_window_start=current_window_start,
        demand_work_units_per_hour=demand,
        remaining_work_units=remaining,
        reason=reason,
        observations=tuple(usable_observations),
        discarded_interval_count=discarded_interval_count,
        reused_prior_observation_count=len(compatible_prior),
    )


def _current_regime_samples(
    samples: list[WeeklyQuotaSample],
) -> tuple[list[WeeklyQuotaSample], bool]:
    """Return the suffix of samples belonging to the current weekly window.

    A reset timestamp can move slightly between upstream responses, so small
    jitter is tolerated. A meaningful counter regression always starts a new
    regime. A larger reset-horizon movement starts one only when it is
    coherent with a material quota drop; a deadline can otherwise drift while
    the same quota window is being reported. The caller already bounded this
    suffix to the latest weekly window.
    """

    if not samples:
        return [], False
    current = samples[-1]
    suffix = [current]
    regression_detected = False
    for previous in reversed(samples[:-1]):
        if _is_reset_boundary(previous, current):
            if current.used_percent < previous.used_percent - MIN_REGRESSION_PERCENT:
                regression_detected = True
            break
        suffix.append(previous)
        current = previous
    suffix.reverse()
    return suffix, regression_detected


def _calibration_segments(samples: list[WeeklyQuotaSample]) -> list[list[WeeklyQuotaSample]]:
    """Split retained weekly samples at reset/regression boundaries."""

    if not samples:
        return []
    segments: list[list[WeeklyQuotaSample]] = [[samples[0]]]
    for previous, current in zip(samples[:-1], samples[1:], strict=True):
        if _is_reset_boundary(previous, current):
            segments.append([current])
        else:
            segments[-1].append(current)
    return segments


def _ordinary_scheduled_reset(
    prior_segment: list[WeeklyQuotaSample],
    current_samples: list[WeeklyQuotaSample],
    current_window_start: datetime,
) -> bool:
    """Whether a prior segment meets the evidence needed for rolling reuse."""

    if not prior_segment or not current_samples:
        return False
    prior_reset = prior_segment[-1].reset_at
    current_reset = current_samples[-1].reset_at
    if prior_reset is None or current_reset is None:
        return False
    expected_window = timedelta(minutes=WEEKLY_WINDOW_MINUTES)
    reset_delta = _utc_naive(current_reset) - _utc_naive(prior_reset)
    if abs(reset_delta - expected_window) > RESET_HORIZON_JUMP:
        return False

    prior_end_gap = current_window_start - prior_segment[-1].recorded_at
    current_start_gap = current_samples[0].recorded_at - current_window_start
    return (
        timedelta(0) <= prior_end_gap <= MAX_QUOTA_INTERPOLATION_GAP
        and timedelta(0) <= current_start_gap <= MAX_QUOTA_INTERPOLATION_GAP
    )


def _has_unexpected_regression(samples: list[WeeklyQuotaSample]) -> bool:
    """Detect a decrease that is not explained by an ordinary weekly reset."""

    for previous, current in zip(samples[:-1], samples[1:], strict=True):
        if current.used_percent >= previous.used_percent - MIN_REGRESSION_PERCENT:
            continue
        if _ordinary_reset_pair(previous, current):
            continue
        return True
    return False


def _ordinary_reset_pair(previous: WeeklyQuotaSample, current: WeeklyQuotaSample) -> bool:
    if previous.reset_at is None or current.reset_at is None:
        return False
    expected_window = timedelta(minutes=WEEKLY_WINDOW_MINUTES)
    reset_delta = _utc_naive(current.reset_at) - _utc_naive(previous.reset_at)
    if abs(reset_delta - expected_window) > RESET_HORIZON_JUMP:
        return False
    boundary = _utc_naive(current.reset_at) - expected_window
    return (
        previous.recorded_at <= boundary <= current.recorded_at
        and current.recorded_at - previous.recorded_at <= MAX_QUOTA_INTERPOLATION_GAP
    )


def _is_reset_boundary(previous: WeeklyQuotaSample, current: WeeklyQuotaSample) -> bool:
    if previous.window_minutes != current.window_minutes:
        return True
    if previous.reset_at is None or current.reset_at is None:
        return True
    usage_drop = previous.used_percent - current.used_percent
    if usage_drop >= MIN_REGRESSION_PERCENT:
        return True
    reset_jump = _utc_naive(current.reset_at) - _utc_naive(previous.reset_at)
    return abs(reset_jump) >= RESET_HORIZON_JUMP and usage_drop >= MIN_PERCENT_DROP


def _calibration_blocks(
    samples: list[WeeklyQuotaSample],
) -> list[tuple[datetime, datetime, float, float]]:
    """Build disjoint multi-hour quota blocks on complete-hour work edges."""
    if len(samples) < 2:
        return []
    first_edge = _ceil_hour(samples[0].recorded_at)
    last_edge = _floor_hour(samples[-1].recorded_at)
    if first_edge >= last_edge:
        return []

    edges: list[datetime] = []
    cursor = first_edge
    while cursor <= last_edge:
        edges.append(cursor)
        cursor += timedelta(hours=1)

    timestamps = [sample.recorded_at for sample in samples]
    values = [_interpolate_percent(samples, timestamps, edge) for edge in edges]
    observations: list[tuple[datetime, datetime, float, float]] = []
    minimum_hours = max(1, int(MIN_INTERVAL.total_seconds() // 3600))
    run_start = 0
    while run_start < len(edges):
        while run_start < len(edges) and values[run_start] is None:
            run_start += 1
        run_end = run_start
        while run_end < len(edges) and values[run_end] is not None:
            run_end += 1
        start_index = run_start
        while start_index + minimum_hours < run_end:
            start_percent = values[start_index]
            assert start_percent is not None
            found = False
            for end_index in range(start_index + minimum_hours, run_end):
                end_percent = values[end_index]
                assert end_percent is not None
                delta_percent = end_percent - start_percent
                if delta_percent + EPSILON < MIN_PERCENT_DROP:
                    continue
                observations.append((edges[start_index], edges[end_index], start_percent, end_percent))
                start_index = end_index
                found = True
                break
            if not found:
                break
        run_start = run_end
    return observations


def _interpolate_percent(
    samples: list[WeeklyQuotaSample],
    timestamps: list[datetime],
    at: datetime,
) -> float | None:
    index = bisect_left(timestamps, at)
    if index < len(samples) and samples[index].recorded_at == at:
        return samples[index].used_percent
    before = samples[index - 1] if index > 0 else None
    after = samples[index] if index < len(samples) else None
    if before is None or after is None:
        return None
    span = (after.recorded_at - before.recorded_at).total_seconds()
    if span <= 0.0 or span > MAX_QUOTA_INTERPOLATION_GAP.total_seconds():
        return None
    fraction = (at - before.recorded_at).total_seconds() / span
    return before.used_percent + (after.used_percent - before.used_percent) * fraction


def _build_simulation_accounts(
    entries: Iterable[_PreparedAccount],
    now: datetime,
) -> list[_SimulationAccount]:
    result: list[_SimulationAccount] = []
    for entry in entries:
        calibration = entry.calibration
        sample = calibration.current_sample
        capacity = calibration.capacity_work_units
        if sample is None or capacity is None or sample.reset_at is None or sample.window_minutes is None:
            continue
        window = timedelta(minutes=sample.window_minutes)
        reset_at = _next_reset_after(_utc_naive(sample.reset_at), window, now)
        balance = capacity * _clamp(100.0 - sample.used_percent, 0.0, 100.0) / 100.0
        result.append(
            _SimulationAccount(
                account_id=entry.account.account_id,
                capacity_work_units=capacity,
                balance_work_units=balance,
                next_reset=reset_at,
                window=window,
                routing_policy=entry.account.routing_policy,
                transitions=[(now, "available" if balance > EPSILON else "exhausted")],
            )
        )
    return result


def _simulate(
    accounts: list[_SimulationAccount],
    *,
    now: datetime,
    horizon: datetime,
    demand_work_units_per_hour: float,
    routing_strategy: str,
    prefer_earlier_reset_accounts: bool,
    relative_availability_power: float,
    relative_availability_top_k: int,
) -> _SimulationResult:
    cursor = now
    pool_segments: list[CoverageInterval] = []
    minimum_balance = _total_balance(accounts)
    minimum_at = now

    while cursor < horizon:
        next_reset = min(account.next_reset for account in accounts)
        segment_end = min(next_reset, horizon)
        if segment_end <= cursor:
            _apply_resets(accounts, cursor)
            continue

        remaining_segment_hours = (segment_end - cursor).total_seconds() / 3600.0
        remaining_hours = remaining_segment_hours
        while remaining_hours > EPSILON:
            pool_state = "available" if _has_routable_balance(accounts) else "exhausted"
            if pool_state == "exhausted" or demand_work_units_per_hour <= EPSILON:
                _append_interval(pool_segments, cursor, segment_end, pool_state)
                cursor = segment_end
                remaining_hours = 0.0
                break

            shares = _allocation_shares(
                accounts,
                at=cursor,
                routing_strategy=routing_strategy,
                prefer_earlier_reset_accounts=prefer_earlier_reset_accounts,
                relative_availability_power=relative_availability_power,
                relative_availability_top_k=relative_availability_top_k,
            )
            if not shares:
                _append_interval(pool_segments, cursor, segment_end, "exhausted")
                cursor = segment_end
                remaining_hours = 0.0
                break
            time_to_exhaust_hours = min(
                account.balance_work_units / (demand_work_units_per_hour * share)
                for account, share in shares
                if share > EPSILON
            )
            step_hours = min(remaining_hours, time_to_exhaust_hours, MAX_SIMULATION_STEP_HOURS)
            step_end = cursor + timedelta(hours=step_hours)
            _append_interval(pool_segments, cursor, step_end, "available")
            consumed = demand_work_units_per_hour * step_hours
            for account, share in shares:
                account.balance_work_units = max(
                    0.0,
                    account.balance_work_units - consumed * share,
                )
            cursor = step_end
            remaining_hours -= step_hours

            for account in accounts:
                if account.balance_work_units <= EPSILON and not _last_state(account, "exhausted"):
                    account.balance_work_units = 0.0
                    account.transitions.append((cursor, "exhausted"))
            current_balance = _total_balance(accounts)
            if current_balance < minimum_balance - EPSILON:
                minimum_balance = current_balance
                minimum_at = cursor

        # datetime rounds fractional exhaustion times to microseconds. Close
        # any sub-microsecond remainder before the next reset/horizon event.
        # Demand still transfers normally after even a tiny account empties.
        if cursor < segment_end and remaining_hours <= EPSILON:
            state = "available" if _has_routable_balance(accounts) else "exhausted"
            _append_interval(pool_segments, cursor, segment_end, state)
            cursor = segment_end
        if cursor >= horizon:
            break
        _apply_resets(accounts, cursor)
        current_balance = _total_balance(accounts)
        if current_balance < minimum_balance - EPSILON:
            minimum_balance = current_balance
            minimum_at = cursor

    return _SimulationResult(
        account_intervals={
            account.account_id: _build_account_intervals(account.transitions, now, horizon) for account in accounts
        },
        pool_intervals=_merge_intervals(pool_segments),
        minimum_balance=max(0.0, minimum_balance),
        minimum_at=minimum_at,
    )


def _allocation_shares(
    accounts: list[_SimulationAccount],
    *,
    at: datetime,
    routing_strategy: str,
    prefer_earlier_reset_accounts: bool,
    relative_availability_power: float,
    relative_availability_top_k: int,
) -> list[tuple[_SimulationAccount, float]]:
    available = [account for account in accounts if account.balance_work_units > EPSILON]
    if not available:
        return []
    if routing_strategy not in {"reset_drain", "sequential_drain", "single_account"}:
        available = _effective_policy_pool(available)
    if prefer_earlier_reset_accounts and routing_strategy == "capacity_weighted":
        earliest_reset = min(account.next_reset for account in available)
        earliest_day = int(max(0.0, (earliest_reset - at).total_seconds()) // timedelta(days=1).total_seconds())
        reset_candidates = [
            account
            for account in available
            if int(max(0.0, (account.next_reset - at).total_seconds()) // timedelta(days=1).total_seconds())
            == earliest_day
        ]
        if reset_candidates:
            available = reset_candidates

    if routing_strategy == "single_account":
        selected = min(available, key=lambda account: account.account_id)
        return [(selected, 1.0)]
    if routing_strategy in {"reset_drain", "sequential_drain"}:
        if routing_strategy == "reset_drain":
            selected = min(
                available,
                key=lambda account: (
                    int(max(0.0, (account.next_reset - at).total_seconds()) // timedelta(days=1).total_seconds()),
                    -_remaining_fraction(account),
                    account.next_reset,
                    account.account_id,
                ),
            )
        else:
            selected = min(available, key=lambda account: (_remaining_fraction(account), account.account_id))
        return [(selected, 1.0)]
    if routing_strategy == "relative_availability":
        weights = [
            _remaining_fraction(account) / max((account.next_reset - at).total_seconds(), 5 * 60)
            for account in available
        ]
        best_weight = max(weights, default=0.0)
        safe_power = (
            relative_availability_power if relative_availability_power > 0.0 else DEFAULT_RELATIVE_AVAILABILITY_POWER
        )
        weighted = []
        for account, weight in zip(available, weights, strict=True):
            if best_weight <= EPSILON:
                continue
            normalized_score = max(0.0, weight) / best_weight
            candidate_weight = normalized_score**safe_power
            if candidate_weight >= RELATIVE_AVAILABILITY_MIN_WEIGHT_FRACTION:
                weighted.append((account, candidate_weight))
        weighted.sort(key=lambda item: (-item[1], item[0].account_id))
        safe_top_k = max(1, relative_availability_top_k)
        available = [account for account, _ in weighted[:safe_top_k]]
        weights = [weight for _, weight in weighted[:safe_top_k]]
    elif routing_strategy == "round_robin":
        weights = [1.0 for _ in available]
    else:  # capacity_weighted
        weights = [_remaining_fraction(account) for account in available]
    total = sum(weights)
    if total <= EPSILON:
        return [(account, 1.0 / len(available)) for account in available]
    return [(account, weight / total) for account, weight in zip(available, weights, strict=True) if weight > EPSILON]


def _effective_policy_pool(accounts: list[_SimulationAccount]) -> list[_SimulationAccount]:
    """Keep the highest-priority account policy group used by the selector."""
    for policy in ("burn_first", "normal", "preserve"):
        candidates = [
            account
            for account in accounts
            if (account.routing_policy if account.routing_policy in {"burn_first", "normal", "preserve"} else "normal")
            == policy
        ]
        if candidates:
            return candidates
    return accounts


def _apply_resets(accounts: list[_SimulationAccount], at: datetime) -> None:
    for account in accounts:
        if account.next_reset <= at:
            account.balance_work_units = account.capacity_work_units
            account.transitions.append((at, "available"))
            account.next_reset = _next_reset_after(account.next_reset, account.window, at)


def _build_account_intervals(
    transitions: list[tuple[datetime, CoverageIntervalState]],
    start: datetime,
    end: datetime,
) -> list[CoverageInterval]:
    # Preserve insertion order for simultaneous transitions. A quota reset can
    # happen at the exact instant an account is exhausted; the reset's
    # ``available`` state is appended after the exhaustion state and must win.
    ordered = sorted(transitions, key=lambda item: item[0])
    result: list[CoverageInterval] = []
    state = ordered[0][1] if ordered else "available"
    cursor = start
    for at, next_state in ordered[1:]:
        at = max(start, min(end, at))
        if at > cursor:
            _append_interval(result, cursor, at, state)
        cursor = at
        state = next_state
    if cursor < end:
        _append_interval(result, cursor, end, state)
    return _merge_intervals(result)


def _append_interval(
    intervals: list[CoverageInterval],
    start: datetime,
    end: datetime,
    state: CoverageIntervalState,
) -> None:
    if end <= start:
        return
    intervals.append(CoverageInterval(startAt=start, endAt=end, state=state))


def _merge_intervals(intervals: list[CoverageInterval]) -> list[CoverageInterval]:
    if not intervals:
        return []
    result: list[CoverageInterval] = []
    for interval in sorted(intervals, key=lambda item: item.start_at):
        if result and result[-1].state == interval.state and result[-1].end_at >= interval.start_at:
            result[-1] = CoverageInterval(
                startAt=result[-1].start_at,
                endAt=max(result[-1].end_at, interval.end_at),
                state=interval.state,
            )
        else:
            result.append(interval)
    return result


def _independent_quota_pace(
    calibration: AccountCalibration,
    now: datetime,
    freshness_seconds: float,
) -> tuple[CoverageQuotaPaceStatus, float | None, datetime | None, float | None]:
    """Project one fresh weekly quota window without a work-unit estimate.

    This deliberately uses only the provider's percentage counter. It remains
    useful while pool calibration is learning or limited, but it does not
    imply that traffic can move between accounts.
    """

    sample = calibration.current_sample
    window_start = calibration.current_window_start
    if (
        sample is None
        or window_start is None
        or sample.reset_at is None
        or sample.window_minutes != WEEKLY_WINDOW_MINUTES
        or calibration.reason
        in {
            "missing_weekly_window",
            "weekly_reset_elapsed",
            "invalid_weekly_window",
            WARNING_WEEKLY_WINDOW_SUPERSEDED,
        }
        or calibration.quota_regression_detected
        or (now - sample.recorded_at).total_seconds() > max(0.0, freshness_seconds)
    ):
        return "unavailable", None, None, None

    reset_at = _utc_naive(sample.reset_at)
    if reset_at <= now or sample.recorded_at <= window_start:
        return "unavailable", None, None, None

    used_percent = _clamp(sample.used_percent, 0.0, 100.0)
    elapsed_days = (sample.recorded_at - window_start).total_seconds() / 86_400.0
    if elapsed_days <= EPSILON:
        return "unavailable", None, None, None
    used_per_day = used_percent / elapsed_days
    if used_percent <= EPSILON or used_per_day <= EPSILON:
        return "no_usage", 0.0, None, 100.0

    reset_days = (reset_at - window_start).total_seconds() / 86_400.0
    projected_usage = used_per_day * reset_days
    projected_remaining = _clamp(100.0 - projected_usage, 0.0, 100.0)
    exhaustion_days = 100.0 / used_per_day
    elapsed_now_days = (now - window_start).total_seconds() / 86_400.0
    if used_percent >= 100.0 - EPSILON or exhaustion_days <= elapsed_now_days:
        exhaustion_at = window_start + timedelta(days=min(100.0 / used_per_day, reset_days))
        return "exhausted", used_per_day, exhaustion_at, 0.0
    if exhaustion_days < reset_days - EPSILON:
        exhaustion_at = window_start + timedelta(days=exhaustion_days)
        return "exhausts_before_reset", used_per_day, exhaustion_at, 0.0
    return "lasts_until_reset", used_per_day, None, projected_remaining


def _account_response(
    entry: _PreparedAccount,
    *,
    intervals: list[CoverageInterval] | None = None,
) -> CoverageAccountResponse:
    calibration = entry.calibration
    status = "excluded" if not entry.included else calibration.state
    return CoverageAccountResponse(
        accountId=entry.account.account_id,
        label=entry.account.label or entry.account.account_id,
        planType=entry.account.plan_type,
        status=status,
        reason=calibration.reason if status != "ready" else None,
        remainingPercent=entry.remaining_percent,
        resetAt=entry.reset_at,
        capacityWorkUnits=calibration.capacity_work_units,
        sampleCount=calibration.sample_count,
        observedDropPercent=calibration.observed_drop_percent,
        quotaPaceStatus=entry.quota_pace_status,
        usedPercentPerDay=entry.used_percent_per_day,
        projectedExhaustionAt=entry.projected_exhaustion_at,
        projectedRemainingAtReset=entry.projected_remaining_at_reset,
        diagnostics={
            "discardedIntervalCount": calibration.discarded_interval_count,
            # Retained as an empty compatibility field; pricing no longer gates work.
            "unpricedModels": [],
        },
        intervals=intervals or [],
    )


def _excluded_reason(account: WeeklyCoverageAccountInput, single_account_id: str | None) -> str | None:
    if not is_pro_family_plan(account.plan_type):
        return "plan_not_supported"
    if account.status not in ELIGIBLE_STATUSES:
        return (
            account.status
            if account.status in {"paused", "reauth_required", "deactivated"}
            else "account_status_not_eligible"
        )
    if single_account_id is not None and account.account_id != single_account_id:
        return "single_account_selection"
    return None


def _eligible_for_single_account(account: WeeklyCoverageAccountInput, account_id: str) -> bool:
    return (
        account.account_id == account_id
        and is_pro_family_plan(account.plan_type)
        and account.status in ELIGIBLE_STATUSES
    )


def _empty_calibration(account_id: str, state: CoverageAccountStatus, reason: str | None) -> AccountCalibration:
    return AccountCalibration(
        account_id=account_id,
        state=state,
        capacity_work_units=None,
        sample_count=0,
        observed_drop_percent=0.0,
        latest_observation_at=None,
        dispersion=None,
        reason=reason,
    )


def _calibration_without_capacity(
    account_id: str,
    latest: WeeklyQuotaSample,
    state: CoverageAccountStatus,
    reason: str,
) -> AccountCalibration:
    return AccountCalibration(
        account_id=account_id,
        state=state,
        capacity_work_units=None,
        sample_count=0,
        observed_drop_percent=0.0,
        latest_observation_at=latest.recorded_at,
        dispersion=None,
        current_sample=latest,
        reason=reason,
    )


def _normalized_sample(sample: WeeklyQuotaSample) -> WeeklyQuotaSample:
    return WeeklyQuotaSample(
        recorded_at=_utc_naive(sample.recorded_at),
        used_percent=_clamp(float(sample.used_percent), 0.0, 100.0),
        reset_at=_utc_naive(sample.reset_at) if sample.reset_at is not None else None,
        window_minutes=sample.window_minutes,
    )


def _work_between(
    buckets: Iterable[CoverageWorkBucket],
    start: datetime,
    end: datetime,
) -> _WorkTotal:
    total = 0.0
    incomplete = False
    for bucket in buckets:
        bucket_start = _align_hour_edge(bucket.started_at)
        if bucket_start is None:
            # Only a bucket that falls in the requested interval can make that
            # interval incomplete; unrelated malformed history is harmless.
            raw_start = _utc_naive(bucket.started_at)
            if start <= raw_start < end:
                incomplete = True
            continue
        if bucket_start < start or bucket_start >= end:
            continue
        work = estimate_work_units(bucket)
        if work is None:
            incomplete = True
            continue
        total += work
    return _WorkTotal(work_units=total, incomplete=incomplete)


def _robust_dispersion(values: list[float], center: float | None) -> float | None:
    if not values or center is None or center <= EPSILON:
        return None
    deviations = [abs(value - center) for value in values]
    return float(median(deviations) / center)


def _observed_drop(samples: list[WeeklyQuotaSample]) -> float:
    if not samples:
        return 0.0
    first = samples[0].used_percent
    latest = samples[-1].used_percent
    return _clamp(max(0.0, latest - first), 0.0, 100.0)


def _align_hour_edge(value: datetime) -> datetime | None:
    value = _utc_naive(value)
    if value.minute or value.second or value.microsecond:
        return None
    return value


def _floor_hour(value: datetime) -> datetime:
    value = _utc_naive(value)
    return value.replace(minute=0, second=0, microsecond=0)


def _ceil_hour(value: datetime) -> datetime:
    value = _utc_naive(value)
    floor = _floor_hour(value)
    return floor if value == floor else floor + timedelta(hours=1)


def _next_reset_after(reset_at: datetime, window: timedelta, now: datetime) -> datetime:
    reset_at = _utc_naive(reset_at)
    now = _utc_naive(now)
    if reset_at > now:
        return reset_at
    window_seconds = window.total_seconds()
    if window_seconds <= 0:
        return reset_at
    steps = int((now - reset_at).total_seconds() // window_seconds) + 1
    return reset_at + steps * window


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _total_balance(accounts: Iterable[_SimulationAccount]) -> float:
    return sum(max(0.0, account.balance_work_units) for account in accounts)


def _has_routable_balance(accounts: list[_SimulationAccount]) -> bool:
    return any(account.balance_work_units > EPSILON for account in accounts)


def _remaining_fraction(account: _SimulationAccount) -> float:
    if account.capacity_work_units <= EPSILON:
        return 0.0
    return _clamp(account.balance_work_units / account.capacity_work_units, 0.0, 1.0)


def _last_state(account: _SimulationAccount, state: str) -> bool:
    return bool(account.transitions and account.transitions[-1][1] == state)


def _append_warning(warnings: list[str], warning: str) -> None:
    if warning not in warnings:
        warnings.append(warning)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))
