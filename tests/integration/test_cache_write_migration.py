import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text

from app.db.migrate import _build_alembic_config, check_schema_drift, run_upgrade

pytestmark = pytest.mark.integration


def test_cache_write_migration_preserves_historical_rows_and_round_trips(tmp_path):
    url = f"sqlite:///{tmp_path / 'cache-write.db'}"
    parent = "20260819_000000_merge_realtime_bindings_and_v123_heads"
    run_upgrade(url, parent, bootstrap_legacy=False)
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO request_logs (request_id,model,status,input_tokens,output_tokens,cost_usd) "
                "VALUES ('old','gpt-6-astra','success',100,20,0.002)"
            )
        )
    run_upgrade(url, "head", bootstrap_legacy=False)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT cache_write_tokens,cost_usd FROM request_logs")).one() == (None, 0.002)
    assert check_schema_drift(url) == ()
    command.downgrade(_build_alembic_config(url), parent)
    assert "cache_write_tokens" not in {c["name"] for c in inspect(engine).get_columns("request_logs")}
    run_upgrade(url, "head", bootstrap_legacy=False)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT cache_write_tokens,cost_usd FROM request_logs")).one() == (None, 0.002)
    engine.dispose()
