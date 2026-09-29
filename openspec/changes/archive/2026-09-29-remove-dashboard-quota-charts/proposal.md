## Why

The operator requested removal of the dashboard's weekly and 5-hour pooled
quota charts after the mixed-capacity display became confusing and the short
window ceased to be useful for the current pool.

## What Changes

- Remove both pooled quota panels without adding replacement graphs.
- Preserve account-level quota information and the separately eligible weekly
  credit pace card.
- Remove dedicated unused chart components and their rendering requirements.
- Verify the dashboard still renders its summaries, accounts and request logs.

## Capabilities

### Modified Capabilities
- `frontend-architecture`: dashboard content excludes pooled quota charts.
- `account-quota-presentation`: remove obsolete pooled donut contribution rules.

## Impact

Dashboard frontend only. No API, pricing, database, routing or history changes.
