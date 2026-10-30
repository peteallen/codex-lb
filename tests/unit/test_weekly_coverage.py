from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from app.modules.dashboard.coverage_types import CoverageWorkBucket, WeeklyCoverageAccountInput, WeeklyQuotaSample
from app.modules.dashboard.weekly_coverage import (
    _simulate,
    _SimulationAccount,
    build_weekly_coverage,
    estimate_work_units,
)

BASE = datetime(2026, 1, 5, 0, 0)
RESET = BASE + timedelta(days=7)


def _bucket(account_id: str, started_at: datetime, *, tier: str | None = None) -> CoverageWorkBucket:
    return CoverageWorkBucket(
        account_id=account_id,
        started_at=started_at,
        model="gpt-6.1-sol",
        service_tier=tier,
        input_tokens=1_000_000,
        output_tokens=0,
        cached_input_tokens=0,
        request_count=1,
        context_long=True,
    )


def _account(
    account_id: str = "a",
    *,
    status: str = "active",
    used: tuple[float, ...] = (10.0, 14.0, 18.0, 22.0),
    sample_start: datetime = BASE + timedelta(days=1),
    reset_at: datetime | None = RESET,
    work: bool = True,
    plan_type: str = "pro",
    routing_policy: str = "normal",
) -> WeeklyCoverageAccountInput:
    samples = tuple(
        WeeklyQuotaSample(
            recorded_at=sample_start + timedelta(hours=2 * index),
            used_percent=value,
            reset_at=reset_at,
            window_minutes=10_080,
        )
        for index, value in enumerate(used)
    )
    buckets = (
        tuple(_bucket(account_id, sample_start + timedelta(hours=2 * index)) for index in range(max(0, len(used) - 1)))
        if work
        else ()
    )
    return WeeklyCoverageAccountInput(
        account_id=account_id,
        label=account_id.upper(),
        plan_type=plan_type,
        status=status,
        quota_history=samples,
        work_buckets=buckets,
        routing_policy=routing_policy,
    )


def _rolling_account(
    *,
    prior_input_tokens: int = 1_000_000,
    current_reset: datetime = BASE + timedelta(days=14),
) -> WeeklyCoverageAccountInput:
    prior_start = BASE + timedelta(days=6, hours=17)
    current_start = BASE + timedelta(days=7, hours=1)
    prior_samples = tuple(
        WeeklyQuotaSample(
            recorded_at=prior_start + timedelta(hours=2 * index),
            used_percent=20.0 + 4.0 * index,
            reset_at=BASE + timedelta(days=7),
            window_minutes=10_080,
        )
        for index in range(4)
    )
    current_samples = tuple(
        WeeklyQuotaSample(
            recorded_at=current_start + timedelta(hours=2 * index),
            used_percent=4.0 + 4.0 * index,
            reset_at=current_reset,
            window_minutes=10_080,
        )
        for index in range(4)
    )
    prior_buckets = tuple(
        replace(
            _bucket("rolling", prior_start + timedelta(hours=2 * index)),
            input_tokens=prior_input_tokens,
        )
        for index in range(3)
    )
    current_buckets = tuple(_bucket("rolling", current_start + timedelta(hours=2 * index)) for index in range(3))
    return WeeklyCoverageAccountInput(
        account_id="rolling",
        label="ROLLING",
        plan_type="pro",
        status="active",
        quota_history=prior_samples + current_samples,
        work_buckets=prior_buckets + current_buckets,
    )


@pytest.mark.parametrize("model", ["gpt-6.1-sol", "codex-auto-review", "future-model"])
@pytest.mark.parametrize("tier", [None, "default", "fast", "ultrafast", "future-tier"])
def test_measured_work_is_independent_of_model_price_and_tier(model: str, tier: str | None) -> None:
    bucket = replace(
        _bucket("a", BASE, tier=tier),
        model=model,
        input_tokens=4_000_000,
        output_tokens=1_000_000,
        cached_input_tokens=3_000_000,
        cache_write_tokens=500_000,
        context_long=None,
    )
    assert estimate_work_units(bucket) == pytest.approx(5.0)


