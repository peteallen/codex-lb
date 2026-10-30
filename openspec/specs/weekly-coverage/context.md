# Weekly coverage context

Normative behavior lives in [spec.md](spec.md). The user guide is
[docs/weekly-coverage.md](../../../docs/weekly-coverage.md).

## Purpose and scope

The useful question is whether continued work will leave the entire eligible
pool empty before a reset restores service. Individual exhaustion dates cannot
answer that question because work transfers to remaining accounts. A time-based
availability view avoids suggesting that account percentages have equal capacity.

This feature is observational. It does not change routing, auto-redeem resets,
include purchased or promotional credits, or predict five-hour limits.

## Compact overview

The default card follows the original visual prototype: one time axis, a pool
row, slim account rows and reset diamonds. Muted blue shows availability, brown
marks pool gaps, gray marks account exhaustion, and a neutral pattern shows
unknown time. A single closed Details
disclosure keeps calibration evidence, excluded accounts, dates and warnings
available without making the overview a diagnostic report.

When the pool cannot be simulated, fresh account rows show their independent
pace only up to the current reset. For example, an account with two days left
that is projected to empty tomorrow shows one blue day, one gray day, a reset
diamond and then unknown time. The pool stays unknown: these rows do not establish
that another account can absorb the extra demand. Stale account rows have no
available segment. The visible caption discloses that transferred traffic is not
modeled in this state.

On narrow screens, the timeline and shared legend remain visible. Full names,
individual outcomes, interval dates and reset times remain available
through accessible descriptions and Details.

## Capacity evidence

The provider rate-limit feed supplies usage percentages and reset timing. It does
not document an account-specific absolute weekly Pro allowance. Plan names are
therefore not used as fixed capacity multipliers. Public credits for overage usage
are a separate billing concept; their numbers do not establish included quota.

Sources consulted for the design:

