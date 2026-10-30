from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import update

from app.core.crypto import TokenEncryptor
from app.core.utils.time import naive_utc_to_epoch
from app.db.models import Account, AccountStatus, AccountUsageRollupState, DashboardSettings, RequestLog
from app.db.session import SessionLocal
from app.modules.accounts.repository import AccountsRepository
from app.modules.accounts.usage_rollup import lock_fold_state
from app.modules.accounts.usage_time_rollup import (
    HourlyUsageRollupRow,
    RequestUsageTimeRollupRepository,
    to_dimension,
)
from app.modules.dashboard.coverage_repository import CoverageRepository
from app.modules.usage.repository import UsageRepository

pytestmark = pytest.mark.integration
NOW = datetime(2026, 10, 2, 12)


def _account(account_id: str, status: AccountStatus = AccountStatus.ACTIVE, plan: str = "pro") -> Account:
    encryptor = TokenEncryptor()
    return Account(
        id=account_id,
        email=f"{account_id}@example.test",
        plan_type=plan,
        status=status,
        access_token_encrypted=encryptor.encrypt("test"),
        refresh_token_encrypted=encryptor.encrypt("test"),
        id_token_encrypted=encryptor.encrypt("test"),
        last_refresh=NOW,
    )


def _log(account_id: str, at: datetime, request_id: str, **overrides) -> RequestLog:
    values = dict(
        account_id=account_id,
        requested_at=at,
        request_id=request_id,
        model="gpt-6-sol",
        status="success",
        input_tokens=1000,
        output_tokens=100,
        cached_input_tokens=100,
        cost_usd=0.003,
        service_tier="default",
    )
    values.update(overrides)
    return RequestLog(**values)


@pytest.mark.asyncio
async def test_work_history_respects_fold_boundary_account_scope_and_complete_hours(db_setup):
    start = NOW - timedelta(hours=4)
    watermark = start + timedelta(hours=2)
    async with SessionLocal() as session:
        accounts = AccountsRepository(session)
        await accounts.upsert(_account("covered"))
        await accounts.upsert(_account("unrelated"))
        await lock_fold_state(session)
        await session.execute(
            update(AccountUsageRollupState)
            .where(AccountUsageRollupState.id == 1)
            .values(hourly_folded_through=watermark)
        )
        await RequestUsageTimeRollupRepository(session).add_hourly(
            [
                HourlyUsageRollupRow(
                    bucket_epoch=int(naive_utc_to_epoch(start)),
                    account_id=to_dimension("covered"),
                    api_key_id=to_dimension(None),
                    model="gpt-6-sol",
                    service_tier=to_dimension("default"),
                    request_kind="normal",
                    is_deleted=False,
                    input_tokens=1000,
                    output_or_reasoning_tokens=100,
                    cached_input_tokens_clamped=100,
                    request_count=1,
                    cost_count=1,
                )
            ]
        )
        session.add_all(
            [
                _log("covered", start + timedelta(minutes=10), "folded-raw-copy"),
                _log("covered", watermark + timedelta(minutes=10), "raw-tail"),
                _log("covered", NOW + timedelta(minutes=2), "incomplete-hour"),
                _log("unrelated", watermark + timedelta(minutes=10), "out-of-scope"),
            ]
        )
        await session.commit()
        result = await CoverageRepository(session).work_history(["covered"], start, NOW + timedelta(minutes=20))
        assert set(result) == {"covered"}
        assert sum(row.input_tokens or 0 for row in result["covered"]) == 2000
        assert sum(row.request_count for row in result["covered"]) == 2
        assert all(row.missing_usage_count == 0 for row in result["covered"])


