## Purpose and scope

This change makes short Reports windows useful as timelines. It applies only
to the five line/area charts on `/reports`; the owning normative requirements
are in the delta `specs/frontend-architecture/spec.md`.

The existing date controls select inclusive calendar dates in the requested
browser timezone. Therefore a range is hourly when it contains one or two
selected dates, and daily when it contains three or more selected dates.

## Decision rationale

The API retains `daily` for the Daily Breakdown and adds an explicit
`chartGranularity` plus an `hourly` series. Overloading `daily` with timestamped
rows was rejected because it would break the table/CSV contract and make the
field name misleading. Computing hourly points in the browser was rejected
because the browser does not receive raw request logs and cannot calculate
correct hourly medians.

Hourly buckets are generated from the selected local-midnight boundaries as
consecutive UTC intervals, then labeled in the requested timezone. This keeps
the range exact across daylight-saving transitions: a spring-forward day has
23 points and a fall-back day has 25 points, with the repeated local hour
distinguished by its UTC offset.

## Constraints and non-goals

- Summary totals, per-day averages, comparisons, distributions, filtering,
  and the 730-day maximum remain unchanged.
- The Daily Breakdown and its CSV remain one row per selected local date.
- Hourly aggregation preserves the same traffic exclusions and all account,
  API-key, model, and user-agent filters as daily aggregation.
- This does not move Reports medians onto the permanent hourly rollup tables;
  the existing raw-only Reports median contract remains in force.
- Stable chart visibility IDs such as `costByDay` remain unchanged so saved
  visibility preferences continue to work.

## Failure modes and edge cases

- Missing or invalid timezone input continues to fall back to UTC.
- Empty hours are returned as zero-valued points so lines do not jump across
  inactive periods.
- Invalid or inverted ranges continue to be rejected before repository work.
- Three selected dates are deliberately the first daily case, avoiding an
  ambiguous boundary at the cutoff.

## Example

For `start_date=2026-06-01`, `end_date=2026-06-02`, and
`timezone=America/Denver`, the API returns `chartGranularity: "hour"`, keeps
two `daily` rows for the table, and returns 48 hourly rows for the charts. For
`end_date=2026-06-03`, it returns `chartGranularity: "day"` and an empty
`hourly` array; the charts use the three daily rows.
