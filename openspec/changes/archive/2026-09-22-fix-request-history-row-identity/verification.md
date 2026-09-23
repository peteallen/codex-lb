# Verification

- The new rendered-table regression failed against the original request-ID key:
  four returned attempts rendered as six rows after refresh, with duplicate-key
  warnings. It passes with the persisted log ID as the row key.
- 92 focused frontend tests passed across the request table, dashboard page,
  and dashboard schemas. Targeted ESLint passed. The production build includes
  TypeScript checking and passed.
- All 11 request-log API integration tests passed, including stable distinct
  string IDs for entries sharing request ID, account, and timestamp, repeat
  listing, and pagination. Targeted Ruff passed.
- A temporary browser fixture using the real component reproduced six jumbled
  rows with the old key and exactly four correctly ordered rows with the fix.
  The fixture and preview server were removed after verification.
- Strict validation passed for the change and all 49 existing capability specs.
- The local service was restarted and `/health/ready` reported database and
  bridge-ring health. Live OpenAPI exposes required string `logId`.
- The staged production build was published to `app/static`, keeping old assets
  available to open tabs. HTTP verification matched the new index and entry
  bundle to their on-disk bytes.

The authenticated live history page was not inspected because the available
browser session required sign-in. Browser verification used a synthetic retry
fixture, and live deployment verification used readiness, OpenAPI, and served
assets. Upstream model rejection causality remains outside this UI fix; the
latest recorded rejection at verification was 2026-09-23 03:39:19 UTC.

## Pre-push checks

The user subsequently reported that the dashboard appeared to be working.
The full local CI hook passed frontend lint, type checking, all 1,062 frontend
tests, the production build, backend lint, and backend type checking. Backend
unit tests reached 5,858 passed and 70 skipped, then stopped the gate with four
failures in unchanged areas:

- `test_cleanup_script_dry_run_lists_superseded_pr`: its subprocess encountered
  the machine's unaccepted Xcode license.
- `test_env_example_does_not_force_leader_election_off`: the example settings
  disable leader election.
- `test_claim_ttl_default_derives_from_raised_timeouts_without_explicit_ttl`:
  expected 30 seconds, received 70 seconds.
- `test_settings_multi_replica_defaults`: expected leader election enabled,
  received disabled.

Later full-gate stages did not run. These failures were recorded rather than
expanding this dashboard fix into unrelated settings or release-tooling changes.
Screenshot fixtures also received distinct log IDs; their targeted lint passed.