def test_five_million_tokens_per_five_points_estimates_one_hundred_million_capacity() -> None:
    account = _account(used=(10, 15, 20, 25))
    account = replace(
        account,
        work_buckets=tuple(
            replace(bucket, model="codex-auto-review", input_tokens=4_000_000, output_tokens=1_000_000)
            for bucket in account.work_buckets
        ),
    )
    response = build_weekly_coverage(
        [account],
        now=BASE + timedelta(days=1, hours=6),
        routing_strategy="capacity_weighted",
        freshness_seconds=3600,
    )
    assert response.status == "ready"
    assert response.accounts[0].capacity_work_units == pytest.approx(100)
    assert response.accounts[0].diagnostics.unpriced_models == []


@pytest.mark.parametrize("missing", [True, False])
def test_missing_or_negative_tokens_remain_incomplete(missing: bool) -> None:
    bucket = replace(_bucket("a", BASE), input_tokens=None if missing else -1)
    assert estimate_work_units(bucket) is None


def test_current_window_calibration_reaches_ready_after_three_multi_hour_estimates() -> None:
    response = build_weekly_coverage(
        [_account()],
        now=BASE + timedelta(days=1, hours=6),
        routing_strategy="capacity_weighted",
        freshness_seconds=3600,
    )

    account = response.accounts[0]
    assert response.status == "ready"
    assert account.status == "ready"
    assert account.sample_count == 3
    assert account.capacity_work_units is not None
    assert account.observed_drop_percent == pytest.approx(12.0)
    assert account.intervals
    assert response.intervals


def test_ordinary_reset_reuses_only_a_stable_prior_regime() -> None:
    response = build_weekly_coverage(
        [_rolling_account()],
        now=BASE + timedelta(days=7, hours=8),
        routing_strategy="capacity_weighted",
        freshness_seconds=3600,
    )

    account = response.accounts[0]
    assert response.status == "ready"
    assert account.sample_count == 6
    assert "prior_capacity_reused" in response.warnings


def test_incompatible_prior_capacity_is_not_reused() -> None:
    response = build_weekly_coverage(
        [_rolling_account(prior_input_tokens=2_000_000)],
        now=BASE + timedelta(days=7, hours=8),
        routing_strategy="capacity_weighted",
        freshness_seconds=3600,
    )

    account = response.accounts[0]
    assert response.status == "ready"
    assert account.sample_count == 3
    assert "prior_capacity_reused" not in response.warnings


def test_early_reset_does_not_reuse_prior_capacity() -> None:
    response = build_weekly_coverage(
        [_rolling_account(current_reset=BASE + timedelta(days=13))],
        now=BASE + timedelta(days=7, hours=8),
        routing_strategy="capacity_weighted",
        freshness_seconds=3600,
    )

    account = response.accounts[0]
    assert response.status == "ready"
    assert account.sample_count == 3
    assert account.quota_pace_status == "unavailable"
    assert "prior_capacity_reused" not in response.warnings


def test_quota_regression_withholds_independent_percentage_projection() -> None:
    response = build_weekly_coverage(
        [_account(used=(10.0, 14.0, 5.0, 9.0, 13.0, 17.0))],
        now=BASE + timedelta(days=1, hours=10),
        routing_strategy="capacity_weighted",
        freshness_seconds=3600,
    )

    account = response.accounts[0]
    assert account.status == "ready"
    assert account.quota_pace_status == "unavailable"
    assert account.projected_remaining_at_reset is None
    assert "quota_regression_reset" in response.warnings


