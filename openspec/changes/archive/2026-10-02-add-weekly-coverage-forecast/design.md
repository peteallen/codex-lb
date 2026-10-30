## Context

OpenAI exposes weekly percentages and reset timestamps, not reliable absolute Pro allowances. Existing usage snapshots and request history can support empirical calibration without persisting another competing quota ledger. Existing dashboard projections are loaded independently of initial overview rendering.

## Goals / Non-Goals

**Goals:** Forecast interruption intervals under current-window average demand; expose evidence quality; preserve per-account resets and account eligibility; validate using retained history.

**Non-Goals:** Routing changes, purchased/promotional-credit forecasting, automatic resets, five-hour forecasts, guaranteed throughput or provider-billing reconstruction.

## Decisions

- Calibrate each account separately from model/speed/cache-weighted work and measured percentage drawdown within its current quota regime. Standard model token prices supply relative work weights only; they are not claimed to be subscription prices or credits. Included-use speed factors are distinct from purchased-credit billing. Unsupported models/tiers lower coverage rather than silently counting zero work.
- Recompute rolling estimates from retained data when projections are requested. Use bounded, account-scoped history and SQL aggregation; do not load all request-log ORM rows or share an AsyncSession across concurrent tasks. Reuse hourly rollups with their fold watermark so retained and raw data cannot double count. No new migration or operator setting is needed.
- Require meaningful multi-hour percentage movement, multiple usable calibration intervals and bounded dispersion. Meaningful percentage decreases, or material drops paired with coherent reset-horizon changes, invalidate affected calibration; timestamp drift alone does not. Saturation, missing token accounting and unexplained drawdown also invalidate affected intervals. New/reset accounts remain learning until evidence exists. Historical validation records observed accuracy and limitations, not an invented probability.
- Calculate demand from used percentage times estimated full capacity divided by time elapsed in each account's current weekly window. Sum demand across eligible accounts; never discard an exhausted account's demand. Continue this workload through future resets, replacing each reset account's remaining balance with its estimated full allowance.
- Simulate allocation using configured strategy where supportable. Disclose that sticky sessions, model-specific access and demand outside the proxy can differ from the simulation. Unsupported routing modes or incomplete evidence produce a limited forecast instead of a confident covered state.
- Expose one additive `weeklyCoverage` payload on dashboard projections. Keep the old weekly-credit payload compatible. The coverage UI supersedes the old card when this new payload is present. Default to seven days, offer fourteen, and report a gap beyond the initial viewport explicitly.
- Track account and pool availability intervals plus minimum remaining work expressed as hours at forecast demand. Do not show summed account percentages or fictitious credit balances. Use approximate date/time labels and an explicit current-window-average assumption.

## Risks / Trade-offs

- Rounded/delayed quota counters and outside usage can bias calibration → multi-hour evidence, conservative learning/limited states and visible assumptions.
- Model or entitlement changes can invalidate learned work weights → window/regime boundaries and dispersion checks; avoid plan-price multipliers.
- Retention can erase calibration data → reuse available rollups, expose inadequate evidence instead of false zero demand.
- Future resets may differ after a manual reset or plan change → use currently reported timing, recalculate on refresh and label future reset repetition as assumed.
- Account stickiness/access restrictions cannot be reconstructed exactly from pool totals → disclose modeled allocation and avoid operational guarantees.

## Migration Plan

Add a backward-compatible projection field and zero-configuration UI. No database or routing migration. Rollback removes the component and projection field without changing account or request state.

## Validation outcome

The read-only historical audit found no cutoff where the complete current
eligible pool was ready. The ready-only held-out validation produced one
candidate interval but no scorable interval, so it cannot report an error
statistic. The implementation therefore keeps whole-pool output conservative:
learning or limited evidence does not become a reassuring interruption
timeline. Aggregate details are in `notes.md` and
`historical-validation.json`.