@pytest.mark.asyncio
async def test_work_history_keeps_hidden_and_warmup_work_and_marks_incomplete_usage(db_setup):
    async with SessionLocal() as session:
        await AccountsRepository(session).upsert(_account("covered"))
        session.add_all(
            [
                _log("covered", NOW - timedelta(hours=1), "warmup", request_kind="warmup", deleted_at=NOW),
                _log("covered", NOW - timedelta(minutes=50), "missing", input_tokens=None),
                _log("covered", NOW - timedelta(minutes=40), "reasoning", output_tokens=None, reasoning_tokens=200),
            ]
        )
        await session.commit()
        result = await CoverageRepository(session).work_history(["covered"], NOW - timedelta(hours=2), NOW)
        assert sum(row.request_count for row in result["covered"]) == 3
        assert sum(row.output_tokens or 0 for row in result["covered"]) == 400
        assert sum(row.missing_usage_count for row in result["covered"]) == 1


@pytest.mark.asyncio
async def test_projections_explain_learning_and_exclusions_without_false_coverage(async_client, db_setup, monkeypatch):
    monkeypatch.setattr("app.modules.dashboard.service.utcnow", lambda: NOW)
    async with SessionLocal() as session:
        accounts = AccountsRepository(session)
        for account in [
            _account("learning"),
            _account("paused", AccountStatus.PAUSED),
            _account("reauth", AccountStatus.REAUTH_REQUIRED),
            _account("free", plan="free"),
        ]:
            await accounts.upsert(account)
        await UsageRepository(session).add_entry(
            "learning",
            40.0,
            window="secondary",
            window_minutes=10080,
            reset_at=int(naive_utc_to_epoch(NOW + timedelta(days=2))),
            recorded_at=NOW,
        )
    response = await async_client.get("/api/dashboard/projections")
    assert response.status_code == 200
    coverage = response.json()["weeklyCoverage"]
    assert coverage["status"] in {"learning", "limited"}
    assert coverage["intervals"] == []
    assert coverage["minimumReserveHours"] is None
    assert coverage["paceBasis"] == "current_window_average"
    assert coverage["generatedAt"].endswith("Z")
    rows = {row["accountId"]: row for row in coverage["accounts"]}
    assert rows["learning"]["remainingPercent"] == 60
    assert all(rows[key]["status"] == "excluded" for key in ("paused", "reauth", "free"))
    assert all(rows[key]["reason"] for key in ("paused", "reauth", "free"))


@pytest.mark.asyncio
async def test_projections_no_accounts_is_not_covered(async_client, db_setup):
    response = await async_client.get("/api/dashboard/projections")
    assert response.status_code == 200
    coverage = response.json()["weeklyCoverage"]
    assert coverage["status"] == "no_eligible_accounts"
    assert coverage["intervals"] == []


@pytest.mark.asyncio
async def test_projections_withhold_forecast_when_reported_reset_has_elapsed(async_client, db_setup, monkeypatch):
    monkeypatch.setattr("app.modules.dashboard.service.utcnow", lambda: NOW)
    async with SessionLocal() as session:
        await AccountsRepository(session).upsert(_account("elapsed"))
        usage = UsageRepository(session)
        for index in range(5):
            await usage.add_entry(
                "elapsed",
                10 + index * 10,
                window="secondary",
                window_minutes=10080,
                reset_at=int(naive_utc_to_epoch(NOW - timedelta(hours=9))),
                recorded_at=NOW - timedelta(hours=8 - index * 2),
            )
        session.add_all([_log("elapsed", NOW - timedelta(hours=hour, minutes=30), f"work-{hour}") for hour in range(8)])
        await session.commit()
    response = await async_client.get("/api/dashboard/projections")
    assert response.status_code == 200
    coverage = response.json()["weeklyCoverage"]
    assert coverage["status"] == "limited"
    assert coverage["accounts"][0]["reason"] == "weekly_reset_elapsed"
    assert coverage["intervals"] == []


