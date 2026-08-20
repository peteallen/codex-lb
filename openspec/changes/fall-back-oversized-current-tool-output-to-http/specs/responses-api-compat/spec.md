## ADDED Requirements

### Requirement: An oversized current tool-output turn falls back to upstream HTTP

When a downstream Responses WebSocket `response.create` carries a non-empty
client-supplied `previous_response_id` and exceeds the upstream websocket frame
budget, the service MUST relay that single anchored turn over upstream HTTP if
and only if its `input` is a non-empty list whose every item is a current
tool-output item and the projected per-account wire frame still exceeds the
budget. Every other oversized anchored turn MUST keep the existing
`payload_too_large` rejection with its oversized-request dump.

A turn whose `previous_response_id` was injected by the proxy MUST NOT be
eligible, because that body was rewritten against a durable anchor the client
never supplied and is therefore not a delta the client could reproduce.

The fallback decision MUST be made before any upstream dispatch, so no
ambiguously dispatched request becomes replayable, and the terminal no-replay
rules MUST be unchanged. The relayed turn MUST NOT be registered in the shared
upstream websocket's pending set.

#### Scenario: Oversized current tool output completes over HTTP

- **GIVEN** a Responses WebSocket turn anchored by a client-supplied
  `previous_response_id` whose input is only current tool outputs
- **AND** its wire frame exceeds the upstream websocket budget
- **WHEN** the client sends it
- **THEN** the turn is relayed over upstream HTTP
- **AND** no upstream websocket is opened for it
- **AND** the client receives the ordinary `response.created`, incremental, and
  terminal events on the same websocket

#### Scenario: Other oversized anchored turns are still rejected

- **WHEN** an oversized anchored turn has any non-tool-output input item or
  carries a proxy-injected anchor
- **THEN** the service returns `payload_too_large`
- **AND** it records the oversized-request dump as before

#### Scenario: A rejected oversized turn still releases its reservation

- **WHEN** an oversized turn is found ineligible and rejected
- **THEN** its API-key usage reservation is released

### Requirement: A fallback turn keeps its websocket identity and settles exactly once

A turn relayed over upstream HTTP MUST remain a websocket turn downstream: the
same socket, the same event shapes, and Codex keepalives while it is still
pre-created. Its request log MUST record the websocket request transport with an
HTTP upstream transport.

The service MUST hold the terminal frame until the upstream stream is drained so
a retry can never follow a terminal frame downstream. It MUST release the
response-create gate on `response.created` and on every exit, settle or release
the API-key reservation under one explicit owner, and cancel and await the relay
task when the client disconnects, when the relay is the newest active turn and
the client sends `response.cancel`, or when the connection is torn down. A
downstream idle close MUST NOT fire while a fallback relay owns a turn.

#### Scenario: Cancel terminates the fallback relay

- **GIVEN** a fallback turn is the newest active request on its downstream
  websocket
- **AND** it is streaming
- **WHEN** the client sends `response.cancel`
- **THEN** the relay task is cancelled and awaited
- **AND** the gate and reservation are released

#### Scenario: Idle close does not interrupt a fallback turn

- **GIVEN** a fallback turn is streaming and no downstream frame has arrived
- **WHEN** the downstream idle timeout elapses
- **THEN** the connection is not closed as idle

### Requirement: Websocket-resolved owner and session context survive the HTTP hop

When a websocket-originated turn is relayed over upstream HTTP, the service MUST
use the previous-response owner account and owner-lookup session id already
resolved on the websocket path instead of re-deriving them from HTTP headers. The
resolved owner-lookup session id MUST also be recorded on owner-unavailable
request logs.

A turn-state synthesized for the current downstream handshake MUST retain that
classification across the HTTP hop so it does not override a durable session or
prompt-cache affinity. An input-file owner resolved during websocket preparation
MUST be passed as a hard file-owner constraint rather than looked up again.

#### Scenario: A fallback continuation stays on its owner account

- **GIVEN** a fallback turn whose previous response is owned by account `A`
- **WHEN** it is relayed over upstream HTTP
- **THEN** the HTTP streamer treats `A` as the resolved owner without a second
  header-derived lookup
- **AND** it does not attempt the continuation as another account

### Requirement: A hard owner-bound continuation surfaces its own upstream error

When a continuation is hard-bound to a previous-response owner and has no verified
fresh replay body, a pre-visible error from that owner MUST be surfaced to the
client unchanged. The service MUST NOT penalize or exclude the owner and then
report the resulting selection miss as
`previous_response_owner_unavailable`.

#### Scenario: An unsupported-parameter error is not rewritten

- **GIVEN** a continuation hard-bound to its previous-response owner with no
  verified fresh replay body
- **WHEN** the owner returns a pre-visible `invalid_request_error` with message
  `Unsupported parameter: previous_response_id`
- **THEN** the client receives that exact code, message, and param
- **AND** the owner is not health-penalized for it
- **AND** the error is not replaced by `previous_response_owner_unavailable`