def test_exact_exhaustion_at_reset_is_not_reported_as_an_early_gap() -> None:
    sample_start = BASE + timedelta(days=3, hours=6)
    response = build_weekly_coverage(
        [_account(used=(20.0, 30.0, 40.0, 50.0), sample_start=sample_start)],
        now=BASE + timedelta(days=3, hours=12),
        routing_strategy="capacity_weighted",
        freshness_seconds=3600,
    )

    account = response.accounts[0]
    assert account.quota_pace_status == "lasts_until_reset"
    assert account.projected_exhaustion_at is None
    assert account.projected_remaining_at_reset == pytest.approx(0.0)


def test_small_reset_deadline_drift_stays_in_the_current_regime() -> None:
    samples = tuple(
        WeeklyQuotaSample(
            recorded_at=BASE + timedelta(days=1, hours=2 * index),
            used_percent=10.0 + (4.0 * index),
            reset_at=RESET + timedelta(minutes=5 * index),
            window_minutes=10_080,
        )
        for index in range(4)
    )
    account = WeeklyCoverageAccountInput(
        account_id="drift",
        label="DRIFT",
        plan_type="pro",
        status="active",
        quota_history=samples,
        work_buckets=tuple(_bucket("drift", sample.recorded_at) for sample in samples[:-1]),
    )

    response = build_weekly_coverage(
        [account],
        now=BASE + timedelta(days=1, hours=7),
        routing_strategy="capacity_weighted",
        freshness_seconds=3600,
    )

    assert response.status == "ready"
    assert response.accounts[0].sample_count == 3


def test_large_reset_deadline_shift_without_quota_drop_stays_in_the_current_regime() -> None:
    samples = tuple(
        WeeklyQuotaSample(
            recorded_at=BASE + timedelta(days=1, hours=2 * index),
            used_percent=10.0 + (4.0 * index),
            reset_at=RESET + (timedelta(hours=12) if index >= 3 else timedelta(0)),
            window_minutes=10_080,
        )
        for index in range(5)
    )
    account = WeeklyCoverageAccountInput(
        account_id="deadline-shift",
        label="DEADLINE SHIFT",
        plan_type="pro",
        status="active",
        quota_history=samples,
        work_buckets=tuple(_bucket("deadline-shift", sample.recorded_at) for sample in samples[:-1]),
    )

    response = build_weekly_coverage(
        [account],
        now=BASE + timedelta(days=1, hours=9),
        routing_strategy="capacity_weighted",
        freshness_seconds=3600,
    )

    assert response.status == "ready"
    assert response.accounts[0].sample_count == 4


def test_counter_reset_starts_a_new_calibration_regime() -> None:
    samples = tuple(
        WeeklyQuotaSample(
            recorded_at=BASE + timedelta(days=1, hours=2 * index),
            used_percent=value,
            reset_at=RESET if index < 4 else RESET + timedelta(hours=12),
            window_minutes=10_080,
        )
        for index, value in enumerate((20.0, 24.0, 28.0, 32.0, 4.0, 8.0, 12.0, 16.0))
    )
    account = WeeklyCoverageAccountInput(
        account_id="reset",
        label="RESET",
        plan_type="pro",
        status="active",
        quota_history=samples,
        work_buckets=tuple(_bucket("reset", sample.recorded_at) for sample in samples[:-1]),
    )

    response = build_weekly_coverage(
        [account],
        now=BASE + timedelta(days=1, hours=15),
        routing_strategy="capacity_weighted",
        freshness_seconds=3600,
    )

    assert response.status == "ready"
    assert response.accounts[0].sample_count == 3
    assert response.accounts[0].observed_drop_percent == pytest.approx(12.0)


def test_quota_regression_discards_prior_regime() -> None:
    response = build_weekly_coverage(
        [_account(used=(10.0, 14.0, 18.0, 22.0, 5.0, 9.0, 13.0, 17.0))],
        now=BASE + timedelta(days=1, hours=14),
        routing_strategy="capacity_weighted",
        freshness_seconds=3600,
    )

    assert response.status == "ready"
    assert response.accounts[0].sample_count == 3
    assert response.accounts[0].observed_drop_percent == pytest.approx(12.0)
    assert "quota_regression_reset" in response.warnings


