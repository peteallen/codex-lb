## Why

The Codex client can send a complete conversation on each downstream
`response.create` instead of continuing with `previous_response_id`. During a
long tool-driven turn, inline screenshots from several earlier tool results can
push that complete resend above the upstream websocket frame budget even though
the request remains valid.

The existing size slimmer preserves everything after the most recent user
message. That is intentionally conservative, but it means a long single turn
with many image-bearing tool results cannot be slimmed. The existing upstream
HTTP relay also rejects this shape because it only admits anchored requests
whose input consists entirely of current tool outputs. The result is a local
`payload_too_large` dead end even though the unanchored request is a complete
body that can be sent over upstream HTTP without a websocket frame.

## What Changes

- Relay an oversized downstream websocket `response.create` over upstream HTTP
  when the final wire body has neither a `previous_response_id` nor a nonblank
  `conversation`.
- Preserve the complete input, including inline images, rather than applying an
  additional lossy rewrite to the current turn.
- Reuse the existing per-turn HTTP relay so downstream websocket events,
  routing, cancellation, admission, reservation settlement, and request-log
  transport fields keep their current behavior.
- Preserve synthesized-turn-state classification and resolved file ownership
  across the HTTP hop, and make reservation ownership explicit across stream
  preflight.
- Reject a later unanchored full resend while the relay is active while keeping
  anchored multiplexing and latest-turn cancellation semantics.
- Record the upstream transport that created each WebSocket continuity response.
  A client continuation of an HTTP-created response stays on upstream HTTP,
  while an unanchored resend never has that HTTP response injected as a
  WebSocket anchor.
- Compare-and-clear a proxy-injected continuity anchor when upstream rejects
  that exact anchor, so the client's unanchored retry cannot receive it again.
- Revalidate proxy-injected continuity immediately before upstream send, and
  fall back to the retained fresh body if a late await invalidated the anchor.
- Publish HTTP response provenance to the scoped owner cache immediately and
  wait for its tracked request-log persistence attempt before terminal delivery
  so healthy restarts retain the correct upstream transport.
- Keep the existing fail-closed behavior for proxy-injected anchors and for
  client-anchored oversized requests that are not all-current-tool-output
  deltas.

## Impact

- Affected capability: `responses-api-compat`.
- Long image-heavy Codex turns that use complete resends can continue without
  manually compacting the task.
- No ambiguously dispatched websocket request becomes replayable because the
  transport decision still happens before upstream dispatch.
- HTTP-created response IDs no longer cross into the incompatible upstream
  WebSocket continuity namespace.
- Successful HTTP-fallback provenance is available across sessions immediately
  and across process restarts after its terminal persistence commit.
