# Verification

The implementation covers 12 requirements and 37 scenarios across API keys,
account routing, usage refresh, and dashboard presentation. Main specifications
are synchronized with this change. This record describes local verification
completed before the separately authorized commit, deployment and historical
cost repair. It does not claim a pull request or cloud CI result.

## Requirement coverage

| Behavior | Implementation and regression coverage |
| --- | --- |
| GPT-6.1 Sol, Sol, Luna rates and aliases | Central pricing registry; pricing unit cases for cache writes, context boundaries, Fast, Flex and snapshots |
| Astra Ultrafast costs | Explicit rates; request-log API, compact settlement, reservations and historical-repair integration cases |
| Authoritative billable tier | Existing actual-tier precedence remains shared by logs and settlement |
| Pro-family identity and unknown capacities | Plan normalization, usage summary types, account mappers and dashboard endpoint regressions |
| Percentage routing fallback | Capacity-weighted, relative-availability and sequential-drain regressions; known zero remains distinct from unknown |
| Weekly/monthly-only usage | Updater, scheduler recovery, account presentation and load-balancer state regressions |
| Safe primary omission | Exact persisted marker requires a complete successful observation; legacy measured percentages without timing metadata remain evidence; incomplete observations do not clear quota |
| Nullable UI and pooled quota | API-key route/schema tests, monthly pool percentages, dashboard parsing and rendering tests |
| Ultrafast enforcement | Create/update/list tests and request forwarding; denied catalogs do not call upstream |
| Account-level tier evidence | Missing, plan-only and incomplete account catalogs cannot grant Ultrafast; general plan and additional-quota fallbacks cannot bypass the tier gate |
| Credit forecasts | Eligible unknown-capacity pools withhold the forecast and legacy Pro-purchase equivalents, including when an eligible account's history is stale; known-capacity forecast tests remain intact |
| UI evidence | Baseline and updated selectors captured with synthetic fixtures; separate weekly/monthly pool percentages inspected |

## Verified local checks

- Final backend unit run: 5,896 passed, 70 skipped, one environment-dependent baseline test deselected.
- Frontend: 139 test files, 1,073 tests; typecheck, lint and production build passed.
- Final caller-visible API-key, dashboard, account and Codex usage endpoint suite: 181 passed.
- Pricing, API-key, repair, and dashboard product suite: 162 passed before the final catalog/omission refinements; the added incomplete-catalog route cases also passed.
- HTTP Responses, compact, extended proxy and WebSocket suite: 303 passed.
- Final quota/refresher/routing regression slice: 422 passed.
- Backend type checking, Ruff lint, Ruff formatting (924 files), architecture checks and `git diff --check` passed.
- Strict OpenSpec: all 49 main specs and the change passed.
- The read-only cost preview and UI screenshots are recorded in [context.md](context.md).

## Environment limits

The release-cleanup dry-run test invokes `/usr/bin/python3` through a deliberately
restricted PATH and fails because the machine's Xcode license is not accepted.
The same failure was reproduced in the unchanged original checkout. It is
excluded from the final broad unit run. Helm rendering and PostgreSQL-only tests
remain subject to their repository environment skips. No OS license acceptance,
database deployment, container build or cloud CI was performed.

## Review

Independent review found no remaining actionable defects after the refinements.
Only the exact persisted omission marker is treated as absence, and Ultrafast
requires per-account catalog evidence even when the general model catalog is
incomplete. Unknown-capacity aggregation with missing percentages stays
unavailable; Pro monthly usage participates in recovery and warmup supersession;
eligible unknown-capacity accounts prevent partial credit forecasts even with
stale history. Regression tests cover these boundaries.

All 12 delta requirements match the synchronized main specifications. All 12
implementation and verification tasks are complete. Completeness, correctness
and design coherence were checked; the environment limitations above are the
only outstanding validation limits. The verified change is archived at
`openspec/changes/archive/2026-09-29-support-september-2026-openai-launch/`.
