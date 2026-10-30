## 1. Work accounting

- [x] 1.1 Replace price-dependent work with additive measured token units and preserve completeness guards.
- [x] 1.2 Align bounded SQL aggregation and historical replay with the normalization.
- [x] 1.3 Remove unpriced-model blocking diagnostics and document the workload-mix assumption.

## 2. Verification

- [x] 2.1 Cover unknown models/tiers, 5M tokens per 5 percent, cache subsets, aggregation invariance and missing usage at unit/repository/API boundaries.
- [x] 2.2 Run focused tests, lint/type checks and read-only live-history audit/backtest; record actual limitations.
- [x] 2.3 Sync specifications/context and validate OpenSpec strictly.

## 3. Deployment

- [x] 3.1 Preserve rollback backups and selectively deploy tested files; restart and verify the local instance.
- [x] 3.2 Verify and archive the completed change, retaining concise evidence and rollback instructions.
