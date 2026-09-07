"""Retain cache-write usage for API cost estimates.

Historical counts remain NULL because they cannot be inferred from input usage.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260904_000000_add_request_log_cache_write_tokens"
down_revision = "20260819_000000_merge_realtime_bindings_and_v123_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("request_logs")}
    if "cache_write_tokens" not in columns:
        op.add_column("request_logs", sa.Column("cache_write_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("request_logs")}
    if "cache_write_tokens" in columns:
        with op.batch_alter_table("request_logs") as batch_op:
            batch_op.drop_column("cache_write_tokens")
