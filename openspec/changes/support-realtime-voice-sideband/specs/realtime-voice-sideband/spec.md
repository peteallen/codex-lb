# realtime-voice-sideband delta

## ADDED Requirements

### Requirement: Successful realtime call creation establishes a durable exact-account binding

When `POST /backend-api/codex/realtime/calls` receives an upstream `201`, the
system MUST validate the response `Location`, extract its terminal call ID, and
persist a shared-database binding before returning the success downstream. The
accepted terminal call ID MUST be exactly one URL-safe `rtc_*` segment or one
canonical hyphenated UUID. The preceding path is trusted upstream metadata and
MUST NOT be required to match a particular prefix or otherwise interpreted for
call-ID extraction. Missing or empty terminal IDs, invalid terminal IDs,
encoded path separators within the terminal segment, fragments, and
unparseable locations MUST be rejected. The downstream `Location` MUST retain
the upstream representation.

The binding MUST contain the final account that actually returned the `201`
after any allowed create-time refresh or failover, the authenticated local API
key ID or `NULL` when the create was validly unauthenticated, and bounded
creation/expiry metadata. It MUST NOT be derived from a second account
selection. The binding MUST use the call ID as a first-writer-wins primary key
and MUST NOT overwrite an existing binding. A malformed or missing location,
call-ID collision, or binding commit failure MUST fail the create rather than
returning an unusable `201`. A non-201 upstream response MUST NOT create a
binding.

Realtime call creation request logs MUST use request kind
`codex_control_realtime_calls` and retain the final selected account and normal
control-request outcome metadata.

#### Scenario: Create failover binds the account that returned the call

- **GIVEN** the first selected account fails before a visible create response
- **AND** the normal previsible control retry selects a second account
- **WHEN** the second account returns `201` with a valid `rtc_*` location
- **THEN** the persisted binding names the second account
- **AND** the binding is committed before the `201` is returned downstream
- **AND** the request log kind is `codex_control_realtime_calls`

#### Scenario: A canonical UUID location is bindable

- **WHEN** upstream returns `201` whose location ends in a canonical hyphenated
  UUID call ID
- **THEN** that exact UUID is persisted as the call ID
- **AND** the original `Location` header is returned downstream

#### Scenario: A trusted upstream path prefix is opaque

- **WHEN** upstream returns `201` with a parseable, fragment-free location whose
  terminal segment is a valid `rtc_*` call ID under a different upstream path
  prefix
- **THEN** that terminal call ID is persisted
- **AND** the preceding path does not cause the location to be rejected

#### Scenario: Invalid successful response fails closed

- **WHEN** upstream returns `201` with a missing location, an empty terminal
  segment, an encoded separator in the terminal segment, a fragment, an
  unparseable location, or an invalid terminal call ID
- **THEN** the client does not receive a successful `201`
- **AND** no call binding is written

#### Scenario: Failed call creation does not reserve an ID

- **WHEN** the realtime call create receives a non-201 upstream response
- **THEN** no call binding is written

#### Scenario: A call ID cannot be rebound

- **GIVEN** a binding already exists for a call ID
- **WHEN** a later successful create response presents the same call ID
- **THEN** the existing binding is not overwritten
- **AND** the later create fails closed

### Requirement: Sideband joins are narrowly routed and authorized before lookup or upstream access

The system SHALL expose backend Codex WebSocket handling only for paths whose
single terminal segment is a validated `rtc_*` call ID or canonical hyphenated
UUID. The feature MUST NOT add an unrestricted `/backend-api/codex/{path}`
WebSocket wildcard. It MUST preserve the downstream query parameters, including
ordering and repeated keys, when constructing the matching upstream URL.
Because these path-based joins are the Frameless Bidi transport, the system
MUST target `wss://api.openai.com/v1/live/<call-id>` for both accepted call-ID
forms. It MUST NOT replay the call ID under the ChatGPT backend call-create
base.

