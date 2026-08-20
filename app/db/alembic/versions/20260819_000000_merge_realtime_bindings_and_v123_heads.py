"""merge deployed realtime bindings and v1.23 heads

The deployed fork is stamped at the realtime-call-binding merge revision,
while v1.23 continues the shared upstream lineage to the HTTP bridge owner
process epoch revision. Preserve both histories and join them without DDL.

Revision ID: 20260819_000000_merge_realtime_bindings_and_v123_heads
Revises:
- 20260726_000000_merge_realtime_call_bindings_and_useragent_families
- 20260806_120000_add_http_bridge_owner_process_epoch
Create Date: 2026-08-19 00:00:00.000000
"""

from __future__ import annotations

revision = "20260819_000000_merge_realtime_bindings_and_v123_heads"
down_revision = (
    "20260726_000000_merge_realtime_call_bindings_and_useragent_families",
    "20260806_120000_add_http_bridge_owner_process_epoch",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
