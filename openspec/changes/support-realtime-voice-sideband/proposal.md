# Change: support-realtime-voice-sideband

## Why

The current Codex live-voice flow creates its WebRTC call through
`POST /backend-api/codex/realtime/calls`, then opens a second WebSocket at the
returned call location for the call's sideband control channel. codex-lb
already proxies the create request and preserves its `Location` response
header, but it has no route for the returned `rtc_*` (or UUID) WebSocket path.
The call therefore succeeds upstream and then fails locally at the sideband
handshake. Direct ChatGPT connections work because they reach the matching
upstream route.

The sideband cannot be sent through the existing Responses WebSocket proxy.
It is a transparent, call-specific byte/message relay with different headers,
account-continuity rules, and lifetime semantics.

## What Changes

- Persist a short-lived shared-database binding from a validated successful
  realtime call ID to the exact upstream account that returned it and the
  local API-key identity, if any.
- Add identifier-constrained backend Codex WebSocket routes for `rtc_*` and
  canonical UUID call IDs; do not add a general backend wildcard.
- Authenticate before binding lookup, re-check the API key's current account
  assignment, and atomically claim the binding so only one replica can open
  the sideband.
- Refresh and connect only the bound account, using that account's configured
  upstream proxy route or direct-egress policy without account failover.
- Build a dedicated Voice handshake: replace downstream auth/account identity,
  preserve allowlisted Voice/session/thread/originator/attestation headers and
  query parameters, and strip cookies, forwarding, hop-by-hop, and downstream
  handshake headers. Never inject the Responses WebSocket beta.
- Translate path-based Frameless Bidi joins to OpenAI's canonical
  `wss://api.openai.com/v1/live/<call-id>` endpoint rather than replaying the
  call-create path against the ChatGPT backend.
- Relay text, binary, and close code/reason in both directions with symmetric
  cancellation, lease renewal, and durable cleanup.
- Keep SDP, frames, transcripts, and audio-related data out of persistence and
  leave both existing Responses WebSocket routes and their state machine
  unchanged.
- Record realtime call creation with request kind
  `codex_control_realtime_calls` instead of the default `normal` kind.

## Impact

This adds one Alembic-managed metadata table and one narrowly matched
WebSocket compatibility surface. A call created on one replica may join on
another, while wrong-key, out-of-scope, expired, malformed, unknown, or
concurrently claimed joins fail before any upstream WebSocket request.