def test_sparse_quota_samples_do_not_create_fabricated_blocks() -> None:
    samples = tuple(
        WeeklyQuotaSample(
            recorded_at=BASE + timedelta(days=1, hours=3 * index),
            used_percent=10.0 + 6.0 * index,
            reset_at=RESET,
            window_minutes=10_080,
        )
        for index in range(3)
    )
    account = WeeklyCoverageAccountInput(
        account_id="sparse",
        label="SPARSE",
        plan_type="pro",
        status="active",
        quota_history=samples,
        work_buckets=tuple(_bucket("sparse", BASE + timedelta(days=1, hours=index)) for index in range(6)),
    )

    response = build_weekly_coverage(
        [account],
        now=BASE + timedelta(days=1, hours=6),
        routing_strategy="capacity_weighted",
        freshness_seconds=3600,
    )

    assert response.status == "learning"
    assert response.accounts[0].capacity_work_units is None


def test_new_window_without_enough_drawdown_stays_learning() -> None:
    response = build_weekly_coverage(
        [_account(used=(1.0, 1.5, 1.8, 2.0))],
        now=BASE + timedelta(days=1, hours=6),
        routing_strategy="capacity_weighted",
        freshness_seconds=3600,
    )

    assert response.status == "learning"
    assert response.accounts[0].status == "learning"
    assert response.accounts[0].capacity_work_units is None
    assert "insufficient_calibration" in response.warnings
    assert response.intervals == []


def test_unattributed_drawdown_is_limited_instead_of_zero_demand() -> None:
    response = build_weekly_coverage(
        [_account(work=False)],
        now=BASE + timedelta(days=1, hours=6),
        routing_strategy="capacity_weighted",
        freshness_seconds=3600,
    )

    assert response.status == "limited"
    assert response.accounts[0].status == "limited"
    assert response.accounts[0].reason == "external_or_unexplained_drawdown"
    assert "external_or_unexplained_drawdown" in response.warnings


def test_inactive_and_non_pro_accounts_are_excluded_with_reasons() -> None:
    response = build_weekly_coverage(
        [_account("paused", status="paused"), _account("plus", plan_type="plus")],
        now=BASE + timedelta(days=1, hours=6),
        routing_strategy="capacity_weighted",
        freshness_seconds=3600,
    )

    assert response.status == "no_eligible_accounts"
    assert [account.status for account in response.accounts] == ["excluded", "excluded"]
    assert response.accounts[0].reason == "paused"
    assert response.accounts[1].reason == "plan_not_supported"


def test_stale_quota_evidence_is_limited_even_when_capacity_is_measurable() -> None:
    response = build_weekly_coverage(
        [_account()],
        now=BASE + timedelta(days=1, hours=12),
        routing_strategy="capacity_weighted",
        freshness_seconds=3600,
    )

    assert response.status == "limited"
    assert response.accounts[0].status == "limited"
    assert response.accounts[0].reason == "stale_usage"
    assert response.intervals == []
    assert response.minimum_reserve_hours is None


def test_all_empty_pool_reports_exhausted_interval_with_zero_pace() -> None:
    now = BASE + timedelta(days=1)
    result = _simulate(
        [
            _SimulationAccount(
                account_id="a",
                capacity_work_units=100.0,
                balance_work_units=0.0,
                next_reset=now + timedelta(hours=3),
                window=timedelta(days=7),
                routing_policy="normal",
                transitions=[(now, "exhausted")],
            )
        ],
        now=now,
        horizon=now + timedelta(hours=6),
        demand_work_units_per_hour=0.0,
        routing_strategy="capacity_weighted",
        prefer_earlier_reset_accounts=False,
        relative_availability_power=2.0,
        relative_availability_top_k=5,
    )

    assert result.pool_intervals[0].state == "exhausted"
    assert result.pool_intervals[0].start_at == now
    assert result.pool_intervals[0].end_at == now + timedelta(hours=3)
    assert result.pool_intervals[1].state == "available"


