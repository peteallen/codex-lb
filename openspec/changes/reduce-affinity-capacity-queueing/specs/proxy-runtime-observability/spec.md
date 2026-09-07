## ADDED Requirements

### Requirement: Missing-created failures expose bounded protocol progress

When a bridge request fails with response activity but no assigned response.created acknowledgment, diagnostics MUST identify response-event count, last event type, dispatch status, and acknowledgment/visibility status without logging request bodies, tool arguments, raw credentials, or unbounded event data.

#### Scenario: Reattached stream fails without an acknowledgment
- **WHEN** an injected-anchor request receives response events but fails before response.created is assigned
- **THEN** its failure diagnostic includes bounded protocol-progress fields sufficient to distinguish an idle request from output-bearing work
- **AND** the diagnostic contains no request or response body
