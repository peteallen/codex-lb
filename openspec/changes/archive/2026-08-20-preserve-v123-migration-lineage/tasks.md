## 1. Preserve and Converge Migration History

- [x] 1.1 Restore the two deployed realtime-call-binding migration files byte-for-byte from commit `81359274` and verify their source digests.
- [x] 1.2 Add a correctly named no-op Alembic revision merging the deployed fork head with the v1.23 head.
- [x] 1.3 Preserve the migration-only binding table without false drift or test-database foreign-key cleanup failures.

## 2. Add Regression Coverage

- [x] 2.1 Add coverage that pins the restored files and verifies the exact merge parents and single graph head.
- [x] 2.2 Add disposable-database coverage for the restored schema revision round-trip, upgrading from the deployed fork head, and applying the no-op merge from both parents.
- [x] 2.3 Verify the exact legacy-table drift exception while retaining detection for unrelated rogue tables.

## 3. Validate the Compatibility Slice

- [x] 3.1 Run focused migration unit and integration tests.
- [x] 3.2 Run `codex-lb-db` upgrade, current, and check flows on disposable databases.
- [x] 3.3 Run Ruff, ty, strict change validation, and full OpenSpec spec validation.
