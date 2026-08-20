## Context

Codex can resend a complete conversation without `previous_response_id`. A
long image-heavy turn may remain above the upstream WebSocket frame budget even
after historical slimming, although the complete body is valid over upstream
HTTP. Once a downstream WebSocket turn completes over HTTP, later exact
continuations also need transport provenance so the response id is not sent to
an incompatible upstream WebSocket continuity namespace.

## Goals / Non-Goals

**Goals:**

- Relay an oversized, unanchored, conversation-free complete resend over
  upstream HTTP without rewriting its input.
- Preserve session affinity, file-owner routing, cancellation ordering,
  admission, and API-key settlement across the handoff.
- Keep exact continuations of HTTP-created responses on HTTP immediately and
  after a healthy process restart.

**Non-Goals:**

- Relay conversation-backed stored-object requests or anchored non-tool
  requests that remain oversized.
- Infer HTTP provenance from missing, legacy, or unrecognized request-log data.
- Add stale-anchor recovery or broaden replay eligibility after dispatch.

## Decisions

### Classify the original client frame

The fallback requires no client `previous_response_id`, no nonblank
`conversation`, and a non-empty input list whose final projected wire body is
over budget. Classification uses the original downstream frame so a later
proxy-injected anchor cannot turn the resend into an ineligible continuation.

### Keep the relay outside shared WebSocket correlation state

The complete resend uses the same owned HTTP relay as the anchored fallback but
does not enter the upstream WebSocket pending queue. A second unanchored resend
cannot overtake it, while an independently owned anchored WebSocket turn may
proceed. Connection-level cancellation targets the most recently started turn.

### Carry routing proof and settlement ownership once

The prepared file owner, synthesized turn state, request session id, API-key
reservation, and response-create admission are transferred explicitly. An
event marks when the HTTP stream takes settlement ownership so cancellation
before and after that boundary cannot leak or double-release the reservation.

### Persist transport provenance before terminal delivery

An HTTP-upstream completion is published to the API-key-scoped owner cache
before request-log persistence begins. The tracked persistence attempt is
shielded and awaited before the held terminal event is sent, so a successful
commit makes exact HTTP continuations restart-safe. A failed observational log
write does not replace the already completed terminal response.

## Risks / Trade-offs

- Waiting for correctness-critical provenance adds request-log commit latency
  before the terminal frame. Only successful WebSocket-downstream,
  HTTP-upstream turns pay that cost.
- A stale or unrelated response id could be forced onto HTTP. The cache and
  repository lookup require an exact id within API-key and session scope, and
  only normalized `http` provenance selects the path.
- A full resend could race another turn. The relay participates in the existing
  connection lifecycle with explicit newest-turn cancellation and conflict
  tests.

## Migration Plan

No schema migration or configuration change is required because request logs
already persist `upstream_transport`. Existing rows with `NULL` provenance stay
on the ordinary WebSocket path. Rollback restores the prior local rejection.

## Open Questions

None.