The existing proxy WebSocket authentication guard MUST run before any call
binding lookup. After authentication, the join identity MUST exactly match the
binding's local API-key ID (including `NULL` only when both create and join are
validly unauthenticated), and the bound account MUST remain in that API key's
current account-assignment scope. Unknown, expired, malformed, already-claimed,
wrong-key, revoked-key, and newly out-of-scope joins MUST be rejected before
any upstream WebSocket request.

#### Scenario: Arbitrary backend path is not captured

- **WHEN** a client opens a backend Codex WebSocket whose path segment is
  neither a valid `rtc_*` ID nor a canonical UUID
- **THEN** realtime sideband handling does not claim the route
- **AND** no binding lookup or upstream request is made by this feature

#### Scenario: Authentication precedes binding lookup

- **GIVEN** proxy WebSocket authentication rejects a missing, unknown,
  inactive, or expired API key
- **WHEN** the client presents a syntactically valid call path
- **THEN** the system returns the existing authentication denial
- **AND** it does not look up the call binding
- **AND** it makes no upstream request

#### Scenario: Exact API-key identity is required

- **GIVEN** a call was created by API key `K1`
- **WHEN** API key `K2` attempts to join its call ID
- **THEN** the join is rejected before any upstream request

#### Scenario: Current account assignment is required

- **GIVEN** a call was created while its bound account was assigned to API key
  `K`
- **AND** an operator removes that account from `K` before the join
- **WHEN** `K` attempts to join
- **THEN** the join is rejected before any upstream request

#### Scenario: Query parameters survive the sideband hop

- **WHEN** an authorized client joins with multiple ordered query parameters,
  including repeated names
- **THEN** the upstream handshake receives the same ordered parameter pairs

#### Scenario: Frameless sideband uses the Live transceiver endpoint

- **GIVEN** a successful ChatGPT backend call-create returned an `rtc_*` or
  canonical UUID call ID
- **WHEN** the matching path-based sideband is joined
- **THEN** the upstream target is
  `wss://api.openai.com/v1/live/<call-id>`
- **AND** the proxy does not append the call ID to the ChatGPT backend base

### Requirement: A shared atomic lease admits at most one sideband owner

The system MUST claim a call binding with one atomic shared-database conditional
write that succeeds only when the row exists, is unexpired, matches the local
API-key identity, and has no live holder. A process-local lock MUST NOT be the
cross-replica correctness mechanism. The holder MUST renew only its own lease
often enough to support a healthy long-lived connection. If it loses lease
ownership, it MUST terminate both sides of its relay.

A failure before the upstream WebSocket opens MUST release only that holder's
claim and MUST retain the account binding for a retry. Once the upstream
WebSocket has opened, every terminal relay exit MUST delete the binding using a
holder-matched operation. An old holder MUST NOT release or delete a newer
holder's binding.

#### Scenario: Simultaneous joins on two replicas have one winner

- **GIVEN** replicas A and B share the database and race to join the same
  unclaimed call
- **WHEN** both execute the atomic claim
- **THEN** exactly one replica wins
- **AND** exactly one upstream WebSocket request is made
- **AND** the losing replica rejects the join

#### Scenario: Pre-open failure remains retryable on the same binding

- **GIVEN** an authorized join wins the claim
- **AND** account refresh, route resolution, or the upstream handshake fails
  before the upstream WebSocket opens
- **WHEN** cleanup completes
- **THEN** that holder's claim is released
- **AND** the call remains bound to its original account for a later retry

#### Scenario: Lease heartbeat supports a long voice session

- **GIVEN** an opened sideband remains connected beyond the initial claim TTL
- **WHEN** the owner continues renewing its holder-matched lease
- **THEN** another replica cannot claim the call

#### Scenario: Terminal relay consumes the binding

- **GIVEN** the upstream sideband opened successfully
- **WHEN** either relay direction terminates
- **THEN** both relay directions are settled
- **AND** the current holder deletes the binding
- **AND** the same call ID cannot be joined again

