from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.db.migrate import _build_alembic_config, check_migration_policy, check_schema_drift, run_upgrade
from app.db.migration_url import to_sync_database_url

pytestmark = pytest.mark.integration

_REPOSITORY_ROOT = Path(__file__).parents[2]
_MIGRATIONS_DIR = _REPOSITORY_ROOT / "app" / "db" / "alembic" / "versions"
_BINDING_PARENT_REVISION = "20260713_040000_add_account_refresh_claims"
_DEPLOYED_BINDING_REVISION = "20260723_000000_add_realtime_call_bindings"
_DEPLOYED_FORK_HEAD = "20260726_000000_merge_realtime_call_bindings_and_useragent_families"
_V123_HEAD = "20260806_120000_add_http_bridge_owner_process_epoch"
_MERGED_HEAD = "20260819_000000_merge_realtime_bindings_and_v123_heads"
_DEPLOYED_MIGRATION_DIGESTS = {
    f"{_DEPLOYED_BINDING_REVISION}.py": "e81d297abe2f8a17c1e538bd86db53c78a984c8f525748b5edd2471aad453220",
    f"{_DEPLOYED_FORK_HEAD}.py": "21779e229547703da1023cf580c17555a874e3d6bedd057568cfc29fdb18dc1e",
}


@pytest.mark.parametrize(("filename", "expected_digest"), _DEPLOYED_MIGRATION_DIGESTS.items())
def test_deployed_realtime_binding_migration_sources_remain_byte_identical(
    filename: str,
    expected_digest: str,
) -> None:
    source = (_MIGRATIONS_DIR / filename).read_bytes()

    assert sha256(source).hexdigest() == expected_digest


def test_v123_compatibility_merge_has_exact_parents_and_single_head(tmp_path: Path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'migration-policy.sqlite'}"
    config = _build_alembic_config(db_url)
    script_directory = ScriptDirectory.from_config(config)

    assert script_directory.get_heads() == [_MERGED_HEAD]
    merge_revision = script_directory.get_revision(_MERGED_HEAD)
    assert merge_revision is not None
    assert isinstance(merge_revision.down_revision, tuple)
    assert set(merge_revision.down_revision) == {
        _DEPLOYED_FORK_HEAD,
        _V123_HEAD,
    }
    assert check_migration_policy(db_url) == ()


def test_deployed_realtime_binding_revision_upgrade_and_downgrade(tmp_path: Path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'realtime-binding-round-trip.sqlite'}"
    sync_url = to_sync_database_url(db_url)
    config = _build_alembic_config(db_url)

    run_upgrade(db_url, _BINDING_PARENT_REVISION, bootstrap_legacy=False)
    engine = create_engine(sync_url, future=True)
    try:
        command.upgrade(config, _DEPLOYED_BINDING_REVISION)
        with engine.connect() as connection:
            assert inspect(connection).has_table("realtime_call_bindings")

        command.downgrade(config, _BINDING_PARENT_REVISION)
        with engine.connect() as connection:
            assert not inspect(connection).has_table("realtime_call_bindings")

        command.upgrade(config, _DEPLOYED_BINDING_REVISION)
        with engine.connect() as connection:
            assert inspect(connection).has_table("realtime_call_bindings")
    finally:
        engine.dispose()


def test_deployed_fork_head_upgrades_to_v123_merged_head(tmp_path: Path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'deployed-fork-upgrade.sqlite'}"
    sync_url = to_sync_database_url(db_url)

    deployed = run_upgrade(db_url, _DEPLOYED_FORK_HEAD, bootstrap_legacy=False)
    assert deployed.current_revision == _DEPLOYED_FORK_HEAD

    engine = create_engine(sync_url, future=True)
    try:
        with engine.connect() as connection:
            assert inspect(connection).has_table("realtime_call_bindings")

        upgraded = run_upgrade(db_url, "head", bootstrap_legacy=False)
        assert upgraded.current_revision == _MERGED_HEAD

        with engine.connect() as connection:
            tables_at_head = set(inspect(connection).get_table_names())
            current_revisions = {
                str(row[0]) for row in connection.execute(text("SELECT version_num FROM alembic_version"))
            }
        assert "realtime_call_bindings" in tables_at_head
        assert current_revisions == {_MERGED_HEAD}
        assert check_schema_drift(db_url) == ()

    finally:
        engine.dispose()


def test_v123_compatibility_merge_is_noop_from_both_parents(tmp_path: Path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'parallel-parent-merge.sqlite'}"
    sync_url = to_sync_database_url(db_url)
    config = _build_alembic_config(db_url)

    run_upgrade(db_url, _DEPLOYED_FORK_HEAD, bootstrap_legacy=False)
    command.upgrade(config, _V123_HEAD)

    engine = create_engine(sync_url, future=True)
    try:
        with engine.connect() as connection:
            tables_before_merge = set(inspect(connection).get_table_names())
            parent_revisions = {
                str(row[0]) for row in connection.execute(text("SELECT version_num FROM alembic_version"))
            }
        assert parent_revisions == {_DEPLOYED_FORK_HEAD, _V123_HEAD}

        command.upgrade(config, "head")
        with engine.connect() as connection:
            tables_after_merge = set(inspect(connection).get_table_names())
            final_revisions = {
                str(row[0]) for row in connection.execute(text("SELECT version_num FROM alembic_version"))
            }
        assert tables_after_merge == tables_before_merge
        assert final_revisions == {_MERGED_HEAD}
    finally:
        engine.dispose()
