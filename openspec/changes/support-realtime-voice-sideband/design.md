# Design: support-realtime-voice-sideband

## 1. Capture the account at the create-response boundary

`POST /backend-api/codex/realtime/calls` remains a previsible Codex control
request, so its normal pre-open selection, credential refresh, and account
failover may run. The control path must retain the account that produced the
final response. Only an upstream `201` with a parseable, fragment-free
`Location` whose terminal path segment is one validated call identifier creates
a binding. Accepted identifiers are a single safe URL segment beginning `rtc_`
and containing only URL-safe identifier characters, or a canonical hyphenated
UUID. The preceding path is trusted upstream metadata and is not constrained or
interpreted. Empty or invalid terminal identifiers and terminal segments with
percent-encoded separators are rejected.

The binding is committed before the `201` is returned downstream. A missing or
malformed location, a call-ID collision, or a database failure is therefore a
failed create from the client's perspective, rather than a successful call
that is guaranteed to fail at its next step. Non-201 upstream responses never
write bindings. The existing downstream `Location` representation remains
unchanged.

The control response type should carry the selected account ID internally (or
the realtime handler should receive an equivalent private result); the account
identity must not be reconstructed from a later selector call. The computed
control `request_kind` must also be passed into request logging so this route
is recorded as `codex_control_realtime_calls`.

## 2. Shared metadata and ownership claim

The Alembic migration adds `realtime_call_bindings`:

- `call_id` — primary key;
- `account_id` — non-null foreign key to `accounts`, cascade delete;
- `api_key_id` — nullable foreign key to `api_keys`, cascade delete rather than
  converting an authenticated call into an unauthenticated one;
- `created_at` and `expires_at` — non-null UTC timestamps;
- `claim_holder` and `claim_expires_at` — nullable lease ownership fields;
- an expiry index for bounded opportunistic cleanup.

The row deliberately stores no `Location`, SDP, message, transcript, audio, or
other call content. Unjoined rows use a short server-defined lifetime. A join
must begin before `expires_at`; a successfully joined connection may outlive
that pre-open deadline because its separate claim lease is renewed. Expired
unjoined rows are removed opportunistically without adding a scheduler.

Each join attempt uses a process/attempt-unique holder ID and claims with one
conditional database write: the call exists, has not expired, matches the
authenticated API-key identity, and is unclaimed or its old claim has expired.
This is the correctness boundary on both SQLite and PostgreSQL; a process-local
lock is not sufficient. A holder renews only its own claim at an interval well
inside the claim TTL. Losing ownership closes both sockets rather than allowing
two relays to continue.

A failure before the upstream WebSocket opens releases the claim with a
holder-matched update and leaves the binding for a retry. Once an upstream
sideband has opened, any terminal relay exit deletes the binding with a
holder-matched delete. Stale holders can neither release nor delete a newer
holder's row.

## 3. Authenticate and authorize before outbound work

The existing proxy WebSocket authentication guard runs before any binding
lookup. This preserves the normal API-key-enabled behavior and the existing
raw-peer rules when global proxy auth is disabled without creating an
identifier-enumeration shortcut.

After authentication, the join must match the exact stored local API-key ID:
the same non-null ID for an authenticated create, or `NULL` for both an
allowed unauthenticated create and join. The bound account must still be in
that key's current account-assignment scope. Unknown, inactive, expired, or
otherwise invalid keys are rejected by the guard; key deletion cascades its
bindings. A scope change that removes the account rejects the join. All of
these checks, plus expiry and claim availability, complete before an upstream
connection is attempted.

The route matches only
`/backend-api/codex/<validated-call-id>` for the two call-ID forms. It does not
capture arbitrary backend Codex paths. The original query parameters are
forwarded in order, including repeated keys.

## 4. Bound-account connection, not a new balancing decision

After the claim, the service loads the bound account directly and applies the
normal freshness rules to that account only. It does not call the account
selector and does not cross to another account after refresh, routing, proxy,
handshake, or relay failure. A same-account refresh/retry is permitted where
the existing token rules allow it. Failed pre-open retries therefore retain
the account that created the call.

The connection resolves the bound account's existing upstream route and uses
its established fail-closed, proxy-endpoint, or direct-egress behavior. Route
resolution may select an allowed endpoint for that same account, but it may
not change the account identity.

The downstream path-based join is the Frameless Bidi transport. Although the
WebRTC call is created through the ChatGPT Codex backend, released Codex joins
its sideband through OpenAI's transceiver at
`wss://api.openai.com/v1/live/<call-id>`. The proxy must make that target
translation for either accepted call-ID representation while preserving the
downstream query string. Replaying `<call-id>` against the ChatGPT call-create
base is not an equivalent route and is rejected at the edge.

## 5. Dedicated Voice handshake builder

The Responses WebSocket builder is intentionally not reused: it injects
`OpenAI-Beta: responses_websockets=2026-02-06` and participates in Responses
continuity behavior that the Voice sideband does not speak.

The Voice builder starts from a case-insensitive allowlist of the safe headers
needed by the live-voice contract. It preserves Voice feature headers (notably
`OpenAI-Alpha: quicksilver=v2`), `x-session-id`, recognized Codex
session/thread headers, first-party `originator`/version/user-agent identity,
and the current attestation/requirements-token headers. It replaces every
downstream `Authorization` and ChatGPT account-ID spelling with one bearer
token and account ID from the bound account.

The builder removes `Cookie`, `Forwarded`, every `X-Forwarded-*` and
`Proxy-*` header, `Connection`, `Upgrade`, `Host`, `Keep-Alive`, `TE`,
`Trailer`, `Transfer-Encoding`, and every downstream `Sec-WebSocket-*`
handshake header. It neither copies nor synthesizes the Responses WebSocket
beta token. The upstream WebSocket client owns the new handshake headers.

## 6. Transparent duplex relay and cleanup

The relay owns two tasks: downstream-to-upstream and upstream-to-downstream.
Text remains text and binary remains the same bytes; the proxy does not parse
the sideband protocol. A close received from either peer propagates its valid
code and reason to the other peer. When either direction ends or raises, the
coordinator cancels and awaits the sibling, closes any still-open sockets, and
performs holder-matched binding cleanup exactly once.

The downstream socket is accepted only after authentication, authorization,
claiming, bound-account refresh, route resolution, and the upstream handshake
have succeeded. Pre-open errors can therefore use a denial response and cannot
strand an accepted client socket. Relay exceptions are transport failures for
this call only; they do not enter Responses pending-turn, continuity,
reservation, archive, or settlement paths.

## 7. Compatibility and observability

The new route and service are separate from `/backend-api/codex/responses` and
`/v1/responses`. Their headers, event transformations, keepalives, account
affinity, retries, close handling, and request accounting remain unchanged.
Sideband logging is metadata-only and must never emit payload/frame content.
Realtime create logs retain the normal selected account and status metadata
while using the dedicated request kind.
