from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.models import (
    Account,
    AccountUsageRollup,
    AccountUsageRollupState,
    ApiKey,
    ApiKeyUsageRollup,
    RequestDemandQuarterRollup,
    RequestLog,
    RequestUsageHourlyRollup,
)
from app.db.session import SessionLocal
from app.modules.accounts.usage_time_rollup import epoch_seconds, to_dimension
from app.modules.request_logs.cost_repair import repair_cost_estimates

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_repair_preserves_pruned_history_and_deduplicates_account_cost(db_setup):
    when = datetime(2026, 9, 4, 10)
    async with SessionLocal() as session:
        session.add(
            Account(
                id="repair-account",
                last_refresh=when,
                email="repair@example.com",
                plan_type="plus",
                access_token_encrypted=b"x",
                refresh_token_encrypted=b"x",
                id_token_encrypted=b"x",
            )
        )
        session.add(ApiKey(id="repair-key", name="repair", key_hash="repair", key_prefix="repair"))
        await session.flush()
        session.add(AccountUsageRollupState(id=1, folded_through=when, hourly_folded_through=when + timedelta(hours=1)))
        session.add(AccountUsageRollup(account_id="repair-account", total_cost_usd=100))
        session.add(ApiKeyUsageRollup(api_key_id="repair-key", total_cost_usd=100))
        dims = dict(
            account_id="repair-account",
            api_key_id="repair-key",
            model="gpt-6-astra",
            request_kind="normal",
            is_deleted=False,
        )
        session.add(
            RequestUsageHourlyRollup(
                bucket_epoch=epoch_seconds(when),
                service_tier=to_dimension(None),
                cost_usd=100,
                cost_count=10,
                request_count=12,
                **dims,
            )
        )
        session.add(
            RequestDemandQuarterRollup(
                slot_epoch=epoch_seconds(when),
                reasoning_effort=to_dimension(None),
                status="success",
                cost_usd=100,
                request_count=12,
                **dims,
            )
        )
        for writes in (None, 40_000):
            session.add(
                RequestLog(
                    account_id="repair-account",
                    api_key_id="repair-key",
                    request_id="duplicate",
                    requested_at=when,
                    model="gpt-6-astra",
                    status="success",
                    input_tokens=200_000,
                    cached_input_tokens=100_000,
                    cache_write_tokens=writes,
                    output_tokens=100_000,
                )
            )
        session.add(
            RequestLog(
                request_id="custom",
                requested_at=when,
                model="gpt-6-astra",
                status="success",
                model_source_id="custom-source",
                input_tokens=200_000,
                output_tokens=100_000,
                cost_usd=42,
            )
        )
        await session.commit()
        preview = await repair_cost_estimates(session, models=["gpt-6-astra"], batch_size=1)
        assert (preview.scanned, preview.changed, preview.missing_cache_write_counts) == (2, 2, 1)
        assert preview.delta_usd == pytest.approx(12.3)
        account_rollup = await session.get(AccountUsageRollup, "repair-account")
        assert account_rollup is not None
        assert account_rollup.total_cost_usd == 100
        assert (
            await session.scalars(select(RequestLog.cost_usd).where(RequestLog.request_id == "duplicate"))
        ).all() == [None, None]
        await session.rollback()
        applied = await repair_cost_estimates(session, models=["gpt-6-astra"], apply=True, batch_size=1)
        assert applied.changed == 2
        account_rollup = await session.get(AccountUsageRollup, "repair-account")
        key_rollup = await session.get(ApiKeyUsageRollup, "repair-key")
        assert account_rollup is not None
        assert key_rollup is not None
        assert account_rollup.total_cost_usd == pytest.approx(106.2)
        assert key_rollup.total_cost_usd == pytest.approx(112.3)
        hourly = (await session.scalars(select(RequestUsageHourlyRollup))).one()
        assert hourly.cost_usd == pytest.approx(112.3)
        assert hourly.cost_count == 12
        assert hourly.request_count == 12
        assert (await session.scalars(select(RequestDemandQuarterRollup.cost_usd))).one() == pytest.approx(112.3)
        assert (await session.scalars(select(RequestLog.cost_usd).where(RequestLog.request_id == "custom"))).one() == 42
        await session.rollback()
        repeated = await repair_cost_estimates(session, models=["gpt-6-astra"], apply=True, batch_size=1)
        assert repeated.changed == 0


