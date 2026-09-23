## ADDED Requirements

### Requirement: HTTP bridge isolation does not imply conversation continuity
For an unanchored OpenAI-style HTTP Responses request, a session-header bridge isolation key alone MUST NOT cause the proxy to inject the durable last response ID when reconnecting. Durable anchor injection MUST require Codex-session continuity affinity or a verified stored input prefix, in addition to existing anchor eligibility guards. Explicit client previous-response IDs and turn-state continuity MUST retain their ownership constraints.

#### Scenario: Independent request reconnects after an upstream response expires
- **GIVEN** a plain `/v1/responses` request completed on a session-header bridge
- **AND** the upstream connection closed and its last response ID is no longer available
- **WHEN** another short request uses that session header without a previous-response ID, turn state, or verified stored input prefix
- **THEN** the proxy sends the client's request without injecting a previous-response ID
- **AND** the request can complete without stale-anchor retries

#### Scenario: Explicit continuity survives reconnect
- **WHEN** the client supplies a previous-response ID or Codex turn state on reconnect
- **THEN** the bridge preserves the existing anchored continuity and ownership behavior

#### Scenario: Verified stored-prefix reuse survives reconnect
- **WHEN** the client's resend matches the stored input prefix
- **THEN** existing safe anchor reuse and full-resend recovery rules remain applicable
