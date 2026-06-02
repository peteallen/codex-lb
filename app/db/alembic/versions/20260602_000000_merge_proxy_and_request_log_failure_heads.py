"""merge proxy routing and request log failure metadata heads

Revision ID: 20260602_000000_merge_proxy_and_request_log_failure_heads
Revises: 20260601_020000_merge_account_proxy_and_upstream_proxy_heads,
    20260601_020000_merge_warmup_and_request_log_failure_heads
Create Date: 2026-06-02
"""

from __future__ import annotations

revision = "20260602_000000_merge_proxy_and_request_log_failure_heads"
down_revision = (
    "20260601_020000_merge_account_proxy_and_upstream_proxy_heads",
    "20260601_020000_merge_warmup_and_request_log_failure_heads",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
