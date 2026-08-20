## MODIFIED Requirements

### Requirement: Tool-only throughput

Reports daily TPS medians and Dashboard recent-request TPS MUST include a
positive-output request when latency and an upstream generation anchor are
available, even if no client-visible token was emitted. The generation anchor
MUST be selected in this order: first upstream event, response created, then
client-visible first token. The numerator MUST use persisted output tokens, and
the denominator MUST be completion latency minus the selected anchor.

#### Scenario: Tool-only request contributes throughput

- **GIVEN** a request has output tokens, completion latency, and a first
  upstream-event latency but no first-token latency
- **WHEN** daily speed medians or recent requests are rendered
- **THEN** the request contributes a positive TPS sample
- **AND** its TTFT display is either absent or marked approximate as first-output
  time rather than presented as client-visible TTFT