- [Rate-limit feed](https://learn.chatgpt.com/docs/app-server#6-rate-limits-chatgpt)
- [Codex pricing](https://learn.chatgpt.com/docs/pricing)
- [Pro tiers](https://help.openai.com/en/articles/9793128-about-chatgpt-pro-tiers)

One local work unit is one million measured input plus output tokens. Reasoning
tokens supply output only when the output measurement is absent. Cached input
and cache-write counts are subsets of input and are not added again. Model names,
context sizes and service-tier names do not require a published pricing entry.
For example, five million tokens consuming five percentage points estimates a
full allowance of one hundred million tokens (100 local work units).

The account-specific estimate is the robust median of observed work divided by
its measured quota fraction. It is recomputed on projection refresh, with no
new settings, database migration or persisted allowance ledger. These are local
work units, not provider credits. The estimate assumes a similar model, speed,
context and cache mix continues. Equal raw token totals need not cost OpenAI the
same quota; rolling observations and dispersion checks can expose changes, but
do not prove that traffic transferred between accounts has the same cost mix.
Fixed guessed model multipliers and an underidentified per-model regression are
avoided in this version.

Account-scoped complete-hour work reads aggregate at most fourteen days of raw
requests in SQL, retaining token totals and completeness evidence. Existing
hourly rollups lack token-completeness evidence, so they are not used for
calibration. Folding does not remove raw rows; the supported raw retention
minimum of thirty days exceeds this lookback. Hidden and warmup work remain
part of consumption.

Calibration uses at least three disjoint intervals spanning at least six hours,
each at least two hours long with at least two percentage points of drawdown.
Quota observations are interpolated onto complete-hour work boundaries, with
no interpolation across gaps longer than two hours. Median capacity estimates
must have median absolute deviation no greater than 75% of their median.
Counter drops of at least half a percentage point start new evidence regimes.
A deadline jump alone is treated as drift; a coherent deadline jump with a
material quota drop marks a reset. Small timestamp jitter is tolerated.

## Forecast assumptions

Each account contributes demand equal to its current used fraction times its
estimated full allowance, divided by elapsed time in its current weekly window.
The sum of those demands continues when accounts empty. Reset replenishment
replaces a balance instead of adding to it. Future reset dates repeat weekly.

For example, two accounts each using ten work units per hour create twenty units
per hour of pool demand. When one empties, the remaining account serves twenty,
until either another reset returns capacity or the pool empties. Minimum reserve
is the lowest pool balance divided by that continuing demand.

Routing is an approximation of the configured strategy. Account stickiness,
model access, health decisions and demand outside the proxy may differ from the
simulation. Unsupported allocation and incomplete evidence never become a
reassuring coverage headline.

## Failure modes and verification

Reset changes, counter regressions, stale observations, saturated intervals,
incomplete token accounting and unexplained drawdown can prevent calibration.
Incomplete intervals are discarded individually without permanently vetoing
otherwise sufficient stable evidence. Request failure with complete tokens and a
missing stored price are not themselves missing usage. Unknown models and tiers
contribute their measured tokens. Ambiguous missing tokens are not imputed from
request counts or assumed to consume zero quota.

New accounts and a new quota regime may need additional observations. Known
limitations remain visible in the UI instead of treating unknown capacity as
zero demand or silently omitting the affected account.

An exhausted account can retain a capacity estimate from earlier uncensored
intervals in the same window, then return at its reported reset. Its demand
still follows the observed current-window average. A visible warning explains
that saturated counters cannot reveal unmet demand. An elapsed reported reset
requires a new observation instead of advancing the old balance to a new week.

Recent observations from before an ordinary scheduled reset can contribute to
rolling calibration when new-window evidence corroborates the same capacity
scale. Intervals never cross a reset. Uncorroborated, stale, regressed or
incompatible regimes remain unavailable rather than assuming an unchanged plan.

Fresh valid quota observations also produce independent percentage-based account
projections even when work calibration is unavailable. For example, 40% consumed
over four days is 10 percentage points per day: that account would finish its
seven-day window with about 30% remaining if its own pace continued. Extra traffic
from another exhausted account can change that outcome. The UI distinguishes
these projections from the shared-demand simulation and never sums percentages
across unequal accounts.

Historical validation uses the read-only `scripts.weekly_coverage_backtest.py`
command. Its report distinguishes usable calibration evidence from whole-pool
prediction coverage. Current account eligibility is not a historical audit trail;
historical results cannot prove prior routing, eligibility or outage behavior.
The original implementation change records its aggregate snapshot result in
[`notes.md`](../../changes/archive/2026-10-02-add-weekly-coverage-forecast/notes.md) and keeps
the screenshot evidence with that change. The evidence-recovery repair also
records an anonymized replay report with its verification notes. Under the earlier pricing-based normalization, its retained
history produced 59 scorable account-drawdown intervals, with median absolute
error of 0.79 percentage points and 95th-percentile error of 2.09 percentage
points. No historical cutoff had a ready complete pool, so these account-level
measurements do not validate pool interruption timing.

The initial retained-history audit did not contain enough ready account evidence
to validate a complete-pool forecast. This release therefore makes no measured
claim about interruption-timing accuracy; learning/limited states are expected
when those same evidence gaps occur in current data.

## Empirical token normalization validation

The 2026-10-05 read-only replay of the current eligible cohort evaluated 98 daily
cutoffs with a fourteen-day lookback and seven-day holdout. It scored 43 complete
account-drawdown intervals: median absolute error 0.945 percentage points and
95th-percentile error 5.401 points. Thirty candidate intervals were incomplete
and one had unexplained work. Twenty-five account/cutoff estimates were ready,
but no cutoff had a ready complete pool. These measurements do not validate
pool interruption timing. The report is retained with the
`empirical-weekly-work-units` archived change.

The live snapshot had usable sample counts 0, 1, 3, 2 and 2 across five eligible
accounts. One account was ready; missing measurements and unexplained quota
movement still limited the others. Unknown model prices no longer blocked any
account. Some failures clearly reject before work, but other failures may have
consumed quota. The implementation does not infer zero consumption from error
codes or absent timing markers.
