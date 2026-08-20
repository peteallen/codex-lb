## MODIFIED Requirements

### Requirement: Oversized response.create payloads are slimmed or rejected fail-fast before upstream send

When the service prepares a Responses `response.create` request, it MUST measure
the serialized outbound request size before sending it to the upstream WebSocket.
If the payload exceeds the upstream WebSocket budget, the
service MUST first attempt to slim only the historical portion of `input` that
precedes the most recent user turn: historical inline images MUST be replaced
with textual omission notices, and oversized historical tool outputs MUST be
replaced with textual omission notices that preserve the item in sequence.

If a downstream Responses WebSocket request still exceeds the budget after
historical slimming, the service MUST relay it over upstream HTTP before any
upstream dispatch when either of these shapes applies:

- it is a complete resend with no `previous_response_id`, no nonblank
  `conversation`, and a non-empty input list; or
- it carries a non-empty client-supplied `previous_response_id` and its
  non-empty input list contains only current tool-output items.

The service MUST preserve the eligible request input without another lossy
rewrite. A proxy-injected `previous_response_id` MUST NOT make a request
eligible. Every request that remains over budget and is not eligible for one of
these upstream-HTTP paths MUST fail locally with status `400` — not `413` —
carrying `error.code = "payload_too_large"`, `error.type =
"invalid_request_error"`, and `error.param = "input"`.

#### Scenario: Historical inline artifacts are slimmed and the latest user turn is preserved

- **WHEN** a Responses request exceeds the upstream WebSocket budget because
  historical inline images or historical oversized tool outputs dominate the
  serialized `input`
- **AND** replacing those historical artifacts with omission notices reduces
  the serialized request below budget
- **THEN** the service forwards the slimmed `response.create` upstream
- **AND** it preserves the most recent user turn unchanged

#### Scenario: Image-heavy complete resend continues over HTTP

- **GIVEN** a Responses WebSocket request has no `previous_response_id`, has
  no nonblank `conversation`, and has a non-empty input list
- **AND** its complete input includes inline screenshots from tool outputs
- **AND** its final projected wire body exceeds the WebSocket budget
- **WHEN** the client sends the request
- **THEN** the service sends the complete input over upstream HTTP
- **AND** it does not open an upstream WebSocket for that request
- **AND** the client receives ordinary response events on the same downstream
  WebSocket
- **AND** the service does not write an oversized-request rejection dump

#### Scenario: Conversation-backed request remains owner-bound

- **GIVEN** an oversized Responses WebSocket request carries a nonblank
  `conversation`
- **WHEN** it remains over budget after historical slimming
- **THEN** the service returns `payload_too_large`
- **AND** it does not relay that stored-object continuation over HTTP

#### Scenario: Ineligible anchored non-tool request remains fail-closed

- **GIVEN** an oversized Responses WebSocket request carries a client-supplied
  `previous_response_id` and a non-empty input list containing a non-tool item
- **WHEN** it remains over budget after historical slimming
- **THEN** the service returns `payload_too_large`
- **AND** it does not open an upstream WebSocket or relay over HTTP

## ADDED Requirements

### Requirement: An oversized full-resend fallback preserves WebSocket routing and lifecycle

An unanchored full resend relayed over upstream HTTP MUST remain a WebSocket
turn downstream, retain the session or prompt-cache affinity resolved with the
downstream handshake's synthesized turn-state classification, and carry any
already-resolved input-file owner as a hard routing constraint without a second
file-owner lookup. Its request log MUST record WebSocket as the request
transport and HTTP as the upstream transport.

The service MUST cancel the request-state reservation heartbeat when settlement
ownership moves to the HTTP streamer. If cancellation or failure occurs before
the streamer enters its settlement guard, the relay MUST release the
reservation; after that guard starts, only stream settlement owns the
reservation. Every path MUST release the response-create admission exactly
once.

The fallback MUST remain outside the shared upstream WebSocket pending set. A
later unanchored full resend on the same Codex WebSocket MUST NOT overtake an
active fallback. An anchored request MAY use the shared upstream WebSocket
concurrently when its ownership permits it; connection-level `response.cancel`
MUST target whichever active request began most recently.

#### Scenario: File owner proof crosses the transport boundary once

- **GIVEN** request preparation resolves an `input_file.file_id` to account `A`
- **WHEN** the oversized full resend is relayed over HTTP
- **THEN** the HTTP streamer treats `A` as the required file owner
- **AND** it does not repeat or downgrade the file-owner lookup

#### Scenario: A second full resend cannot overtake the HTTP relay

- **GIVEN** an oversized unanchored full resend is active over upstream HTTP
- **WHEN** the same downstream WebSocket sends another unanchored full resend
  before the first turn reaches a terminal event
