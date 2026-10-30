from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.crypto import TokenEncryptor
from app.db.models import Account, AccountStatus, RequestLog
from app.db.session import SessionLocal
from app.modules.accounts.repository import AccountsRepository
from app.modules.accounts.usage_time_rollup import run_hourly_fold_pass
from app.modules.dashboard.coverage_repository import CoverageRepository
from app.modules.dashboard.coverage_types import CoverageWorkBucket
from app.modules.dashboard.coverage_work import estimate_work_units

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 2, 12)


def _account(account_id: str = "covered") -> Account:
    encryptor = TokenEncryptor()
    return Account(
        id=account_id,
        email=f"{account_id}@example.test",
        plan_type="pro",
        status=AccountStatus.ACTIVE,
        access_token_encrypted=encryptor.encrypt("test"),
        refresh_token_encrypted=encryptor.encrypt("test"),
        id_token_encrypted=encryptor.encrypt("test"),
        last_refresh=NOW,
    )


def _log(
    account_id: str,
    at: datetime,
    request_id: str,
    *,
    input_tokens: int | None = 1_000,
    output_tokens: int | None = 100,
    cached_input_tokens: int | None = 0,
    cache_write_tokens: int | None = 0,
    status: str = "success",
    cost_usd: float | None = None,
    service_tier: str | None = "default",
    actual_service_tier: str | None = None,
    model: str = "gpt-6-sol",
) -> RequestLog:
    return RequestLog(
        account_id=account_id,
        requested_at=at,
        request_id=request_id,
        model=model,
        status=status,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        cache_write_tokens=cache_write_tokens,
        cost_usd=cost_usd,
        service_tier=service_tier,
        actual_service_tier=actual_service_tier,
    )


def _bucket_signature(rows: list[CoverageWorkBucket]) -> list[tuple]:
    return [
        (
            row.started_at,
            row.model,
            row.service_tier,
            row.context_long,
            row.input_tokens,
            row.output_tokens,
            row.cached_input_tokens,
            row.cache_write_tokens,
            row.request_count,
            row.missing_usage_count,
        )
        for row in rows
    ]


@pytest.mark.asyncio
async def test_raw_aggregation_preserves_additive_measured_work(db_setup) -> None:
    async with SessionLocal() as session:
        await AccountsRepository(session).upsert(_account())
        session.add_all(
            [
                _log(
                    "covered",
                    NOW - timedelta(hours=1) + timedelta(minutes=offset),
                    f"short-{offset}",
                    input_tokens=100_000,
                )
                for offset in (10, 20, 30)
            ]
        )
        await session.commit()
        rows = await CoverageRepository(session).work_history(["covered"], NOW - timedelta(hours=2), NOW)

    buckets = rows["covered"]
    assert len(buckets) == 1
    bucket = buckets[0]
    assert bucket.request_count == 3
    assert bucket.input_tokens == 300_000
    assert bucket.context_long is None

    individual_work = sum(
        estimate_work_units(
            CoverageWorkBucket(
                account_id="covered",
                started_at=bucket.started_at,
                model="gpt-6-sol",
                service_tier="default",
                context_long=False,
                input_tokens=100_000,
                output_tokens=100,
                cached_input_tokens=0,
                cache_write_tokens=0,
                request_count=1,
            )
        )
        or 0.0
        for _ in range(3)
    )
    assert estimate_work_units(bucket) == pytest.approx(individual_work)


@pytest.mark.asyncio
async def test_raw_aggregation_uses_actual_tier_and_requested_fallback(db_setup) -> None:
    async with SessionLocal() as session:
        await AccountsRepository(session).upsert(_account())
        session.add_all(
            [
                _log("covered", NOW - timedelta(hours=1, minutes=10), "actual", actual_service_tier="priority"),
                _log("covered", NOW - timedelta(hours=1, minutes=20), "fallback", service_tier="priority"),
                _log("covered", NOW - timedelta(hours=1, minutes=30), "standard", service_tier="default"),
            ]
        )
        await session.commit()
        rows = await CoverageRepository(session).work_history(["covered"], NOW - timedelta(hours=2), NOW)

    buckets = rows["covered"]
    assert {(row.service_tier, row.request_count) for row in buckets} == {
        ("priority", 2),
        ("default", 1),
    }


@pytest.mark.asyncio
async def test_token_completeness_ignores_missing_price_and_failure_status(db_setup) -> None:
    async with SessionLocal() as session:
        await AccountsRepository(session).upsert(_account())
        session.add_all(
            [
                _log("covered", NOW - timedelta(hours=1, minutes=10), "zero-success", input_tokens=0, output_tokens=0),
                _log(
                    "covered",
                    NOW - timedelta(hours=1, minutes=20),
                    "failed-complete",
                    status="error",
                    cost_usd=None,
                    input_tokens=1_000,
                    output_tokens=100,
                ),
                _log(
                    "covered",
                    NOW - timedelta(hours=1, minutes=30),
                    "success-unpriced",
                    cost_usd=None,
                    input_tokens=1_000,
                    output_tokens=100,
                ),
            ]
        )
        await session.commit()
        rows = await CoverageRepository(session).work_history(["covered"], NOW - timedelta(hours=2), NOW)

    buckets = rows["covered"]
    incomplete = [row for row in buckets if row.missing_usage_count]
    complete = [row for row in buckets if not row.missing_usage_count]
    assert [(row.request_count, row.input_tokens, row.output_tokens) for row in incomplete] == [(1, 0, 0)]
    assert sum(row.request_count for row in complete) == 2
    assert sum(row.input_tokens or 0 for row in complete) == 2_000


@pytest.mark.asyncio
async def test_raw_work_is_invariant_when_hourly_fold_is_added(db_setup) -> None:
    async with SessionLocal() as session:
        await AccountsRepository(session).upsert(_account())
        session.add_all(
            [
                _log("covered", NOW - timedelta(days=2, minutes=10), "fold-invariant-a"),
                _log("covered", NOW - timedelta(days=2, minutes=20), "fold-invariant-b"),
            ]
        )
        await session.commit()
        before = await CoverageRepository(session).work_history(
            ["covered"], NOW - timedelta(days=3), NOW - timedelta(days=1)
        )

    assert await run_hourly_fold_pass(now=NOW) >= 1

    async with SessionLocal() as session:
        after = await CoverageRepository(session).work_history(
            ["covered"], NOW - timedelta(days=3), NOW - timedelta(days=1)
        )

    assert _bucket_signature(after["covered"]) == _bucket_signature(before["covered"])
