## Purpose and Scope

This change keeps a v1.23-based fork compatible with databases that already ran the local realtime Voice migrations. The normative behavior is defined in `specs/database-migrations/spec.md`; this file records why the chosen lineage matters operationally.

The scope is migration history only. The local Voice runtime and stale-anchor recovery remain intentionally excluded because v1.23 supplies its own broader runtime behavior.

## Decision and Constraints

An applied Alembic revision is a database-facing identifier, not just a source file. The deployed database records `20260726_000000_merge_realtime_call_bindings_and_useragent_families`, so the build must continue to recognize that exact graph node. The safe convergence mechanism is a later two-parent merge revision. Reparenting, renaming, deleting, or stamping around either local revision would make source history disagree with deployed state.

Both restored migration files therefore remain byte-identical to commit `81359274`. The new merge is schema-neutral and points to the deployed fork head plus the actual v1.23 head.

## Failure Modes

- Omitting the local files makes the deployed database appear newer than or unknown to the build.
- Restoring the local files without another merge leaves two Alembic heads and fails migration policy.
- Reparenting an applied revision can make upgrades appear valid in source while breaking databases stamped with the original graph.
- Dropping the historical binding table in this slice could destroy deployed data even though v1.23 does not consume that table.

## Operational Example

A database stamped at the deployed fork head starts the v1.23-based build. Alembic recognizes that head, applies only the pending v1.23-side descendants, and then records the new two-parent merge revision as the sole current revision. No manual `stamp`, table rewrite, or Voice-runtime port is involved.

Validation uses disposable databases only. Any live migration or service restart requires a separate deployment authorization and copied-database rehearsal.
