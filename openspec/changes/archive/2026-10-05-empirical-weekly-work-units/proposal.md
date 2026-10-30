## Why

The weekly pool cannot learn capacity for recorded traffic such as `codex-auto-review` because its work unit depends on a published model price. The provider's percentage windows and separate overage-credit balance do not supply an absolute included weekly allowance.

## What Changes

- Define a local work unit from measured input plus output tokens, independent of model pricing, context pricing and service-tier names.
- Learn each account's capacity from observed work divided by weekly quota drawdown; keep reset, completeness and stability safeguards.
- Describe the estimate as conditional on the observed workload mix continuing and remove unpriced-model blocking diagnostics.
- Validate against deterministic API tests and retained-history replay without changing routing or the compact card layout.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `weekly-coverage`: empirical token normalization, aggregation invariance and evidence recovery without a pricing catalog dependency.

## Impact

Coverage work accounting, calibration diagnostics, historical validation, dashboard evidence wording and documentation. No new setting, dependency, database migration or persistent allowance ledger. Existing work-unit numbers change scale; they remain relative estimates, never provider credits.