def test_exhausted_account_keeps_uncensored_capacity_evidence_and_returns_at_reset() -> None:
    now = BASE + timedelta(days=1, hours=8)
    account = _account(status="quota_exceeded", used=(10, 14, 18, 22, 100))
    forecast = build_weekly_coverage(
        [account],
        now=now,
        routing_strategy="reset_drain",
        freshness_seconds=300,
    )
    assert forecast.status == "ready"
    assert forecast.accounts[0].sample_count == 3
    assert forecast.accounts[0].remaining_percent == 0
    assert forecast.intervals[0].state == "exhausted"
    assert forecast.intervals[0].start_at == now
    assert forecast.intervals[0].end_at == RESET
    assert forecast.intervals[1].state == "available"
    assert "quota_limit_censoring" in forecast.warnings


def test_demand_transfers_after_one_account_exhausts() -> None:
    now = BASE + timedelta(days=1)
    result = _simulate(
        [
            _SimulationAccount(
                account_id="small",
                capacity_work_units=20.0,
                balance_work_units=20.0,
                next_reset=now + timedelta(days=7),
                window=timedelta(days=7),
                routing_policy="normal",
                transitions=[(now, "available")],
            ),
            _SimulationAccount(
                account_id="large",
                capacity_work_units=100.0,
                balance_work_units=100.0,
                next_reset=now + timedelta(days=8),
                window=timedelta(days=7),
                routing_policy="normal",
                transitions=[(now, "available")],
            ),
        ],
        now=now,
        horizon=now + timedelta(hours=4),
        demand_work_units_per_hour=100.0,
        routing_strategy="reset_drain",
        prefer_earlier_reset_accounts=False,
        relative_availability_power=2.0,
        relative_availability_top_k=5,
    )

    small_exhaustion = next(
        interval.start_at for interval in result.account_intervals["small"] if interval.state == "exhausted"
    )
    assert small_exhaustion < now + timedelta(hours=2)
    large_exhaustion = next(
        interval.start_at for interval in result.account_intervals["large"] if interval.state == "exhausted"
    )
    assert large_exhaustion > small_exhaustion
    assert len(result.pool_intervals) == 2
    assert result.pool_intervals[0].state == "available"
    assert result.pool_intervals[0].end_at == large_exhaustion
    assert result.pool_intervals[1].state == "exhausted"


@pytest.mark.parametrize("reset_hours", [1, 2])
def test_reset_replaces_unused_balance_and_exact_exhaustion_at_reset(reset_hours: int) -> None:
    now = BASE + timedelta(days=1)
    result = _simulate(
        [
            _SimulationAccount(
                account_id="a",
                capacity_work_units=2.0,
                balance_work_units=2.0,
                next_reset=now + timedelta(hours=reset_hours),
                window=timedelta(days=7),
                routing_policy="normal",
                transitions=[(now, "available")],
            )
        ],
        now=now,
        horizon=now + timedelta(hours=5),
        demand_work_units_per_hour=1.0,
        routing_strategy="capacity_weighted",
        prefer_earlier_reset_accounts=False,
        relative_availability_power=2.0,
        relative_availability_top_k=5,
    )

    intervals = result.account_intervals["a"]
    assert len(intervals) == 2
    assert intervals[0].state == "available"
    assert intervals[0].start_at == now
    assert intervals[0].end_at == now + timedelta(hours=reset_hours + 2)
    assert intervals[1].state == "exhausted"


