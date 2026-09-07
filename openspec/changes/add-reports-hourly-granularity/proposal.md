## Why

Reports currently collapse every selected calendar day into one chart point.
That makes a one-day or two-day report look nearly flat and hides the hours in
which traffic, cost, and latency actually changed.

## What Changes

- Use hourly chart buckets when the selected inclusive local-calendar range is
  fewer than three days (one or two selected dates).
- Keep daily chart buckets for ranges of three days or more.
- Return real timezone-aware hourly aggregates from `GET /api/reports`,
  including empty hours, instead of relabeling daily totals.
- Keep the existing `daily` response, Daily Breakdown table, CSV export,
  summary averages, comparisons, distributions, and filters unchanged.
- Render hourly chart titles and bucket labels for short ranges while keeping
  the existing chart visibility preference IDs stable.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontend-architecture`: Define conditional Reports chart granularity and
  its API/UI contract.

## Impact

- Backend: `app/modules/reports/{repository,schemas,service}.py`
- Frontend: Reports response schema, chart-series mapping, chart cards,
  filters, and locale resources
- Tests: focused repository, service/API, schema, and chart rendering coverage
- No database migration, setting, query parameter, summary calculation, or
  Daily Breakdown behavior change
