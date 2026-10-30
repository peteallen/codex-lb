# Verification: empirical-weekly-work-units

## Completeness and correctness

The local unit is one million input plus output tokens. Repository and backtest
preserve the reasoning fallback, missing-usage evidence and bounded raw-history
reads. Pricing imports and context-price SQL are removed. Unknown models and
tiers contribute measured work; cache fields are not counted twice. Public
`unpricedModels` remains an empty compatibility field. The UI's closed Details
section discloses the workload-mix assumption without adding default-card noise.

Scenarios map to unit tests for unknown models/tiers and the 5M/5% example;
repository tests for additive aggregation and fold invariance; API regressions
for pooled forecasts from mixed known/unknown models, and limited forecasts when
those same requests lack tokens. Existing reset, stale, saturation, outside
usage, incompatible prior evidence and routing tests pass.

## Checks

- 68 focused backend unit/repository/API/backtest tests passed.
- 55 focused frontend component/schema tests passed.
- Python Ruff and scoped ty checks passed; frontend typecheck, lint and build passed.
- Strict change validation and all 50 main OpenSpec specifications passed.
- Read-only SQLAlchemy live work read completed in 0.121 seconds for 2,198 aggregate buckets.
- Historical replay: 43 scorable account intervals, median absolute error 0.945 percentage points, p95 5.401. See backtest.json.
- No complete-pool historical cutoffs were ready. Pool interruption accuracy remains unvalidated.

## Coherence and limitations

No persistent allowance, migration, pricing fallback or inferred Pro/Max ratio
was introduced. The live evidence remains limited: one ready account, three
learning accounts with 1/2/2 samples, and Pro Max with no usable interval. Missing
token data stays uncertain; no error code is assumed to mean zero work.

The existing zero-usage wording repair is included: Details says no usage was
observed instead of implying a calibrated 100 percent remaining-at-reset result.
The compact timeline geometry is unchanged.

## Deployment

Independent read-only review found no actionable defects. The 60 focused unit/API
tests also passed against the deployed checkout before restart.

Selective deployment preserved original rollback backups and unrelated dirty
source. The LaunchAgent restarted successfully: listener PID 52115 became 60802,
with cwd `/Users/pete/workspace/codex-lb`. Fresh `/health/ready` returned HTTP 200
and status `ok`. Served index and all 20 directly referenced assets matched the
tested build; index SHA-256:
`a1864a650610fd974288a68e6f2ccbbdea7e4d0146de0f9687ff0df4433397f3`.

The rollback script passed integrity verification after deployment:
`bash /Users/pete/workspace/codex-lb/.local/rollback-weekly-coverage.sh`.

The authenticated live dashboard showed the new 1/2/2/0 sample counts for
learning/limited accounts and the ready fifth account. No unpriced-model warning
remained, and the measured-token workload-mix wording appeared in Details.
With Details closed, the card was still 398 CSS pixels high. The served pool
correctly remained unavailable. No critical or warning review findings remain;
all specified scenarios are covered. Complete-pool accuracy is explicitly
unvalidated rather than a release claim.
