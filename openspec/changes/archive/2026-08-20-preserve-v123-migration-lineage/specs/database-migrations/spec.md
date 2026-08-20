## ADDED Requirements

### Requirement: Applied fork revisions remain immutable and discoverable

The migration graph MUST retain the deployed realtime-call-binding revision and its deployed lineage-merge revision with their original filenames, revision identifiers, parent identifiers, and file contents. The system MUST NOT reparent, rename, rewrite, or replace either applied revision when integrating a newer upstream release.

#### Scenario: Build recognizes the deployed fork head

- **GIVEN** a database is stamped at `20260726_000000_merge_realtime_call_bindings_and_useragent_families`
- **WHEN** migration state is inspected by the v1.23-based build
- **THEN** the stamped revision is present in the build's Alembic graph with its original parents
- **AND** the database is not classified as newer than or unknown to the build

#### Scenario: Restored revisions remain byte-identical

- **WHEN** the two deployed realtime-call-binding migration files are compared with the revisions shipped by the deployed fork
- **THEN** both files match byte-for-byte
- **AND** their revision and parent identifiers are unchanged

#### Scenario: Restored schema revision remains reversible

- **GIVEN** a disposable database at the parent of `20260723_000000_add_realtime_call_bindings`
- **WHEN** the restored revision is upgraded, downgraded, and upgraded again
- **THEN** the realtime call binding table is created, removed, and recreated without error

### Requirement: Fork and v1.23 lineages converge through an explicit merge revision

The migration graph SHALL append a no-op merge revision whose parents are the deployed fork head `20260726_000000_merge_realtime_call_bindings_and_useragent_families` and the v1.23 head `20260806_120000_add_http_bridge_owner_process_epoch`. The resulting build MUST expose exactly one Alembic head and MUST allow both fresh databases and databases already at the deployed fork head to upgrade to that head without manual stamping.

#### Scenario: Already-deployed fork database upgrades normally

- **GIVEN** a database has applied the deployed fork head and retains its realtime call binding table
- **WHEN** the v1.23-based build upgrades the database to `head`
- **THEN** all pending v1.23 migrations are applied
- **AND** the database finishes at the new merge revision as its only current revision
- **AND** the pre-existing realtime call binding table is preserved

#### Scenario: Retained migration-only table does not cause false drift

- **GIVEN** a database has upgraded to the new merge revision and retains `realtime_call_bindings`
- **WHEN** schema drift is checked against the v1.23 runtime metadata
- **THEN** the retained migration-only table and its indexes are ignored
- **AND** unrelated unmodeled tables continue to be reported as schema drift

#### Scenario: Fresh database reaches the merged head

- **GIVEN** an empty supported database
- **WHEN** migrations upgrade it to `head`
- **THEN** the complete fork and v1.23 lineages are applied
- **AND** migration policy reports one correctly named head

#### Scenario: Merge revision applies without schema changes

- **GIVEN** a database whose current revisions are exactly the two merge parents
- **WHEN** the database upgrades to `head`
- **THEN** the new merge revision becomes the only current revision
- **AND** applying the merge revision does not alter application tables
