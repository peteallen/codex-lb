## Context

The deployed fork is currently stamped at `20260726_000000_merge_realtime_call_bindings_and_useragent_families`. That revision joins the fork's durable realtime-call-binding revision with the upstream user-agent-family lineage. The v1.23-based branch instead continues from that shared upstream lineage to `20260806_120000_add_http_bridge_owner_process_epoch` and does not contain either deployed fork revision.

Without the deployed files, startup treats the live revision as unknown to the build. Adding the files alone produces a second Alembic head. See `proposal.md` for the integration motivation and `specs/database-migrations/spec.md` for the compatibility contract.

## Goals / Non-Goals

**Goals:**

- Preserve the exact revision identities and bytes already recorded by deployed databases.
- Produce one Alembic head that is reachable from both the deployed fork head and the v1.23 head.
- Exercise the fresh-install, deployed-upgrade, schema-revision round-trip, and two-parent merge paths on disposable databases.

**Non-Goals:**

- Port the fork's local realtime Voice runtime, repository, model, or API implementation.
- Port stale-anchor recovery behavior.
- Delete the historical `realtime_call_bindings` table or migrate its data to v1.23's sticky-session affinity storage.
- Stamp, downgrade, or otherwise modify the live database.

## Decisions

### Restore the two deployed files verbatim

The two migration files are restored directly from commit `81359274` and guarded by source digests in regression coverage. Their existing parentage remains intact.

Reparenting the first revision onto the v1.23 line or editing the existing merge would make the source graph disagree with databases that already recorded the deployed revision. Adding a legacy-ID remap is also inappropriate because the deployed identifier is valid and should remain first-class.

### Add a new two-parent, no-op merge

A new revision uses the deployed fork head and the actual v1.23 head as its `down_revision` tuple. Its upgrade and downgrade functions perform no DDL because both parents already own their schema changes; the new file only converges graph history.

The alternative—stamping deployed databases directly to the v1.23 head—would skip migrations and require manual database mutation. Replaying or squashing history would likewise lose the exact applied lineage.

### Test graph identity and executable upgrade paths

Regression coverage checks the restored-file digests, exact merge parents, single-head policy, the schema-changing restored revision's upgrade/downgrade behavior, an upgrade from the deployed fork head, and merge application from an explicit two-parent state. Disposable SQLite databases provide deterministic coverage without touching the live service or database.

Alembic cannot express a relative one-step downgrade from a merge node with two parents because the downward walk is ambiguous. The tests therefore exercise downgrade on the schema-changing restored revision and prove the merge itself is no-op by comparing table sets immediately before and after applying it from both parent heads.

### Retain the historical table as migration-only compatibility schema

The v1.23 Voice implementation stores affinity in sticky sessions and has no ORM model for the fork's `realtime_call_bindings` table. The migration drift checker therefore excludes only this named historical table and its owned schema objects from autogenerate removal diffs. Test database reset drops the table explicitly before ORM-managed tables so its foreign keys cannot block fixture cleanup.

Adding the old ORM model would blur the boundary into porting local Voice runtime code. Dropping the table would discard deployed data without a separate retention decision. A narrow compatibility allowlist preserves the data while still reporting every unrelated rogue table.

## Risks / Trade-offs

- **Historical table remains unused by v1.23 runtime** -> Keep it intact in this compatibility slice so deployed data is not silently discarded; any cleanup requires a separate forward migration and explicit retention decision.
- **Ignoring legacy schema could hide unrelated drift** -> Exclude only the exact `realtime_call_bindings` table and objects owned by it; retain the rogue-table regression test.
- **Fresh installs traverse the historical fork revision** -> Accept the harmless extra table so one graph works for both fresh and already-deployed databases.
- **A binary rollback after later v1.23 migrations may see a newer schema** -> Rehearse deployment and rollback with database copies; do not solve this by stamping or rewriting history.
- **Future edits could accidentally alter an applied file** -> Pin both restored file digests in tests and keep all future corrections forward-only.

## Migration Plan

1. Validate the combined graph and upgrade disposable databases from empty state and from the deployed fork head.
2. Rehearse `codex-lb-db upgrade head`, `current`, and `check` against disposable database copies before any deployment.
3. During a separately authorized deployment, allow the normal migration runner to apply pending v1.23 revisions and finish at the new merge head.
4. Verify the single current revision, migration policy, schema drift, application readiness, and retained historical table.

No live deployment, stamping, or database downgrade is part of this change.
