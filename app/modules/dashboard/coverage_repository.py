from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import Integer, and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RequestLog
from app.modules.accounts.usage_time_rollup import HOURLY_BUCKET_SECONDS, _requested_at_epoch_bucket_expr, floor_to_hour
from app.modules.accounts.usage_time_rollup_read import epoch_to_datetime
from app.modules.dashboard.coverage_types import CoverageWorkBucket

MAX_LOOKBACK = timedelta(days=14)


class CoverageRepository:
    """Bounded raw request aggregation for weekly coverage calibration.

    The hourly rollup intentionally is not a source for this feature.  It
    lacks the per-request token-completeness evidence needed by the estimator;
    using it would make confidence depend on whether a fold happened.
    The raw query remains bounded and returns aggregates only; no ORM request
    rows are materialized.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def work_history(
        self, account_ids: list[str], since: datetime, until: datetime
    ) -> dict[str, list[CoverageWorkBucket]]:
        if not account_ids:
            return {}

        # Calibration edges are whole hours.  Keep the same complete-hour
        # contract as the estimator and cap the raw scan at fourteen days.
        end = floor_to_hour(until)
        start = max(floor_to_hour(since), end - MAX_LOOKBACK)
        if end <= start:
            return {}

        bucket = _requested_at_epoch_bucket_expr(self._session, HOURLY_BUCKET_SECONDS)
        tier = func.coalesce(RequestLog.actual_service_tier, RequestLog.service_tier)
        output = func.coalesce(RequestLog.output_tokens, RequestLog.reasoning_tokens)

        dialect = self._session.get_bind().dialect.name
        greatest = func.greatest if dialect == "postgresql" else func.max
        least = func.least if dialect == "postgresql" else func.min
        cached = case(
            (RequestLog.cached_input_tokens.is_(None), 0),
            (RequestLog.input_tokens.is_(None), greatest(0, RequestLog.cached_input_tokens)),
            else_=greatest(0, least(RequestLog.cached_input_tokens, RequestLog.input_tokens)),
        )
        cache_write = case(
            (RequestLog.cache_write_tokens.is_(None), 0),
            (RequestLog.input_tokens.is_(None), greatest(0, RequestLog.cache_write_tokens)),
            else_=greatest(
                0,
                least(RequestLog.cache_write_tokens, RequestLog.input_tokens - cached),
            ),
        )
        # Price/status metadata is deliberately absent from completeness.  A
        # failed request with complete tokens still consumed measurable work,
        # and a missing stored cost does not affect measured tokens.
        # Preserve the historical zero-token success guard because it
        # is a known logging anomaly rather than a measured workload.
        missing = or_(
            RequestLog.input_tokens.is_(None),
            output.is_(None),
            RequestLog.input_tokens < 0,
            output < 0,
            RequestLog.cached_input_tokens < 0,
            RequestLog.cache_write_tokens < 0,
            and_(RequestLog.input_tokens == 0, output == 0, RequestLog.status == "success"),
        )
        missing_flag = case((missing, True), else_=False)

        statement = select(
            RequestLog.account_id,
            bucket.label("bucket_epoch"),
            RequestLog.model,
            tier.label("service_tier"),
            missing_flag.label("missing_flag"),
            func.coalesce(func.sum(RequestLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(output), 0).label("output_tokens"),
            func.coalesce(func.sum(cached), 0).label("cached_tokens"),
            func.coalesce(func.sum(cache_write), 0).label("cache_write_tokens"),
            func.count(RequestLog.id).label("request_count"),
            func.sum(case((missing, 1), else_=0).cast(Integer)).label("missing_count"),
        ).where(
            RequestLog.account_id.in_(account_ids),
            RequestLog.requested_at >= start,
            RequestLog.requested_at < end,
        )
        statement = statement.group_by(
            RequestLog.account_id,
            bucket,
            RequestLog.model,
            tier,
            missing_flag,
        )

        rows = (await self._session.execute(statement)).all()
        result: dict[str, list[CoverageWorkBucket]] = defaultdict(list)
        for row in rows:
            result[row.account_id].append(
                CoverageWorkBucket(
                    account_id=row.account_id,
                    started_at=epoch_to_datetime(int(row.bucket_epoch)),
                    model=row.model,
                    service_tier=row.service_tier,
                    # Context classification was needed only for the former
                    # pricing-based work proxy.  Keep the nullable field for
                    # compatibility with callers that still construct
                    # CoverageWorkBucket values.
                    context_long=None,
                    input_tokens=int(row.input_tokens),
                    output_tokens=int(row.output_tokens),
                    cached_input_tokens=int(row.cached_tokens),
                    cache_write_tokens=int(row.cache_write_tokens),
                    request_count=int(row.request_count),
                    missing_usage_count=int(row.missing_count or 0),
                )
            )
        for account_id in result:
            result[account_id].sort(key=lambda row: row.started_at)
        return dict(result)
