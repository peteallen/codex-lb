## Context

An upstream Responses WebSocket rejects a `response.create` frame above its
frame budget. Historical slimming cannot help when the current tool output is
itself the oversized content, while the upstream HTTP/SSE path accepts the same
request body. The WebSocket path has already resolved continuation ownership,
session scope, admission, and API-key reservation state before this decision.

## Goals / Non-Goals

**Goals:**

- Continue an unambiguously anchored, current-tool-output-only turn over
  upstream HTTP while preserving the downstream WebSocket contract.
- Preserve the already-resolved owner and session scope across the transport
  boundary and settle every gate, task, and reservation exactly once.
- Keep every other oversized request fail-closed on the existing local
  `payload_too_large` path.

**Non-Goals:**

- Replay a request after ambiguous upstream dispatch.
- Treat a proxy-injected anchor as a client-authored continuation.
- Change the WebSocket frame budget, historical slimming policy, or public
  event shapes.

## Decisions

### Decide before dispatch from the final projected frame

Eligibility is evaluated only after request preparation and per-account
installation metadata projection. The fallback requires a client-supplied
anchor and a non-empty input containing only current tool-output item types.
The request is never registered in the shared upstream WebSocket pending set.

### Transfer one turn to the existing HTTP streamer

The per-connection relay owns the turn as a tracked task and reuses the HTTP
stream retry, logging, and settlement machinery. It receives the owner account,
owner-lookup session id, synthesized turn state, and reservation already
resolved on the WebSocket path instead of repeating those lookups.

### Preserve downstream lifecycle semantics

The relay converts SSE blocks back to ordinary WebSocket response events,
emits keepalives before `response.created`, delays the terminal frame until the
HTTP stream drains, and releases admission and reservation ownership on normal
completion, cancellation, disconnect, and teardown.

## Risks / Trade-offs

- A transport handoff could double-settle or leak a reservation. The handoff
  clears the WebSocket state's reservation owner and tests cancellation on both
  sides of the HTTP settlement guard.
- Re-resolving continuation ownership could cross accounts. The WebSocket
  result is authoritative and is passed explicitly to the HTTP streamer.
- An owner-specific upstream error could be hidden by later selection failure.
  A hard owner-bound continuation without a safe fresh replay body surfaces the
  owner's original pre-visible error unchanged.

## Migration Plan

No database migration, setting, or operator action is required. Rollback is a
code rollback; ineligible requests retain the pre-change rejection behavior.

## Open Questions

None.