### Requirement: An established call never fails over to another account

After winning a claim, the system MUST load and refresh only the account stored
in the binding. It MUST NOT run normal account selection or fail over to another
account because of credential, account-state, route, proxy, handshake, or relay
failure. A permitted refresh or connection retry MUST remain on the bound
account. The service MUST resolve and honor that account's existing upstream
proxy/direct-egress policy without changing the account identity.

#### Scenario: A failed pre-open retry retains account ownership

- **GIVEN** a call is bound to account `A`
- **AND** its first sideband attempt fails before upstream open and releases the
  claim
- **WHEN** the client retries the join
- **THEN** the service loads and refreshes account `A` again
- **AND** it never selects account `B`

#### Scenario: Bound account failure does not cross accounts

- **GIVEN** a call is bound to account `A`
- **AND** refreshing or connecting account `A` fails
- **WHEN** another healthy account is selectable for ordinary requests
- **THEN** no sideband request is sent as that other account
- **AND** the join fails or remains retryable according to its pre-open state

#### Scenario: Bound account uses its configured upstream proxy

- **GIVEN** the bound account resolves to an upstream proxy route
- **WHEN** the sideband opens
- **THEN** its upstream WebSocket uses that route
- **AND** the bound account remains unchanged

#### Scenario: Bound account may use direct egress

- **GIVEN** the bound account's current route policy resolves to direct egress
- **WHEN** the sideband opens
- **THEN** its upstream WebSocket connects directly as that account

### Requirement: Voice sideband handshakes use dedicated sanitized headers

The system MUST build the upstream Voice handshake independently of the
Responses WebSocket header builder. It MUST replace all downstream
authorization and ChatGPT account identity values with exactly one bearer token
and account ID from the bound account. It MUST preserve a case-insensitive
allowlist of safe Voice/session/thread/originator/attestation headers required
by the client contract, including `OpenAI-Alpha: quicksilver=v2` and
`x-session-id`.

The builder MUST strip cookies; `Forwarded`, `X-Forwarded-*`, and `Proxy-*`;
hop-by-hop headers; host; and downstream `Sec-WebSocket-*` handshake headers.
It MUST NOT inject or forward the Responses WebSocket beta token
`responses_websockets=2026-02-06`. The upstream WebSocket client MUST generate
its own handshake headers.

#### Scenario: Bound identity replaces downstream identity

- **GIVEN** a join carries downstream authorization and account-ID headers
- **WHEN** the upstream Voice headers are built
- **THEN** exactly one authorization value contains the bound account token
- **AND** exactly one ChatGPT account-ID value contains the bound account ID
- **AND** no downstream credential or account identity survives

#### Scenario: Voice compatibility headers are preserved

- **GIVEN** a join carries `OpenAI-Alpha: quicksilver=v2`, `x-session-id`, and
  allowlisted thread, originator, and attestation headers
- **WHEN** the upstream handshake is opened
- **THEN** those values are preserved case-insensitively

#### Scenario: Unsafe and Responses-specific headers are absent

- **GIVEN** a join carries cookies, forwarding, proxy, hop-by-hop, downstream
  WebSocket handshake headers, and a Responses WebSocket beta token
- **WHEN** the Voice handshake is built
- **THEN** none of those unsafe or Responses-specific values reaches upstream
- **AND** `responses_websockets=2026-02-06` is not synthesized

### Requirement: Sideband setup failures are observable without exposing call content or credentials

The system MUST log metadata-only sideband setup outcomes that distinguish
local WebSocket authentication, binding lookup, API-key match, atomic claim,
bound-account authorization/refresh, route resolution, and upstream handshake
phases. A rejected upstream handshake MUST retain its upstream HTTP status and
an explicitly allowlisted, log-safe error-code token separately from the downstream status.
Handshake diagnostics MAY record whether the response declared JSON, parsed as
an OpenAI error, or carried Cloudflare/server header names, but MUST NOT log any
response body, message, request ID, or header value.