@pytest.mark.asyncio
async def test_repair_missing_rollup_rolls_back_batch(db_setup):
    when = datetime(2026, 9, 4, 10)
    async with SessionLocal() as session:
        session.add(AccountUsageRollupState(id=1, folded_through=when, hourly_folded_through=when + timedelta(hours=1)))
        session.add(
            RequestLog(
                request_id="missing-rollup",
                requested_at=when,
                model="gpt-6-astra",
                status="success",
                input_tokens=200_000,
                output_tokens=100_000,
            )
        )
        await session.commit()
        with pytest.raises(ValueError, match="Missing folded usage"):
            await repair_cost_estimates(session, models=["gpt-6-astra"], apply=True)
        assert (await session.scalars(select(RequestLog.cost_usd))).one() is None


@pytest.mark.asyncio
async def test_repair_scope_and_unpublished_prices(db_setup):
    when = datetime(2026, 9, 4, 10)
    async with SessionLocal() as session:
        for model, at in [
            ("gpt-6-astra", when),
            ("gpt-6-astra", when - timedelta(days=1)),
            ("gpt-5.3-codex-spark", when),
            ("unknown", when),
        ]:
            session.add(
                RequestLog(
                    request_id=f"{model}-{at}",
                    requested_at=at,
                    model=model,
                    status="success",
                    input_tokens=200_000,
                    output_tokens=100_000,
                    cost_usd=1,
                )
            )
        await session.commit()
        result = await repair_cost_estimates(
            session,
            models=["gpt-6-astra", "gpt-5.3-codex-spark"],
            since=when,
            until=when + timedelta(hours=1),
            apply=True,
        )
        assert result.changed == 2
        costs = (await session.execute(select(RequestLog.model, RequestLog.cost_usd).order_by(RequestLog.id))).all()
        assert costs == [("gpt-6-astra", 7), ("gpt-6-astra", 1), ("gpt-5.3-codex-spark", None), ("unknown", 1)]
        await session.rollback()
        with pytest.raises(ValueError, match="No published"):
            await repair_cost_estimates(session, models=["unknown"])


@pytest.mark.asyncio
async def test_repair_new_gpt6_models_preview_and_apply(db_setup):
    when = datetime(2026, 9, 29, 10)
    rows = [
        ("gpt-6.1-sol", None, 1.11),
        ("gpt-6-sol", None, 1.115),
        ("gpt-6-luna", None, 0.05575),
        ("gpt-6-astra", "ultrafast", 33.45),
    ]
    async with SessionLocal() as session:
        for index, (model, service_tier, _) in enumerate(rows):
            session.add(
                RequestLog(
                    request_id=f"repair-{index}",
                    requested_at=when,
                    model=model,
                    service_tier=service_tier,
                    status="success",
                    input_tokens=100_000,
                    cached_input_tokens=50_000,
                    cache_write_tokens=10_000,
                    output_tokens=100_000,
                    cost_usd=0,
                )
            )
        await session.commit()

        preview = await repair_cost_estimates(
            session,
            models=[model for model, _, _ in rows],
            since=when,
        )
        assert preview.scanned == 4
        assert preview.changed == 4
        assert preview.missing_cache_write_counts == 0
        assert preview.delta_usd == pytest.approx(sum(expected for _, _, expected in rows))
        assert (await session.scalars(select(RequestLog.cost_usd).order_by(RequestLog.id))).all() == [0, 0, 0, 0]

        await session.rollback()
        applied = await repair_cost_estimates(
            session,
            models=[model for model, _, _ in rows],
            since=when,
            apply=True,
        )
        assert applied.changed == 4
        assert (await session.scalars(select(RequestLog.cost_usd).order_by(RequestLog.id))).all() == [
            pytest.approx(expected) for _, _, expected in rows
        ]
