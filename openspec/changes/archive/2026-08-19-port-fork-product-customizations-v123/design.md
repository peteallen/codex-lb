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
midnight remains stable across daylight-saving transitions. Daily and weekly
trend points are aligned to explicit local-calendar boundaries rather than UTC
epoch multiples, so a selected day is represented once even when its elapsed
duration is 23 or 25 hours. Date inputs retain an incomplete or temporarily
inverted local draft and update the URL only after both dates form a valid
range.

### Weekly forecast semantics

The existing working-day set already controls schedule gap calculations. The
forecast simulation now applies that same set to burnable intervals and maps a
burnable depletion duration back to wall-clock hours. An empty set retains the
existing all-days behavior.

### Throughput semantics

TTFT remains both the client-visible-token metric and the throughput anchor for
normal responses. When a tool-only turn has no TTFT, throughput falls back to
`response_created`; `first_upstream_event` remains transport diagnostics and is
not an output anchor because it may precede response creation. TPS counts
persisted output tokens, including reasoning time covered by the generation
interval. A tool-only row may therefore contribute TPS without inventing TTFT;
its recent-request TTFT cell is shown as an approximate first-output time.

### Localization

Custom-range labels and accessibility text, plus the approximate first-output
tooltip, use the existing English, Korean, and Simplified Chinese catalogs.

### Branding

Brand constants are centralized so the header, auth gate, status-bar link, and
document title cannot drift. The link label is intentionally fork-specific and
is not added to translation catalogs because it identifies this deployment.
