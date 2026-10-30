# Verification: fix-current-account-quota

Verified September 29, 2026.

## Completeness and correctness

All implementation and delivery-preparation tasks are complete. Main specifications
are synchronized. The quota mapper, routing state construction, Force Probe settlement,
background recovery/warmup selection and usage summary share the current monthly-window
predicate. Historical rows and genuine cooldown/quota blocks remain intact.

Route regressions cover account listing and dashboard overview for pro, prolite and
promax, both weekly-after-monthly and monthly-after-weekly. Weekly cases also verify
the usage summary excludes superseded monthly data. Predicate tests cover same-fetch
timing, incomplete rows and absence markers. Routing/probe tests prove exhausted weekly
quota cannot be hidden by an old available monthly balance.

The probe transport is exercised through the real account API with a fake upstream
429. It omits the unsupported field, refreshes usage and preserves the quota block.
Frontend tests cover 2xx, 400, 429, network failure and unknown status notifications,
including query invalidation.

## Checks

- Initial backend regression suite: 528 passed.
- Final focused usage/probe/concurrency suite: 269 passed (overlaps the initial suite).
- Affected frontend suite: 27 passed.
- Ruff, backend typecheck, frontend lint/typecheck/build and diff whitespace checks passed.
- Strict OpenSpec validation: all 49 main specs and this change passed.
- Browser rendering verified the actual mapper's synthetic before/after payloads:
  Monthly 100% became Weekly 0%, with Quota exceeded and the weekly reset.
- A browser Force Probe fixture showed the upstream HTTP 429 error notification.

## Incident evidence and limits

The observed live probe failed with HTTP 400 because max_output_tokens is unsupported.
The otherwise identical corrected request returned HTTP 429 usage_limit_reached with
a weekly window and its reset deadline. This confirms quota exhaustion independently
of the stale display. The correction does not replenish quota or redeem reset credits.

The live API requires dashboard authentication. Deployment verification therefore
checks service readiness, served asset hashes, source identity and a read-only rendering
of the affected account's live database observations. Synthetic screenshots contain no
real account credentials or identifying details.

## Rollout preparation

The previous live source files and frontend build are backed up. Thirteen unrelated
local files are hash-tracked for preservation. Deploy by fast-forwarding the existing
checkout, retaining old hashed assets, replacing the index last and restarting the
LaunchAgent to load the backend correction. Record final runtime evidence in the
ignored deployment backup directory. No database rewrite or migration is needed.

No unresolved implementation or verification finding remains.
