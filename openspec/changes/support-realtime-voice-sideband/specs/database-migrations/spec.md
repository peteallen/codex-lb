# database-migrations delta

## ADDED Requirements

### Requirement: Realtime call bindings use a reversible shared-database migration on a single-head graph

The system SHALL add `realtime_call_bindings` through one Alembic revision
`20260723_000000_add_realtime_call_bindings` whose parent is
`20260713_040000_add_account_refresh_claims`. That parent MUST NOT be changed,
because deployed databases are already stamped at the revision and reparenting
would invalidate their `alembic_version` rows. The table MUST contain
primary-key `call_id`; non-null `account_id`; nullable `api_key_id`; non-null
`created_at` and `expires_at`; and nullable `claim_holder` and
`claim_expires_at`. `account_id` MUST reference `accounts` with cascade delete,
and `api_key_id` MUST reference `api_keys` with cascade delete so key removal
cannot make a previously authenticated binding anonymous. Expiry lookup/cleanup
MUST be indexed.

Because the binding revision was authored against an earlier head than the
concurrent upstream `20260722_000000_backfill_request_log_useragent_families`
lineage, the system MUST join the two lineages with a no-op Alembic merge
revision whose parents are exactly those two revisions, so the graph exposes
exactly one head. Convergence MUST be reachable by `alembic upgrade` alone: a
database already stamped at `20260723_000000_add_realtime_call_bindings` MUST be
able to apply every missing upstream revision and land on the single head
without any manual `stamp`.

Upgrade and downgrade MUST work on SQLite and PostgreSQL-compatible schema
paths, downgrade MUST remove the added table/indexes without changing existing
data, and post-upgrade ORM schema-drift checks MUST report no drift. The table
starts empty and requires no historical backfill.

#### Scenario: Upgrade creates the binding schema without drift

- **GIVEN** a database at revision
  `20260713_040000_add_account_refresh_claims`
- **WHEN** Alembic upgrades to the new head
- **THEN** `realtime_call_bindings` has the declared keys, timestamps, claim
  fields, foreign-key deletion behavior, and expiry index
- **AND** the migration policy reports exactly one head
- **AND** the ORM schema-drift check reports no differences

#### Scenario: A database stamped at the deployed binding revision catches up

- **GIVEN** a database whose `alembic_version` is
  `20260723_000000_add_realtime_call_bindings`
- **WHEN** Alembic upgrades to head
- **THEN** every missing upstream revision is applied
- **AND** `alembic_version` holds exactly the single merge head
- **AND** no manual stamp is required
- **AND** the ORM schema-drift check reports no differences

#### Scenario: Downgrade removes only realtime call bindings

- **GIVEN** a database upgraded through the realtime call binding revision
- **WHEN** Alembic downgrades one revision
- **THEN** the realtime binding table and its indexes are removed
- **AND** all pre-existing tables and data remain intact

#### Scenario: API key deletion cannot anonymize a binding

- **GIVEN** a realtime call binding has a non-null API-key foreign key
- **WHEN** that API key is deleted
- **THEN** the binding is deleted by referential action
- **AND** it is not retained with `api_key_id = NULL`
