## Context

See proposal.md for motivation. Raw Pro and Pro Max usage responses expose weekly percentage/timing and a separate overage credit balance, not an absolute included weekly allowance. Existing request logs already preserve input and output counts for unknown models.

## Goals / Non-Goals

**Goals:** Learn an account-specific effective allowance from measured traffic, remove mandatory pricing metadata, retain meaningful uncertainty, and keep the compact UI.

**Non-Goals:** Reconstruct OpenAI billing, invent a fixed Pro/Max multiplier, change account routing, or fit an underidentified per-model regression.

## Decisions

Use `(input_tokens + output_tokens) / 1_000_000` as the common local work unit, with the existing reasoning fallback when output is absent. Cache counts are subsets of input and are not added. All model/tier names use the same arithmetic. This unit is observable and additive, and does not imply a hidden provider weighting. A 5M-token interval with 5 percentage points of drawdown estimates 100 units of full allowance.

Retain disjoint complete calibration intervals, percentage rounding thresholds, reset boundaries, robust medians, dispersion checks, and current-window corroboration before prior-window reuse. Do not treat ambiguous missing usage as zero or impute it from request counts. No mandatory price lookup or context-price SQL grouping remains. Preserve public schema compatibility where harmless; legacy unpriced-model diagnostics remain empty because pricing does not affect completeness.

Keep the forecast conditional on the account's observed workload mix. A new model mix or cache fraction may change the empirical capacity; rolling samples and instability checks expose that change. Learned class coefficients are deferred until identifiable data exists. Fixed cache/output weights were considered but would add unsupported assumptions.

## Risks / Trade-offs

- Equal tokens do not guarantee equal provider quota cost across workloads → state the workload-mix assumption and retain calibration stability checks; report held-out error without claiming validated pool timing.
- Missing measurements can still prevent capacity learning → audit observed failure categories, retain conservative treatment for ambiguous work, and report live evidence limits.
- Unit scale changes → capacity and demand are recomputed together from raw history; no migration or mixed-unit persisted state exists.

## Migration Plan

Run focused unit/API/repository tests and a read-only historical replay. Selectively deploy the tested files into the running checkout with original rollback backups preserved. Restart the LaunchAgent and verify changed PID, readiness and served forecast. Existing one-line rollback restores the pre-repair deployment. No unrelated dirty source is overwritten.
