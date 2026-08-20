## ADDED Requirements

### Requirement: HTTP fallback preserves capability routing and lineage

When an oversized WebSocket `response.create` request requires Trusted Cyber
authorization, the HTTP fallback MUST pass that requirement to upstream
account selection and MUST persist the capability lineage aliases for the
generated response ID before forwarding `response.created` downstream.

#### Scenario: capability-aware fallback

- **WHEN** an oversized fallback requires Trusted Cyber authorization
- **THEN** ordinary accounts are not eligible for its upstream selection
- **AND** the generated response ID is persisted in the capability lineage
  before `response.created` is exposed

### Requirement: HTTP fallback participates in drain and cancellation

Graceful WebSocket drain MUST treat an active HTTP fallback relay as active
work. If fallback setup is cancelled before a relay task takes ownership of
the API-key reservation, the service MUST release that reservation and the
response-create admission exactly once.

#### Scenario: active fallback drains

- **WHEN** graceful shutdown begins while an HTTP fallback is the only active
  turn on a downstream WebSocket
- **THEN** the downstream socket remains open until the fallback reaches a
  terminal event or the drain deadline expires

#### Scenario: setup cancellation cleans up

- **WHEN** fallback setup is cancelled while waiting for response-create
  admission, before its relay task starts
- **THEN** the API-key reservation and response-create admission are released
  exactly once