def test_multiple_outage_windows_recover_at_staggered_resets() -> None:
    now = BASE + timedelta(days=1)
    result = _simulate(
        [
            _SimulationAccount(
                account_id="a",
                capacity_work_units=10.0,
                balance_work_units=0.0,
                next_reset=now + timedelta(hours=2),
                window=timedelta(days=7),
                routing_policy="normal",
                transitions=[(now, "exhausted")],
            ),
            _SimulationAccount(
                account_id="b",
                capacity_work_units=10.0,
                balance_work_units=0.0,
                next_reset=now + timedelta(hours=5),
                window=timedelta(days=7),
                routing_policy="normal",
                transitions=[(now, "exhausted")],
            ),
        ],
        now=now,
        horizon=now + timedelta(hours=6),
        demand_work_units_per_hour=10.0,
        routing_strategy="capacity_weighted",
        prefer_earlier_reset_accounts=False,
        relative_availability_power=2.0,
        relative_availability_top_k=5,
    )

    states = [(interval.state, interval.start_at - now, interval.end_at - now) for interval in result.pool_intervals]
    assert states == [
        ("exhausted", timedelta(0), timedelta(hours=2)),
        ("available", timedelta(hours=2), timedelta(hours=3)),
        ("exhausted", timedelta(hours=3), timedelta(hours=5)),
        ("available", timedelta(hours=5), timedelta(hours=6)),
    ]


def test_elapsed_reset_is_applied_without_a_new_quota_sample() -> None:
    now = BASE + timedelta(days=8)
    result = _simulate(
        [
            _SimulationAccount(
                account_id="a",
                capacity_work_units=10.0,
                balance_work_units=1.0,
                next_reset=now - timedelta(hours=1),
                window=timedelta(days=7),
                routing_policy="normal",
                transitions=[(now, "available")],
            )
        ],
        now=now,
        horizon=now + timedelta(hours=2),
        demand_work_units_per_hour=1.0,
        routing_strategy="capacity_weighted",
        prefer_earlier_reset_accounts=False,
        relative_availability_power=2.0,
        relative_availability_top_k=5,
    )

    assert result.account_intervals["a"][0].end_at == now + timedelta(hours=2)


def test_unsupported_routing_strategy_cannot_claim_ready() -> None:
    response = build_weekly_coverage(
        [_account()],
        now=BASE + timedelta(days=1, hours=6),
        routing_strategy="fill_first",
        freshness_seconds=3600,
    )

    assert response.status == "limited"
    assert "unsupported_routing_strategy" in response.warnings
    assert response.intervals == []


@pytest.mark.timeout(2)
@pytest.mark.parametrize("horizon_delta", [timedelta(microseconds=1), timedelta(seconds=1, microseconds=1)])
def test_fractional_exhaustion_does_not_skip_demand_or_stall_at_horizon(horizon_delta: timedelta) -> None:
    now = BASE
    accounts = [
        _SimulationAccount(
            account_id=account_id,
            capacity_work_units=1,
            balance_work_units=balance,
            next_reset=now + timedelta(days=1),
            window=timedelta(days=7),
            routing_policy="normal",
            transitions=[(now, "available")],
        )
        for account_id, balance in [("nearly_empty", 1e-8), ("full", 1.0)]
    ]
    result = _simulate(
        accounts,
        now=now,
        horizon=now + horizon_delta,
        demand_work_units_per_hour=1_000_000,
        routing_strategy="sequential_drain",
        prefer_earlier_reset_accounts=False,
        relative_availability_power=2,
        relative_availability_top_k=5,
    )
    assert result.pool_intervals[0].start_at == now
    assert result.pool_intervals[-1].end_at == now + horizon_delta
    if horizon_delta > timedelta(seconds=1):
        gap = next(interval for interval in result.pool_intervals if interval.state == "exhausted")
        assert abs((gap.start_at - now).total_seconds() - 0.0036) < 0.000001


def test_single_account_selection_excludes_other_eligible_accounts() -> None:
    response = build_weekly_coverage(
        [_account("a"), _account("b")],
        now=BASE + timedelta(days=1, hours=6),
        routing_strategy="single_account",
        freshness_seconds=3600,
        single_account_id="a",
    )

    assert response.accounts[0].status == "ready"
    assert response.accounts[1].status == "excluded"
    assert response.accounts[1].reason == "single_account_selection"