Header diagnostics MUST be limited to presence booleans for attestation,
alpha, session, thread, originator, and user-agent headers; alpha validity; and
the app-server attestation envelope's bounded integer version/status and opaque
token-presence boolean. They MUST NOT emit header values or lengths, API keys,
account/call/session/thread/request identifiers, SDP, query values, sideband
frames, transcripts, audio, or attestation token content. Unrecognized
upstream error codes MUST be replaced with a fixed safe fallback. Diagnostic
parsing MUST treat malformed or pathological bounded attestation envelopes as
invalid metadata and MUST NOT alter authentication or routing behavior.

#### Scenario: Local and upstream 403 responses remain distinguishable

- **WHEN** local authentication, binding authorization, or bound-account
  authorization rejects a sideband with HTTP 403
- **THEN** diagnostics identify the corresponding local failure phase
- **AND** no upstream status is attributed to that denial
- **WHEN** the upstream sideband handshake instead returns HTTP 403
- **THEN** diagnostics identify the upstream-handshake phase and status 403
- **AND** expose only a bounded safe error-code token and response-shape flags

#### Scenario: Attestation diagnostics never expose the opaque token

- **GIVEN** `x-oai-attestation` contains an app-server JSON envelope with
  version, status, and an opaque token
- **WHEN** sideband setup succeeds or fails
- **THEN** logs may identify envelope validity, version, status, and whether a
  non-empty token was present
- **AND** the opaque token and all other header values are absent from logs

### Requirement: The sideband relay is transparent, symmetric, and content-free

After upstream open, the system SHALL relay downstream and upstream
concurrently with two owned tasks. Text messages MUST remain identical text and
binary messages MUST remain identical bytes. A close from either peer MUST
propagate its valid close code and reason to the other peer. When either relay
direction ends or fails, the system MUST cancel and await its sibling, close
both sockets as needed, stop the claim heartbeat, and perform holder-matched
binding cleanup exactly once.

The service MUST NOT decode sideband application messages into the Responses
state machine and MUST NOT persist or content-log the realtime call body/SDP,
sideband frames, transcripts, or audio-related data.

#### Scenario: Text and binary frames retain their type and content

- **WHEN** either peer sends text and binary sideband messages
- **THEN** the other peer receives the same text and bytes in order
- **AND** the proxy does not parse them as Responses events

#### Scenario: Downstream close propagates upstream

- **WHEN** the downstream client closes with a valid code and reason
- **THEN** the upstream socket is closed with that code and reason
- **AND** both relay tasks and the heartbeat are awaited or cancelled cleanly

#### Scenario: Upstream close propagates downstream

- **WHEN** upstream closes with a valid code and reason
- **THEN** the downstream socket is closed with that code and reason
- **AND** terminal binding cleanup occurs exactly once

#### Scenario: Call content is not archived

- **WHEN** realtime call creation and sideband relay complete
- **THEN** persistent storage contains only the bounded routing/claim metadata
  needed by this feature
- **AND** no SDP, frame, transcript, or audio-related content is archived or
  written to request logs

### Requirement: Realtime sideband support does not change Responses WebSockets

The realtime sideband route MUST NOT use Responses pending-turn, continuity,
bridge, retry, keepalive, event-rewrite, reservation, archive, or settlement
machinery. Existing `/backend-api/codex/responses` and `/v1/responses`
WebSocket behavior MUST remain unchanged, including their use of the Responses
WebSocket beta where required.

#### Scenario: Responses routing and headers remain unchanged

- **GIVEN** realtime sideband support is enabled
- **WHEN** a client uses `/backend-api/codex/responses` or `/v1/responses` over
  WebSocket
- **THEN** the request follows the existing Responses WebSocket service
- **AND** its header normalization, account continuity, events, and cleanup do
  not pass through the Voice sideband implementation
