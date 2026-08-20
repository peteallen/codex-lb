## Why

Existing fork deployments have already applied two local Alembic revisions for realtime Voice bindings, while upstream v1.23 continued on a separate migration lineage. A v1.23-based build must retain those immutable revision identities and join both lineages so deployed databases can upgrade normally instead of being rejected as newer than the build or left with multiple heads.

## What Changes

- Restore the two already-applied local migration files without changing their bytes or revision metadata.
- Add an explicit no-op Alembic merge revision joining the deployed fork head with the v1.23 head.
- Treat the retained migration-only binding table as intentional legacy schema so drift checks remain accurate without adding local Voice runtime models.
- Add migration regression coverage for a single-head graph, fresh upgrades, and upgrades from the already-applied fork revision.
- Document the migration-lineage compatibility and operational constraints.
- Do not restore the fork's local Voice runtime implementation or stale-anchor recovery behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `database-migrations`: Require immutable preservation of deployed fork revisions and an explicit merge revision that converges the fork and v1.23 lineages to one head.

## Impact

- Affected code: Alembic revisions under `app/db/alembic/versions/` and migration regression tests.
- Affected operations: fresh database creation and upgrades from the deployed fork's current revision.
- No API, dashboard, runtime Voice, or database-model behavior changes are introduced by this compatibility slice.
