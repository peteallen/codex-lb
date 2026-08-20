"""merge realtime call bindings and request-log useragent family heads

The realtime Voice binding revision was authored (and deployed) against the
``account_refresh_claims`` head before the upstream ``useragent_families``
backfill landed. Reparenting the deployed revision would invalidate the
``alembic_version`` row of every database already stamped at that head, so the
two lineages are joined by this no-op merge instead.

Revision ID: 20260726_000000_merge_realtime_call_bindings_and_useragent_families
Revises:
- 20260723_000000_add_realtime_call_bindings
- 20260722_000000_backfill_request_log_useragent_families
Create Date: 2026-07-26 00:00:00.000000
"""

from __future__ import annotations

revision = "20260726_000000_merge_realtime_call_bindings_and_useragent_families"
down_revision = (
    "20260723_000000_add_realtime_call_bindings",
    "20260722_000000_backfill_request_log_useragent_families",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
