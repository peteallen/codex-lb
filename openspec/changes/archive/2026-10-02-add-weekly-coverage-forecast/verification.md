# Verification: weekly coverage

Verified locally on 2026-10-02. Implementation is uncommitted in the isolated
`weekly-coverage` worktree. No deployment or cloud CI claim is made.

## Requirement coverage

| Requirement | Implementation and evidence |
| --- | --- |
| Eligibility and complete evidence | Pro-family/status filtering, monthly-regime guard, primary-slot weekly normalization, stale/elapsed checks; API tests exercise learning, exclusions, empty pools and monthly/elapsed windows. |
| Empirical capacity and current-window demand | Model/cache/speed work weights, disjoint complete-hour calibration, reset/regression boundaries and insufficient-evidence gates; unit tests cover interpolation, sparse history, drawdown and retained uncensored evidence for exhausted accounts. |
| Continuing demand and staggered resets | Hourly allocation updates plus exhaustion/reset events, fourteen-day horizon and reserve; tests prove transferred demand, repeated gaps, reset replacement, exact reset/exhaustion ordering and sub-microsecond progress. |
| Coverage presentation | Seven/fourteen-day controls, first-gap/recovery headline, reserve, account evidence and reasons; component and route tests cover learning, exclusions, horizon gaps, keyboard controls and replacement of the legacy card. |
| Historical validation and bounded reads | Account-scoped bounded SQL aggregation with watermark partitioning; integration tests prevent raw/rollup overlap. Read-only backtest tests prove no future calibration buckets, no reset/censor scoring, actual-speed grouping, WAL visibility and rejected writes. |
| Existing dashboard contract | Additive optional projections field; overview remains independent, legacy API data remains compatible, and removed pooled quota charts stay absent. |

## Checks

- The repository unit gate passed with 5934 tests passed and 70 skipped; the final weekly-coverage unit/API/backtest slice passed 35 tests.
- Ruff and `ty` passed for the changed dashboard code and backtest. Test-file lint passed.
- Full frontend tests passed with 1065 tests across 138 files; frontend typecheck, lint and production build passed.
- Frontend typecheck, lint and production build passed.
- All sixteen existing screenshot scenes passed during implementation. The final four coverage scenes and two standard dashboard scenes were refreshed successfully, with narrow-screen overflow checked.
- Strict OpenSpec validation passed for the change and all 50 main capabilities.
- `git diff --check` passed.

The final reset-regime regression test also confirms that a large reset-date
movement without a quota drop is treated as timestamp drift, while a meaningful
percentage regression still starts a new calibration regime.

## Visual evidence

Fixtures are synthetic and contain no live account credentials or usage.

- [Legacy comparison](../../../../docs/screenshots/dashboard-weekly-coverage-legacy.jpg)
- [Ready desktop](../../../../docs/screenshots/dashboard-weekly-coverage-ready.jpg)
- [Ready narrow](../../../../docs/screenshots/dashboard-weekly-coverage-ready-narrow.jpg)
- [Learning](../../../../docs/screenshots/dashboard-weekly-coverage-learning.jpg)

## Material limitation

[Historical validation](notes.md) is unavailable for predictive accuracy: no
complete pool met the evidence safeguards at the replayed cutoffs, and there
were no usable held-out intervals from a ready account estimate. This is not
represented as successful accuracy validation. The reproducible read-only path,
reported coverage limits and conservative product states satisfy the agreed
validation requirement. Live workload mix, outside usage, model access and
sticky routing remain disclosed approximations.

All implementation tasks are complete. Specs and stable context are synced.
No unresolved implementation or contract mismatch was found in the final review.
