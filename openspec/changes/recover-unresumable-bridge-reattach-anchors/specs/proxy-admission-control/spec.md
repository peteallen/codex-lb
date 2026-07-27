## ADDED Requirements

### Requirement: An unresumable proxy-injected reattach anchor is invalidated after a bounded eventless failure

When the eventless `response.created` watchdog fails a request whose
`previous_response_id` was injected by the proxy from a durable session's
`latest_response_id`, the proxy MUST clear that anchor from the durable session
row. The clear MUST be guarded by an exact match on the recorded
`latest_response_id`, so a newer anchor written by a concurrent turn is never
discarded. A client-supplied `previous_response_id` MUST NOT be invalidated. A
failed invalidation MUST NOT change the request's terminal outcome.

When the anchor is invalidated, the terminal error returned to that request MUST
state that the proxy-injected continuation anchor was dropped, so a retry is
known to start a fresh turn without prior server-side conversation state. The
proxy MUST emit a structured low-cardinality invalidation log without raw keys,
anchors, or prompt content.

The proxy MUST NOT introduce a second bounded-wait setting for this behavior; the
existing stuck-gate retirement threshold governs the wait, and the existing
fail-closed no-replay boundaries are unchanged.

#### Scenario: A dead proxy-injected anchor stops poisoning its lane

- **GIVEN** the proxy injected a durable session's `latest_response_id` as a
  reattach anchor on a fresh upstream websocket
- **AND** upstream accepted the `response.create` and emitted no frame
- **WHEN** the eventless `response.created` watchdog fails the request
- **THEN** the durable session's `latest_response_id` is cleared
- **AND** the request's terminal error reports that the continuation anchor was
  dropped
- **AND** an invalidation event is logged without the anchor value

#### Scenario: A concurrently updated anchor is not clobbered

- **GIVEN** a timed-out request carried a proxy-injected anchor
- **AND** the durable row's `latest_response_id` has since been replaced by a
  newer turn
- **WHEN** invalidation runs
- **THEN** the durable row is left unchanged

#### Scenario: A client-supplied continuation anchor survives

- **GIVEN** a timed-out request carried a client-supplied `previous_response_id`
- **WHEN** the eventless `response.created` watchdog fails it
- **THEN** no durable anchor is invalidated
- **AND** the terminal error does not claim an anchor was dropped

### Requirement: A downstream-visible sibling is not destroyed by an eventless failure

When the eventless `response.created` watchdog expires for one or more requests
on a bridge, the proxy MUST determine whether any other pending request on the
same websocket has downstream-visible progress -- downstream visibility or an
assigned downstream sequence number. Holding a `response_id` alone MUST NOT count
as progress.

If such a sibling exists, the proxy MUST fail only the expired requests, leave
the sibling pending, leave the upstream websocket open and the session
registered, and instead mark the bridge for reconnect and retirement after drain
so no later request is admitted to it. It MUST emit a structured
low-cardinality quarantine log. If no such sibling exists, the proxy MUST keep
retiring the bridge as before. In both cases the proxy MUST NOT transparently
replay an ambiguously dispatched request.

#### Scenario: A streaming sibling keeps its stream

- **GIVEN** one pending request has emitted downstream output on a bridge
- **AND** another pending request on the same bridge never received
  `response.created` and its bounded wait expires
- **WHEN** the watchdog fires
- **THEN** only the unacknowledged request receives a terminal failure
- **AND** the streaming request remains pending with its stream intact
- **AND** the upstream websocket is not closed and the session stays registered
- **AND** the bridge is marked for reconnect and retirement after drain
- **AND** a quarantine event is logged

#### Scenario: A sibling with only a response id is still failed

- **GIVEN** a pending sibling holds a `response_id` but has produced no
  downstream-visible output
- **WHEN** the eventless watchdog expires for the unacknowledged request
- **THEN** the bridge is retired and both requests receive terminal failures

### Requirement: Reader-driven failures retain API-key attribution

A failure raised by the upstream reader has no single calling API key and passes
none. When writing the request log for such a failure, the proxy MUST fall back
to the API key recorded on the failing request so the row keeps its
`api_key_id`. This MUST NOT change routing, health accounting, or the bytes
returned to the client.

#### Scenario: An idle-timeout row keeps its API key

- **GIVEN** a pending request was authenticated with an API key
- **WHEN** the upstream reader fails it without supplying a caller key
- **THEN** the request log row records that request's API key
