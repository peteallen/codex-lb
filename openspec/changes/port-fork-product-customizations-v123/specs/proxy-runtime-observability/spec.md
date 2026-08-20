## MODIFIED Requirements

### Requirement: Dashboard request logs show generation speed

The dashboard request-log table MUST show time to first token and output-token
generation speed when the required latency and output-token fields are
available. When TTFT is present, generation speed MUST use output tokens divided
by elapsed generation time after TTFT, even if earlier first-upstream-event or
response-created timings are also present. A positive-output row without TTFT
MUST instead use response-created latency when available and MUST mark that
timing as an approximate first-output value. First-upstream-event latency MUST
NOT be used as a generation anchor. Generation speed MUST NOT use total input
plus output tokens or total request latency including the selected output
anchor.

#### Scenario: TPS excludes TTFT and input tokens

- **GIVEN** a successful request log has 1,000 input tokens, 200 output tokens,
  1,000 ms total latency, 200 ms TTFT, 100 ms response-created latency, and 50 ms
  first-upstream-event latency
- **WHEN** the dashboard renders request logs
- **THEN** it shows TTFT as 200ms
- **AND** it shows TPS as 250.0

#### Scenario: Tool-only request uses response-created timing

- **GIVEN** a positive-output request has 1,000 ms total latency, no TTFT,
  200 ms response-created latency, and 100 ms first-upstream-event latency
- **WHEN** the dashboard renders request logs
- **THEN** it calculates TPS from the 800 ms interval after response creation
- **AND** it shows 200 ms as a localized approximate first-output value rather
  than client-visible TTFT

#### Scenario: Missing speed inputs stay blank

- **GIVEN** a request log is missing both TTFT and response-created latency,
  total latency, or output tokens
- **WHEN** the dashboard renders request logs
- **THEN** it does not show a misleading calculated TPS value
- **AND** first-upstream-event latency alone does not produce an approximate
  first-output value

### Requirement: Reports show daily median generation speed trends

The Reports dashboard MUST expose daily median TTFT, daily median TPS, and daily
median queue-wait trends when request-log latency fields are available. Empty
days and rows with no valid timing/speed inputs MUST render as zero in those
trend charts. Daily TPS MUST median per-request output-token TPS after TTFT when
TTFT is present, otherwise after response creation for a positive-output
tool-only row. Daily TPS MUST NOT use input tokens, include time before the
selected anchor, or substitute first-upstream-event latency. Daily queue wait
MUST median per-request `latency_queue_ms` over rows where it is non-null.

#### Scenario: Daily speed charts use median valid request values

- **GIVEN** one report day has request logs with TTFT and output-token TPS values
- **WHEN** the dashboard renders Reports
- **THEN** it shows a Time to First Token chart using median TTFT for the day
- **AND** it shows a Tokens per Second chart using median per-request TPS for the day

#### Scenario: Tool-only row contributes response-created TPS

- **GIVEN** a report row has positive output tokens, completion latency, and
  response-created latency but no TTFT
- **WHEN** Reports calculates the daily median TPS
- **THEN** the row contributes output-token TPS measured after response creation
- **AND** earlier first-upstream-event latency does not change that sample

#### Scenario: Missing daily speed data is zero-filled

- **GIVEN** a selected report range includes a day with no request logs or no valid timing data
- **WHEN** the dashboard renders Reports
- **THEN** the TTFT and TPS charts include that day with value zero

#### Scenario: Daily queue-wait trend surfaces load-balancer wait

- **GIVEN** a report day has request logs with non-null `latency_queue_ms`
- **WHEN** the dashboard renders Reports
- **THEN** it shows a queue-wait trend using the day's median `latency_queue_ms`
- **AND** days without queue samples render as zero
