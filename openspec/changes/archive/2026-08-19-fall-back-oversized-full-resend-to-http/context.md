# Context

## Purpose and scope

Codex clients may resend the complete input history on every
`response.create` instead of using `previous_response_id`. Long tool-driven
turns can make that complete body too large for the upstream Responses
WebSocket even though the body is valid and can be sent over upstream HTTP.

This change covers the narrow transport fallback for oversized, unanchored
complete resends and the continuity metadata needed to keep that fallback
correct across concurrent turns and service restarts.

## Decisions

- The decision is made after the proxy has prepared the final downstream
  request body and before any upstream WebSocket dispatch.
- A complete resend is portable when it has no `previous_response_id`, no
  nonblank `conversation`, and a non-empty input list. Its input is preserved
  byte-for-byte at the HTTP boundary, including inline images.
- A client continuation of a response created over upstream HTTP remains on
  upstream HTTP. A response created over upstream HTTP is never injected as a
  WebSocket anchor into a later unanchored resend.
- The fallback remains a WebSocket request from the client's perspective. It
  uses the already-resolved session, file owner, previous-response owner, and
  API-key reservation rather than performing a second, potentially divergent
  lookup.

## Constraints and failure modes

- Conversation-backed requests and client-anchored requests whose input is not
  exclusively current tool outputs remain fail-closed when they exceed the
  WebSocket budget.
- A second unanchored full resend cannot overtake an active HTTP fallback on
  the same downstream socket. Anchored requests may still multiplex through
  the shared upstream WebSocket when their ownership permits it.
- Reservation heartbeat ownership moves to the HTTP streamer only after its
  routing preflight reaches the settlement guard. Cancellation before that
  point releases the reservation; cancellation after it is left to stream
  settlement.
- Legacy owner rows with a missing or unknown upstream transport are not
  inferred to be HTTP. No database migration is required because the new
  value is nullable metadata on existing request-log rows.

## Non-goals

This change does not add stale-anchor invalidation, compare-and-clear logic,
pre-send proxy-anchor revalidation, or a new stale-response error classifier.
Those behaviors are separate work and are intentionally not part of this
port.

## Example

A WebSocket request contains the user's current turn, completed image-viewing
tool calls, and inline screenshots. It has no `previous_response_id`, and the
final projected WebSocket body is 17 MiB. codex-lb sends the unchanged input
over upstream HTTP and relays the normal response events over the same
downstream WebSocket.
