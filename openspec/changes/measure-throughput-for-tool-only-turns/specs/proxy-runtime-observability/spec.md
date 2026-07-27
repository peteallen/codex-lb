## ADDED Requirements

### Requirement: Generation throughput is anchored at first upstream output

Generation throughput MUST be computed over the window from the first upstream
output of a response to its completion, anchored by the first available of
`latency_first_upstream_event_ms`, `latency_response_created_ms`, and
`latency_first_token_ms`. It MUST NOT depend solely on time-to-first-token, which
exists only for turns that emit a client-visible token and therefore excludes
agentic tool-only turns.

Because reasoning time lies inside that window, the numerator MUST be total
output tokens rather than visible-only output tokens, so numerator and
denominator describe the same interval. Throughput MUST be omitted when no anchor
exists, when total output tokens are not positive, or when the window is not
positive.

This applies identically to the per-request dashboard value and the daily report
median, so the two cannot disagree.

#### Scenario: A tool-only turn reports throughput

- **GIVEN** a successful request that emitted no client-visible token
- **AND** its first upstream event latency was recorded
- **WHEN** throughput is computed
- **THEN** it is measured from the first upstream event to completion
- **AND** total output tokens including reasoning tokens form the numerator

#### Scenario: Throughput is omitted when unmeasurable

- **WHEN** a request has no anchor, non-positive total output tokens, or a
  non-positive generation window
- **THEN** no throughput value is reported for it

#### Scenario: Per-request and aggregate agree

- **GIVEN** a set of requests with recorded anchors and output tokens
- **WHEN** the per-request dashboard value and the daily report median are
  computed
- **THEN** both use the same anchor precedence and the same numerator

### Requirement: Time-to-first-token keeps its meaning and degrades visibly

`latency_first_token_ms` MUST continue to mean time to the first client-visible
token and MUST NOT be redefined to include non-visible output. Request-log API
entries MUST expose `latency_first_upstream_event_ms` and
`latency_response_created_ms` alongside it.

Where a request has no time-to-first-token, the dashboard MAY present time to
first output in its place, but MUST mark that value as approximate so the two
measurements are never presented as equivalent.

#### Scenario: A visible-token turn shows exact TTFT

- **WHEN** a request recorded a time-to-first-token
- **THEN** the dashboard shows that value unmarked

#### Scenario: A tool-only turn shows a marked approximation

- **WHEN** a request recorded no time-to-first-token but did record a first
  upstream output
- **THEN** the dashboard shows the first-output time marked as approximate
- **AND** it does not report that value as time-to-first-token
