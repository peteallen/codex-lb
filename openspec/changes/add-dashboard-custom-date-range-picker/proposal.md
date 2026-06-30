# Add dashboard custom date range picker

## Why

Operators use the main dashboard as the first place to inspect activity. The dashboard overview already supports fast `1d`, `7d`, and `30d` windows, but it cannot inspect an arbitrary calendar range without switching to the Reports page. The dashboard date-filtered overview should offer the same custom range affordance while keeping the quick presets easy to reach.

## What Changes

- Add a Custom range picker to the main dashboard overview range control alongside `1d`, `7d`, and `30d`.
- Extend `GET /api/dashboard/overview` to accept explicit `start_date`, `end_date`, and `timezone` query parameters for custom calendar ranges.
- Keep preset dashboard URLs and behavior unchanged.
- Keep future dates disabled for custom dashboard overview range selection.

## Impact

- Affects the `/dashboard` overview summary cards and trend charts.
- Does not change account quota windows, dashboard projections, or recent request-log filters.
