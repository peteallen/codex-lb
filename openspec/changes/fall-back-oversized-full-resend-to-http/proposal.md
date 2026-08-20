## Why

The Codex client can send a complete conversation on each downstream
`response.create` instead of continuing with `previous_response_id`. During a
long tool-driven turn, inline screenshots from several earlier tool results
can push that complete resend above the upstream WebSocket frame budget even
though the request remains valid.

Historical slimming intentionally preserves the latest user turn, but it
cannot safely remove the current turn's complete input. The existing HTTP
relay also only admits anchored current-tool-output deltas. The result is a
local `payload_too_large` dead end even though the complete body can be sent
over upstream HTTP without a WebSocket frame.

## What Changes

- Relay an oversized downstream WebSocket `response.create` over upstream HTTP
  when the final wire body has neither a `previous_response_id` nor a nonblank
  `conversation`, and has a non-empty input list.
- Preserve the complete input, including inline images, rather than applying
  another lossy rewrite to the current turn.
- Reuse the existing per-turn HTTP relay so downstream WebSocket events,
  routing, cancellation, admission, reservation settlement, and request-log
  transport fields keep their intended behavior.
- Preserve synthesized-turn-state classification and resolved file ownership
  across the HTTP hop, and make reservation ownership explicit across stream
  preflight.
- Reject a later unanchored full resend while the relay is active while
  keeping anchored multiplexing and latest-turn cancellation semantics.
- Record the upstream transport that created each WebSocket continuity
  response. An exact client continuation of an HTTP-created response stays on
  upstream HTTP, while an unanchored resend never receives that HTTP response
  as a WebSocket anchor.
- Publish HTTP response provenance to the scoped owner cache immediately and
  wait for its tracked request-log persistence attempt before terminal
  delivery so healthy restarts retain the correct upstream transport.
- Keep fail-closed behavior for proxy-injected anchors and for client-anchored
  oversized requests that are not all-current-tool-output deltas.

This change intentionally does not include stale-anchor invalidation,
compare-and-clear helpers, pre-send anchor revalidation, or a stale-response
classifier.

## Impact

- Affected capability: `responses-api-compat`.
- Long image-heavy Codex turns that use complete resends can continue without
  manually compacting the task.
- No ambiguously dispatched WebSocket request becomes replayable because the
  transport decision still happens before upstream dispatch.
- HTTP-created response IDs do not cross into the incompatible upstream
  WebSocket continuity namespace.
- Successful HTTP-fallback provenance is available across sessions immediately
  and across process restarts after its terminal persistence commit.
