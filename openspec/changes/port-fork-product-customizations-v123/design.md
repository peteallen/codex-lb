## Context

v1.23 serves historical Dashboard activity from hourly usage rollups plus the
raw edge windows. The custom range must therefore pass both start and end
bounds to every read that contributes to the overview; extending only the raw
query would make rollup-backed trend or conversation buckets leak outside the
selected dates.

## Decisions

### Dashboard range semantics

Preset ranges remain rolling windows. A custom range is inclusive by local
calendar date and is converted to a half-open UTC interval
`[start_midnight, end_date + 1 day)`. The previous comparison window has the
same duration immediately before the selected interval. Invalid or inverted
ranges return a dashboard validation error; the maximum range is 730 days.

The response keeps the existing timeframe metadata shape and reports
`key="custom"` with a bucket size selected for the range. The frontend stores
custom dates in the dashboard URL and sends the browser time zone so local
midnight remains stable across daylight-saving transitions.

### Weekly forecast semantics

The existing working-day set already controls schedule gap calculations. The
forecast simulation now applies that same set to burnable intervals and maps a
burnable depletion duration back to wall-clock hours. An empty set retains the
existing all-days behavior.

### Throughput semantics

TTFT remains the client-visible-token metric. Throughput uses the earliest
available upstream anchor (`first_upstream_event`, then `response_created`, then
TTFT) and counts persisted output tokens, including reasoning time covered by
the generation interval. A tool-only row may therefore contribute TPS without
inventing TTFT; its recent-request TTFT cell is shown as an approximate first
output time.

### Branding

Brand constants are centralized so the header, auth gate, status-bar link, and
document title cannot drift. The link label is intentionally fork-specific and
is not added to translation catalogs because it identifies this deployment.
