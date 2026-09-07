"""Reprice retained usage without discarding already-pruned rollup history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.usage.logs import calculated_cost_from_log
from app.core.usage.pricing import get_pricing_for_model
from app.db.models import (
    AccountUsageRollup,
    AccountUsageRollupState,
    ApiKeyUsageRollup,
    RequestDemandQuarterRollup,
    RequestLog,
    RequestUsageHourlyRollup,
)
from app.db.session import sqlite_writer_section
from app.modules.accounts.usage_rollup import lock_fold_state
from app.modules.accounts.usage_time_rollup import WARMUP_REQUEST_KINDS, epoch_seconds, to_dimension


@dataclass
class CostRepairSummary:
    scanned: int = 0
    changed: int = 0
    missing_cache_write_counts: int = 0
    delta_usd: float = 0.0


def _is_unpublished_spark(model: str) -> bool:
    model = model.lower()
    return model == "gpt-5.3-codex-spark" or model.startswith("gpt-5.3-codex-spark-20")


async def repair_cost_estimates(
    session: AsyncSession,
    *,
    models: list[str],
    since: datetime | None = None,
    until: datetime | None = None,
    apply: bool = False,
    batch_size: int = 500,
) -> CostRepairSummary:
    """Commit bounded batches only when explicitly applying; preview is read-only.

    Custom model sources and quota enforcement counters are never repriced.
    Fold locks serialize repairs against aggregation and account lifecycle writes.
    """
    if not models or batch_size < 1:
        raise ValueError("Provide explicit models and a positive batch size")
    if since is not None and until is not None and since >= until:
        raise ValueError("since must precede until")
    for model in models:
        if get_pricing_for_model(model) is None and not _is_unpublished_spark(model):
            raise ValueError(f"No published API pricing for {model}")
    summary = CostRepairSummary()
    last_id = 0
    # New traffic arriving during repair is handled by current pricing normally.
    max_id = await session.scalar(select(func.max(RequestLog.id))) or 0
    await session.rollback()
    while last_id < max_id:
        async with sqlite_writer_section():
            try:
                session.expire_all()
                if apply:
                    await lock_fold_state(session)
                state = await session.get(AccountUsageRollupState, 1)
                stmt = select(RequestLog).where(
                    RequestLog.id > last_id,
                    RequestLog.id <= max_id,
                    RequestLog.model.in_(models),
                    RequestLog.model_source_id.is_(None),
                    RequestLog.model_source_kind.is_(None),
                    (RequestLog.source.is_(None) | (RequestLog.source != "model_source")),
                )
                if since is not None:
                    stmt = stmt.where(RequestLog.requested_at >= since)
                if until is not None:
                    stmt = stmt.where(RequestLog.requested_at < until)
                logs = list((await session.scalars(stmt.order_by(RequestLog.id).limit(batch_size))).all())
                if not logs:
                    await session.rollback()
                    break
                for log in logs:
                    summary.scanned += 1
                    price = get_pricing_for_model(log.model)
                    if price is not None and price[1].cache_write_multiplier > 1 and log.cache_write_tokens is None:
                        summary.missing_cache_write_counts += 1
                    new_cost = calculated_cost_from_log(log)
                    # Incomplete usage cannot establish a replacement estimate.
                    if new_cost is None and not _is_unpublished_spark(log.model):
                        continue
                    if new_cost == log.cost_usd:
                        continue
                    delta = (new_cost or 0.0) - (log.cost_usd or 0.0)
                    summary.changed += 1
                    summary.delta_usd += delta
                    if apply:
                        await _mirror_cost_delta(session, state, log, new_cost, delta)
                        log.cost_usd = new_cost
                last_id = logs[-1].id
                if apply:
                    await session.commit()
                else:
                    await session.rollback()
            except BaseException:
                await session.rollback()
                raise
    return summary


async def _mirror_cost_delta(
    session: AsyncSession,
    state: AccountUsageRollupState | None,
    log: RequestLog,
    new_cost: float | None,
    delta: float,
) -> None:
    if state is None:
        return
    if log.requested_at < state.hourly_folded_through:
        epoch = epoch_seconds(log.requested_at)
        dimensions = (
            to_dimension(log.account_id),
            to_dimension(log.api_key_id),
            log.model,
        )
        hourly = await session.get(
            RequestUsageHourlyRollup,
            (
                epoch // 3600 * 3600,
                *dimensions,
                to_dimension(log.service_tier),
                log.request_kind,
                log.deleted_at is not None,
            ),
        )
        demand = await session.get(
            RequestDemandQuarterRollup,
            (
                epoch // 900 * 900,
                *dimensions,
                to_dimension(log.reasoning_effort),
                log.request_kind,
                log.status,
                log.deleted_at is not None,
            ),
        )
        if hourly is None or demand is None:
            raise ValueError(f"Missing folded usage for request-log row {log.id}; repair rolled back")
        hourly.cost_usd += delta
        hourly.cost_count += int(new_cost is not None) - int(log.cost_usd is not None)
        demand.cost_usd += delta
    if log.requested_at > state.folded_through or log.request_kind in WARMUP_REQUEST_KINDS:
        return
    if log.api_key_id is not None:
        key = await session.get(ApiKeyUsageRollup, log.api_key_id)
        if key is None:
            raise ValueError(f"Missing API-key lifetime rollup for request-log row {log.id}")
        key.total_cost_usd += delta
    if log.account_id is not None and log.deleted_at is None:
        # Lifetime account totals count only the latest duplicate, unlike time/key totals.
        latest_id = await session.scalar(
            select(func.max(RequestLog.id)).where(
                RequestLog.account_id == log.account_id,
                RequestLog.request_id == log.request_id,
                RequestLog.requested_at == log.requested_at,
                RequestLog.deleted_at.is_(None),
                RequestLog.request_kind.not_in(WARMUP_REQUEST_KINDS),
            )
        )
        if latest_id == log.id:
            account = await session.get(AccountUsageRollup, log.account_id)
            if account is None:
                raise ValueError(f"Missing account lifetime rollup for request-log row {log.id}")
            account.total_cost_usd += delta