- **THEN** the service rejects the later resend as a continuity conflict
- **AND** it does not start a second upstream request

#### Scenario: Cancellation before settlement ownership releases the reservation

- **GIVEN** a fallback relay has transferred its reservation out of the
  WebSocket request state
- **AND** the HTTP stream has not entered its settlement guard
- **WHEN** the relay is cancelled
- **THEN** its request-state heartbeat is stopped
- **AND** the relay releases the reservation exactly once

#### Scenario: Cancellation follows the newest active transport

- **GIVEN** an HTTP fallback remains active after `response.created`
- **AND** a newer anchored request is active on the shared upstream WebSocket
- **WHEN** the client sends connection-level `response.cancel`
- **THEN** the cancel frame is forwarded to the newer upstream WebSocket turn
- **AND** it does not cancel the older HTTP fallback

### Requirement: WebSocket continuity respects the transport that created the response

The service MUST record whether the latest response in WebSocket continuity was
created by upstream WebSocket or upstream HTTP. It MUST use only a
WebSocket-created response as a proxy-injected anchor on a later unanchored
request. When a client-supplied `previous_response_id` exactly matches the
latest HTTP-created response for the same continuity scope, the service MUST
preserve that anchor and relay the continuation over upstream HTTP regardless
of whether the continuation itself exceeds the WebSocket frame budget.

Only an exact normalized upstream transport value of `http` may select this
persisted-provenance path. Legacy rows whose upstream transport is `NULL`,
WebSocket-created rows, and rows containing an unrecognized transport value
MUST NOT be inferred as HTTP; their continuations remain on the ordinary
WebSocket path and remain subject to its frame-size limit.

After a WebSocket-downstream, HTTP-upstream response completes successfully,
the service MUST publish its account and HTTP transport provenance to the
API-key-scoped owner cache before starting request-log persistence. It MUST
wait for that tracked persistence attempt before forwarding the held terminal
frame, while preserving the completed terminal if the observational log write
itself fails. A successful persistence commit MUST let a fresh service instance
route an exact continuation over HTTP.

#### Scenario: Matching HTTP continuation remains on HTTP

- **GIVEN** the latest response for a WebSocket continuity scope completed over
  upstream HTTP
- **WHEN** the client sends a small continuation with that exact
  `previous_response_id`
- **THEN** the service preserves the client-supplied anchor
- **AND** it relays the continuation over upstream HTTP
- **AND** it does not open or reuse an upstream WebSocket for that request

#### Scenario: A different client anchor is not forced onto HTTP

- **GIVEN** the latest response completed over upstream HTTP with response ID
  `A`
- **WHEN** the client sends a continuation with a client-supplied
  `previous_response_id` of `B`
- **AND** `B` does not equal `A`
- **THEN** the service does not classify the request as a continuation of the
  HTTP-created response
- **AND** absent another fallback eligibility condition, it follows the
  ordinary upstream WebSocket path

#### Scenario: Matching WebSocket continuation remains on WebSocket

- **GIVEN** the latest response completed over upstream WebSocket with response
  ID `A`
- **WHEN** the client sends a continuation with `previous_response_id` of `A`
- **THEN** the service preserves the client-supplied anchor
- **AND** it sends the continuation over the upstream WebSocket
- **AND** it does not relay the request over upstream HTTP

#### Scenario: Missing or unknown transport provenance is never inferred as HTTP

- **GIVEN** a persisted response owner record exactly matches a client-supplied
  `previous_response_id`
- **AND** its upstream transport is legacy `NULL` or an unrecognized value
- **WHEN** the client sends a continuation within the WebSocket frame budget
- **THEN** the service follows the ordinary upstream WebSocket path
- **AND** it does not relay the request over upstream HTTP
- **WHEN** the same continuation exceeds the WebSocket frame budget
- **THEN** the service returns `payload_too_large`
- **AND** it still does not relay the request over upstream HTTP

#### Scenario: HTTP completion is not injected into an unanchored resend

- **GIVEN** the latest response completed over upstream HTTP
- **WHEN** the client sends a complete resend without `previous_response_id`
- **THEN** the service does not inject the HTTP-created response ID
- **AND** an oversized resend remains eligible for the unanchored HTTP fallback

#### Scenario: HTTP provenance is immediate and restart-resilient

- **GIVEN** a WebSocket-downstream response completes over upstream HTTP with
  response ID `A` on account `X`
- **WHEN** a different session using the same API-key scope immediately
  continues `A`
- **THEN** the owner cache identifies `X` and HTTP as the upstream transport
  before request-log persistence can race that continuation
- **AND** the service does not send `A` over an upstream WebSocket
- **WHEN** a fresh service instance resolves `A` after the successful terminal
  persistence commit
- **THEN** the request log identifies `X` and HTTP as its durable provenance
