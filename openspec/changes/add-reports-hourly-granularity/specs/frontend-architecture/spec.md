## ADDED Requirements

### Requirement: Reports charts use hourly granularity for ranges shorter than three days

`GET /api/reports` MUST expose `chartGranularity` as `hour` when the selected
inclusive local-calendar range contains one or two dates, and as `day` when it
contains three or more dates. For hourly responses, the endpoint MUST return
an `hourly` array containing real per-hour aggregates for the same filtered
traffic as the report summary and daily rows. For daily responses, `hourly`
MUST be empty. The existing `daily` array MUST remain present and unchanged for
the Daily Breakdown, CSV export, and daily-mode charts.

The `/reports` page MUST render all five line/area charts from `hourly` when
`chartGranularity` is `hour`, and from `daily` when it is `day`. Cost and token
chart titles and chart-filter labels MUST describe the active hour/day
granularity. Stable chart visibility IDs and saved visibility preferences MUST
remain unchanged.

#### Scenario: One-day report renders hourly charts and a daily table

- **WHEN** an operator requests one selected local calendar date
- **THEN** `GET /api/reports` returns `chartGranularity: "hour"`
- **AND** `hourly` contains real per-hour report aggregates
- **AND** `daily` still contains the selected date's daily aggregate
- **AND** all five report charts render the hourly series
- **AND** the Daily Breakdown and CSV remain daily

#### Scenario: Two-day report remains hourly

- **WHEN** an operator selects two inclusive local calendar dates
- **THEN** `GET /api/reports` returns `chartGranularity: "hour"`
- **AND** the charts render hourly buckets spanning both selected dates

#### Scenario: Three-day report uses daily charts

- **WHEN** an operator selects three inclusive local calendar dates
- **THEN** `GET /api/reports` returns `chartGranularity: "day"`
- **AND** `hourly` is empty
- **AND** all five report charts render the existing daily series

### Requirement: Reports hourly chart buckets preserve local-time boundaries and gaps

Hourly report rows MUST use timezone-aware ISO 8601 bucket timestamps and
half-open bucket ranges that exactly partition the selected local-calendar
window. The rows MUST preserve existing report filters and traffic exclusions,
and MUST calculate hourly medians from requests in each hour rather than
deriving them from daily medians. Every hour in the selected window MUST be
represented; an hour with no matching traffic MUST contain zero-valued
metrics.

#### Scenario: Inactive hour renders as zero

- **WHEN** a one-day report has no matching traffic during one hour
- **THEN** `hourly` contains that hour with zero cost, tokens, requests, errors,
  active accounts, and latency medians
- **AND** each chart renders the zero-valued point

#### Scenario: Spring-forward day has no nonexistent hour

- **WHEN** a selected local date advances through a daylight-saving transition
  and contains 23 elapsed hours
- **THEN** `hourly` contains exactly 23 ordered rows
- **AND** the nonexistent local wall-clock hour is not synthesized

#### Scenario: Fall-back day distinguishes the repeated hour

- **WHEN** a selected local date repeats a wall-clock hour during a
  daylight-saving transition
- **THEN** `hourly` contains exactly 25 ordered rows
- **AND** the two repeated-hour timestamps have distinct UTC offsets

#### Scenario: Hourly filters match daily filters

- **WHEN** account, API-key, model, or user-agent report filters are selected
- **THEN** each hourly aggregate includes only traffic matching every selected
  filter and the existing normal-traffic exclusions
