## Context

`GET /api/reports` currently queries local-calendar daily aggregates and the
frontend sends that same `daily` array to all five charts and to the Daily
Breakdown. Short selections therefore contain only one or two chart points.

## Goals / Non-Goals

**Goals:**

- Provide true hourly cost, token, and latency-median points for one-day and
  two-day report ranges.
- Preserve timezone boundaries, filters, traffic exclusions, and DST behavior.
- Keep the table and CSV daily and preserve saved chart visibility settings.

**Non-Goals:**

- Changing summary averages, comparison windows, distributions, report range
  limits, or query parameters.
- Adding an operator-configurable granularity control.
- Changing retention or report-rollup architecture.

## Decisions

### Add an explicit short-range chart series

The response adds `chartGranularity` (`hour` or `day`) and `hourly`. The
service fills `hourly` only when the inclusive `window_days` is less than
three. The existing `daily` array remains authoritative for the Daily
Breakdown and for charts in daily mode.

### Share the SQL bucket aggregation path

Daily and hourly repository reads use the same aggregate and median SQL over
labeled half-open ranges. This preserves metric and filter semantics without
duplicating the calculations. The hourly wrapper fills absent labels with
zero-valued rows because its maximum response is bounded to two local days.

### Treat UTC instants as the hourly sequence

The repository walks hourly UTC instants from the selected local midnight to
the following local midnight and converts each label back to the requested
timezone. This produces the correct 23/24/25-point DST day and offset-qualified
labels for repeated hours.

### Keep chart components backward compatible

Chart props retain the existing daily `data` input and gain the response
granularity and hourly series. A shared mapper selects the correct series and
formats hourly labels. Existing visibility IDs remain stable; only displayed
titles/options switch from “by Day” to “by Hour” where applicable.

## Risks / Trade-offs

- Short report requests perform an additional bounded aggregate/median read.
  The maximum is under 50 hourly ranges, so the added work is limited.
- Both the main report query and the relaxed filter-catalog query request the
  full payload. This follows the existing complete-payload contract and avoids
  a new chart-specific request parameter.
- Offset-qualified timestamps are a larger payload than dates, but only for
  one-day and two-day windows.

## Verification approach

- Repository tests cover aggregation, filtering, zero-filled gaps, and DST
  point counts/offsets.
- Service/API tests cover the two-day/three-day cutoff and prove `daily`
  remains present.
- Frontend schema and chart tests cover hourly parsing, selection, titles, and
  labels while retaining daily behavior.
