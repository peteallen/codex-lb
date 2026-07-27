# Context: support-realtime-voice-sideband

## Purpose and scope

The live-voice client uses WebRTC for media and a separate backend Codex
WebSocket for sideband control. codex-lb already reaches upstream for the
multipart call-create request, but the returned call path currently falls
through locally because the only backend WebSocket route is `/responses`.
This change supplies that missing control-channel hop. It does not proxy the
WebRTC media plane and does not reinterpret the sideband protocol.

Normative behavior lives in the delta specs under
`specs/realtime-voice-sideband/spec.md` and
`specs/database-migrations/spec.md`.

## Why a durable binding is necessary

The create request is movable until an account returns a successful call. The
returned call exists inside that upstream ChatGPT account, so the sideband is
not movable afterward. Process memory is insufficient because an ingress or
local multi-worker setup may send the create to replica A and the WebSocket to
replica B. A small shared-database row makes the upstream account and local
client identity available to every replica without routing the connection
through the Responses bridge ring.

The claim lease solves a different problem: clients and intermediaries can
race duplicate WebSocket handshakes. Exactly one can own the sideband, while a
crashed pre-open attempt becomes retryable after its lease expires. A heartbeat
is required because a healthy voice session can be much longer than a safe
crash-recovery lease.

## Constraints and non-goals

- The route must recognize only the upstream call-ID shapes. A backend wildcard
  would silently expose future ChatGPT routes without a reviewed contract.
- Local API-key identity is part of the binding. Account assignment is checked
  again at join time because an operator may narrow a key between create and
  join.
- Account failover is valid before the `201`, but invalid after it. Retrying on
  a different account would attach to no such call and could expose identity
  across account pools.
- The Voice handshake has its own allowlist. Reusing the Responses builder
  would add a protocol beta header that this endpoint did not request.
- Only routing metadata is durable. SDP, sideband frames, transcripts, and
  audio-related data are neither archived nor added to request logs.
- Sideband diagnostics expose phases and header shape only. They do not emit
  call, account, key, request, session, thread, attestation-token, SDP, query,
  or frame values. The app-server attestation envelope may contribute only its
  bounded integer version/status and token-presence boolean.
- The change does not add new dashboard controls, a media recorder, a
  sideband-message schema, or a Responses transport mode.

## Failure modes

- **Malformed or absent `Location`:** fail the create and write no binding;
  returning the upstream `201` would advertise an unusable call.
- **Create succeeded but binding commit failed:** fail closed. The orphaned
  upstream call expires upstream; the client is not told to join it.
- **Key was revoked or account scope changed:** reject before upstream. Deleting
  a key also removes its bound calls rather than making them anonymous.
- **Two replicas join together:** one atomic claim wins; the loser does not
  make an upstream request.
- **Upstream handshake fails:** release only the current holder's claim and
  retain the binding so a retry targets the same account. Metadata distinguishes
  an upstream HTTP rejection from local auth, binding, account, and route
  phases; safe response classification distinguishes parsed application errors
  from likely edge/WAF responses without logging response bodies or headers.
- **Wrong upstream host/path:** the call-create response comes from the ChatGPT
  backend, but its path-based Frameless sideband joins
  `wss://api.openai.com/v1/live/<call-id>`. Replaying the call ID under the
  ChatGPT backend produces an edge 403 even with valid auth and attestation.
- **Relay or heartbeat ends:** close both peers and delete the holder-owned
  binding. A stale task cannot delete a newer claim.
- **Binding expires before join:** reject without upstream work. A connection
  that joined in time stays valid while its claim heartbeat remains owned.

## Concrete flow

1. Replica A receives `POST /backend-api/codex/realtime/calls` from local API
   key `K`. Account `acct-1` fails before a visible response, so the existing
   control retry selects `acct-2`.
2. `acct-2` returns `201 Location: /backend-api/codex/rtc_abc123`. Replica A
   commits `(rtc_abc123, acct-2, K, expiry, no claim)` and then returns the
   unchanged response.
3. The client opens
   `ws://<codex-lb>/backend-api/codex/rtc_abc123?client_version=...`; ingress
   sends it to replica B.
4. Replica B authenticates `K`, confirms `acct-2` is still assigned, and wins
   the shared claim. It refreshes only `acct-2`, resolves that account's
   upstream route, replaces auth/account headers, preserves the Voice headers
   and query, and opens `wss://api.openai.com/v1/live/rtc_abc123`.
5. Replica B relays text and binary messages transparently. When either peer
   closes, it propagates the close code/reason, awaits both relay tasks, and
   deletes the binding.

## Rollout notes

The migration is additive and starts empty, so mixed-version replicas do not
corrupt existing traffic. A new-version replica can create a binding that an
old replica cannot serve; deploy behind draining or upgrade replicas together
if live voice must work throughout rollout. Before changing a live SQLite
installation, use the repository's online-snapshot backup procedure. Validate
the full flow against a separate local instance; restarting the active
LaunchAgent is not part of implementation verification.

The isolated canary validated the current v3 call-create response and browser
SDP application. Its upstream sideband handshake remained `403` because a
standalone harness cannot produce the signed desktop-host `x-oai-attestation`
value. The released desktop host supplies that value, and this proxy preserves
the same client attestation across call creation and sideband join. Keep the
end-to-end verification task open until the signed desktop flow is exercised
after rollout; do not weaken the attestation or Voice header policy to make an
unsigned harness pass.
