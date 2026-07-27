from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.time import utcnow
from app.db.models import RealtimeCallBinding


@dataclass(frozen=True, slots=True)
class RealtimeCallBindingData:
    call_id: str
    account_id: str
    api_key_id: str | None
    created_at: datetime
    expires_at: datetime
    claim_holder: str | None
    claim_expires_at: datetime | None

    def is_expired(self, now: datetime | None = None) -> bool:
        return self.expires_at <= (now or utcnow())


class RealtimeCallBindingConflictError(RuntimeError):
    """Raised when upstream reuses a still-live realtime call id."""


class RealtimeCallBindingsRepository:
    """Shared-database bindings and atomic single-join claims."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        call_id: str,
        account_id: str,
        api_key_id: str | None,
        ttl_seconds: float,
    ) -> RealtimeCallBindingData:
        now = utcnow()
        values = {
            "call_id": call_id,
            "account_id": account_id,
            "api_key_id": api_key_id,
            "created_at": now,
            "expires_at": now + timedelta(seconds=max(1.0, ttl_seconds)),
            "claim_holder": None,
            "claim_expires_at": None,
        }
        # Opportunistic cleanup bounds abandoned pre-open bindings without a
        # scheduler.  A live claimant is retained even when the join-window TTL
        # has elapsed; terminal relay cleanup removes it.
        await self._session.execute(
            delete(RealtimeCallBinding).where(
                RealtimeCallBinding.expires_at <= now,
                or_(
                    RealtimeCallBinding.claim_holder.is_(None),
                    RealtimeCallBinding.claim_expires_at.is_(None),
                    RealtimeCallBinding.claim_expires_at <= now,
                ),
            )
        )

        dialect_name = self._session.get_bind().dialect.name
        if dialect_name == "postgresql":
            insert_stmt = pg_insert(RealtimeCallBinding).values(**values)
        elif dialect_name == "sqlite":
            insert_stmt = sqlite_insert(RealtimeCallBinding).values(**values)
        else:
            raise RuntimeError(f"Realtime call bindings unsupported for dialect={dialect_name!r}")
        stmt = insert_stmt.on_conflict_do_nothing(
            index_elements=[RealtimeCallBinding.call_id],
        ).returning(
            RealtimeCallBinding.call_id,
            RealtimeCallBinding.account_id,
            RealtimeCallBinding.api_key_id,
            RealtimeCallBinding.created_at,
            RealtimeCallBinding.expires_at,
            RealtimeCallBinding.claim_holder,
            RealtimeCallBinding.claim_expires_at,
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        row = result.one_or_none()
        if row is None:
            raise RealtimeCallBindingConflictError(call_id)
        return _binding_from_row(row)

    async def get(self, call_id: str) -> RealtimeCallBindingData | None:
        result = await self._session.execute(
            select(
                RealtimeCallBinding.call_id,
                RealtimeCallBinding.account_id,
                RealtimeCallBinding.api_key_id,
                RealtimeCallBinding.created_at,
                RealtimeCallBinding.expires_at,
                RealtimeCallBinding.claim_holder,
                RealtimeCallBinding.claim_expires_at,
            ).where(RealtimeCallBinding.call_id == call_id)
        )
        row = result.one_or_none()
        return _binding_from_row(row) if row is not None else None

    async def claim(
        self,
        *,
        call_id: str,
        api_key_id: str | None,
        holder: str,
        ttl_seconds: float,
    ) -> RealtimeCallBindingData | None:
        now = utcnow()
        key_predicate = (
            RealtimeCallBinding.api_key_id.is_(None)
            if api_key_id is None
            else RealtimeCallBinding.api_key_id == api_key_id
        )
        result = await self._session.execute(
            update(RealtimeCallBinding)
            .where(
                RealtimeCallBinding.call_id == call_id,
                key_predicate,
                RealtimeCallBinding.expires_at > now,
                or_(
                    RealtimeCallBinding.claim_holder.is_(None),
                    RealtimeCallBinding.claim_expires_at.is_(None),
                    RealtimeCallBinding.claim_expires_at <= now,
                ),
            )
            .values(
                claim_holder=holder,
                claim_expires_at=now + timedelta(seconds=max(1.0, ttl_seconds)),
            )
            .returning(
                RealtimeCallBinding.call_id,
                RealtimeCallBinding.account_id,
                RealtimeCallBinding.api_key_id,
                RealtimeCallBinding.created_at,
                RealtimeCallBinding.expires_at,
                RealtimeCallBinding.claim_holder,
                RealtimeCallBinding.claim_expires_at,
            )
        )
        await self._session.commit()
        row = result.one_or_none()
        return _binding_from_row(row) if row is not None else None

    async def renew(self, *, call_id: str, holder: str, ttl_seconds: float) -> bool:
        now = utcnow()
        result = await self._session.execute(
            update(RealtimeCallBinding)
            .where(
                RealtimeCallBinding.call_id == call_id,
                RealtimeCallBinding.claim_holder == holder,
                RealtimeCallBinding.claim_expires_at > now,
            )
            .values(claim_expires_at=now + timedelta(seconds=max(1.0, ttl_seconds)))
            .returning(RealtimeCallBinding.call_id)
        )
        await self._session.commit()
        return result.scalar_one_or_none() is not None

    async def release(self, *, call_id: str, holder: str) -> None:
        await self._session.execute(
            update(RealtimeCallBinding)
            .where(
                RealtimeCallBinding.call_id == call_id,
                RealtimeCallBinding.claim_holder == holder,
            )
            .values(claim_holder=None, claim_expires_at=None)
        )
        await self._session.commit()

    async def delete_claimed(self, *, call_id: str, holder: str) -> None:
        await self._session.execute(
            delete(RealtimeCallBinding).where(
                RealtimeCallBinding.call_id == call_id,
                RealtimeCallBinding.claim_holder == holder,
            )
        )
        await self._session.commit()


def _binding_from_row(
    row: Row[tuple[str, str, str | None, datetime, datetime, str | None, datetime | None]],
) -> RealtimeCallBindingData:
    mapping = row._mapping
    return RealtimeCallBindingData(
        call_id=mapping[RealtimeCallBinding.call_id],
        account_id=mapping[RealtimeCallBinding.account_id],
        api_key_id=mapping[RealtimeCallBinding.api_key_id],
        created_at=mapping[RealtimeCallBinding.created_at],
        expires_at=mapping[RealtimeCallBinding.expires_at],
        claim_holder=mapping[RealtimeCallBinding.claim_holder],
        claim_expires_at=mapping[RealtimeCallBinding.claim_expires_at],
    )