@pytest.mark.asyncio
async def test_current_monthly_regime_does_not_reuse_superseded_weekly_quota(async_client, db_setup, monkeypatch):
    monkeypatch.setattr("app.modules.dashboard.service.utcnow", lambda: NOW)
    async with SessionLocal() as session:
        await AccountsRepository(session).upsert(_account("monthly"))
        repo = UsageRepository(session)
        # This history MUST be independently calibratable: an insufficient
        # weekly fixture would conceal a missing supersession guard.
        for hour in range(13):
            await repo.add_entry(
                "monthly",
                20 + hour * 2,
                window="secondary",
                window_minutes=10080,
                reset_at=int(naive_utc_to_epoch(NOW + timedelta(days=2))),
                recorded_at=NOW - timedelta(hours=12 - hour, seconds=30),
            )
        session.add_all(
            [_log("monthly", NOW - timedelta(hours=hour, minutes=30), f"monthly-work-{hour}") for hour in range(12)]
        )
        await session.commit()
    baseline = (await async_client.get("/api/dashboard/projections")).json()["weeklyCoverage"]
    assert baseline["status"] == "ready"
    async with SessionLocal() as session:
        repo = UsageRepository(session)
        await repo.add_entry(
            "monthly",
            90,
            window="monthly",
            window_minutes=43200,
            reset_at=int(naive_utc_to_epoch(NOW + timedelta(days=20))),
            recorded_at=NOW,
        )
    response = await async_client.get("/api/dashboard/projections")
    assert response.status_code == 200
    coverage = response.json()["weeklyCoverage"]
    assert coverage["status"] != "ready"
    assert coverage["intervals"] == []
    account = coverage["accounts"][0]
    assert account["reason"] == "weekly_window_superseded"
    assert account["quotaPaceStatus"] == "unavailable"
    assert account["remainingPercent"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("window", ["primary", "secondary"])
async def test_projections_forecast_exhaustion_and_recovery_from_dense_weekly_samples(
    async_client, db_setup, monkeypatch, window
):
    monkeypatch.setattr("app.modules.dashboard.service.utcnow", lambda: NOW)
    reset = NOW + timedelta(days=6)
    start = NOW - timedelta(hours=12)
    async with SessionLocal() as session:
        await AccountsRepository(session).upsert(_account("calibrated"))
        usage = UsageRepository(session)
        # Real poll cadence is much shorter than a calibration interval.
        for minute in range(0, 721, 5):
            await usage.add_entry(
                "calibrated",
                40 + minute / 18,
                window=window,
                window_minutes=10080,
                reset_at=int(naive_utc_to_epoch(reset)),
                recorded_at=start + timedelta(minutes=minute),
            )
        session.add_all(
            [_log("calibrated", start + timedelta(hours=hour, minutes=30), f"work-{hour}") for hour in range(12)]
        )
        await session.commit()
    response = await async_client.get("/api/dashboard/projections")
    assert response.status_code == 200
    coverage = response.json()["weeklyCoverage"]
    assert coverage["status"] == "ready"
    account = coverage["accounts"][0]
    assert account["sampleCount"] >= 3
    assert account["remainingPercent"] == pytest.approx(20)
    first_gap = next(interval for interval in coverage["intervals"] if interval["state"] == "exhausted")
    gap_start = datetime.fromisoformat(first_gap["startAt"]).replace(tzinfo=None)
    gap_end = datetime.fromisoformat(first_gap["endAt"]).replace(tzinfo=None)
    assert abs((gap_start - (NOW + timedelta(hours=6))).total_seconds()) < 60
    assert gap_end == reset
    assert coverage["minimumReserveHours"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_tokens", [False, True])
async def test_unknown_model_tokens_calibrate_the_pool_without_pricing(
    async_client, db_setup, monkeypatch, missing_tokens
):
    monkeypatch.setattr("app.modules.dashboard.service.utcnow", lambda: NOW)
    async with SessionLocal() as session:
        await AccountsRepository(session).upsert(_account("unpriced"))
        usage = UsageRepository(session)
        for hour in range(13):
            await usage.add_entry(
                "unpriced",
                20 + hour * 2,
                window="secondary",
                window_minutes=10080,
                reset_at=int(naive_utc_to_epoch(NOW + timedelta(days=3))),
                recorded_at=NOW - timedelta(hours=12 - hour),
            )
        session.add_all(
            [
                _log(
                    "unpriced",
                    NOW - timedelta(hours=hour, minutes=30),
                    f"unpriced-{hour}",
                    model="codex-auto-review" if hour % 2 else "gpt-6-sol",
                    actual_service_tier="future-tier",
                    cost_usd=None,
                    input_tokens=None if missing_tokens else 1000,
                )
                for hour in range(12)
            ]
        )
        await session.commit()
    response = await async_client.get("/api/dashboard/projections")
    assert response.status_code == 200
    coverage = response.json()["weeklyCoverage"]
    account = coverage["accounts"][0]
    assert account["quotaPaceStatus"] == "lasts_until_reset"
    assert account["usedPercentPerDay"] == pytest.approx(11)
    assert account["projectedRemainingAtReset"] == pytest.approx(23)
    assert account["diagnostics"]["unpricedModels"] == []
    if missing_tokens:
        assert coverage["status"] == "limited"
        assert coverage["intervals"] == []
        assert account["capacityWorkUnits"] is None
        assert account["reason"] == "incomplete_work_history"
    else:
        assert coverage["status"] == "ready"
        assert coverage["intervals"]
        assert all(interval["state"] == "available" for interval in coverage["intervals"])
        assert account["sampleCount"] >= 3
        assert account["capacityWorkUnits"] == pytest.approx(0.055)


@pytest.mark.asyncio
@pytest.mark.parametrize("selected", [None, "", "   ", "missing"])
async def test_single_account_without_valid_selection_cannot_claim_coverage(
    async_client, db_setup, monkeypatch, selected
):
    monkeypatch.setattr("app.modules.dashboard.service.utcnow", lambda: NOW)
    async with SessionLocal() as session:
        await AccountsRepository(session).upsert(_account("calibrated"))
        usage = UsageRepository(session)
        for hour in range(13):
            await usage.add_entry(
                "calibrated",
                20 + hour * 2,
                window="secondary",
                window_minutes=10080,
                reset_at=int(naive_utc_to_epoch(NOW + timedelta(days=2))),
                recorded_at=NOW - timedelta(hours=12 - hour),
            )
        session.add_all(
            [_log("calibrated", NOW - timedelta(hours=hour, minutes=30), f"single-{hour}") for hour in range(12)]
        )
        await session.commit()
    baseline = (await async_client.get("/api/dashboard/projections")).json()["weeklyCoverage"]
    assert baseline["status"] == "ready"
    async with SessionLocal() as session:
        await session.execute(
            update(DashboardSettings).values(routing_strategy="single_account", single_account_id=selected)
        )
        await session.commit()
    result = (await async_client.get("/api/dashboard/projections")).json()["weeklyCoverage"]
    assert result["status"] != "ready"
    assert result["intervals"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_tokens", [False, True])
async def test_clean_usage_recovers_after_an_early_failed_request(async_client, db_setup, monkeypatch, missing_tokens):
    monkeypatch.setattr("app.modules.dashboard.service.utcnow", lambda: NOW)
    start = NOW - timedelta(hours=12)
    async with SessionLocal() as session:
        await AccountsRepository(session).upsert(_account("recovering"))
        usage = UsageRepository(session)
        for hour in range(13):
            await usage.add_entry(
                "recovering",
                20 + hour * 2,
                window="secondary",
                window_minutes=10080,
                reset_at=int(naive_utc_to_epoch(NOW + timedelta(days=3))),
                recorded_at=start + timedelta(hours=hour),
            )
        for hour in range(12):
            overrides = {}
            if hour == 0:
                overrides = {"status": "error", "cost_usd": None}
                if missing_tokens:
                    overrides["input_tokens"] = None
                    overrides["output_tokens"] = None
            session.add(_log("recovering", start + timedelta(hours=hour, minutes=30), f"recover-{hour}", **overrides))
        await session.commit()
    response = await async_client.get("/api/dashboard/projections")
    assert response.status_code == 200
    result = response.json()["weeklyCoverage"]
    assert result["status"] == "ready"
    assert result["intervals"]
    account = result["accounts"][0]
    assert account["sampleCount"] >= 3
    assert account["diagnostics"]["discardedIntervalCount"] == (1 if missing_tokens else 0)
