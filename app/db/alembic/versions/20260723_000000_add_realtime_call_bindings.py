"""add durable realtime Voice call bindings

Revision ID: 20260723_000000_add_realtime_call_bindings
Revises: 20260713_040000_add_account_refresh_claims
Create Date: 2026-07-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260723_000000_add_realtime_call_bindings"
down_revision = "20260713_040000_add_account_refresh_claims"
branch_labels = None
depends_on = None

_TABLE_NAME = "realtime_call_bindings"
_ACCOUNT_INDEX = "ix_realtime_call_bindings_account_id"
_API_KEY_INDEX = "ix_realtime_call_bindings_api_key_id"
_EXPIRES_INDEX = "ix_realtime_call_bindings_expires_at"
_CLAIM_EXPIRES_INDEX = "ix_realtime_call_bindings_claim_expires_at"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(_TABLE_NAME):
        return
    op.create_table(
        _TABLE_NAME,
        sa.Column("call_id", sa.String(length=128), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("api_key_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("claim_holder", sa.String(length=128), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("call_id"),
    )
    op.create_index(_ACCOUNT_INDEX, _TABLE_NAME, ["account_id"])
    op.create_index(_API_KEY_INDEX, _TABLE_NAME, ["api_key_id"])
    op.create_index(_EXPIRES_INDEX, _TABLE_NAME, ["expires_at"])
    op.create_index(_CLAIM_EXPIRES_INDEX, _TABLE_NAME, ["claim_expires_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE_NAME):
        return
    op.drop_index(_CLAIM_EXPIRES_INDEX, table_name=_TABLE_NAME)
    op.drop_index(_EXPIRES_INDEX, table_name=_TABLE_NAME)
    op.drop_index(_API_KEY_INDEX, table_name=_TABLE_NAME)
    op.drop_index(_ACCOUNT_INDEX, table_name=_TABLE_NAME)
    op.drop_table(_TABLE_NAME)
