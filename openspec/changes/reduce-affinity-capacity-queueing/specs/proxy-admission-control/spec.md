## ADDED Requirements

### Requirement: Session gate waiters do not reserve account startup capacity

The proxy MUST acquire the session response-create gate before reserving account response-create capacity. A request waiting for that gate MUST hold no account response-create lease. Failure or cancellation after either acquisition MUST release all resources owned by that request without releasing another request's gate.

#### Scenario: One stalled session does not saturate the account with waiters
- **GIVEN** one request owns a session gate and three additional requests are waiting for that gate
- **WHEN** an unrelated session requests account startup capacity
- **THEN** the three gate waiters contribute zero account response-create leases
- **AND** admission uses only actual admitted startup work

#### Scenario: Account admission fails after the session gate opens
- **WHEN** account startup admission fails after a request acquires its session gate
- **THEN** the session gate is released and the request retains no admission lease

### Requirement: Safe original full resends can escape local bridge pressure

For a complete original client request whose replay safety is proven, the proxy MUST retain the ability to use an independent route when its preferred bridge is busy. Eligibility MUST require no client-supplied previous response, conversation, turn state, file reference or required file owner; no upstream dispatch or response progress for the current request; and a validated original full-context body. A proxy-injected previous-response optimization MUST NOT by itself revoke this eligibility. The independent route MUST preserve the original full input and prompt-cache key, prefer an available connection on the original account, and select another eligible account if that account is locally capped. It MUST NOT replace or rebind the existing canonical bridge or its locality mapping.

#### Scenario: Busy warm bridge with another ready route
- **GIVEN** a replay-safe original full resend is eligible for capacity escape
- **AND** its warm session gate is already held
- **WHEN** the request is admitted
- **THEN** it attempts an independent connection without waiting through the busy gate's admission timeout
- **AND** it sends full context without the proxy-injected anchor

#### Scenario: Local cap race after context optimization
- **GIVEN** the proxy injected an optional anchor into a proven full resend
- **WHEN** local admission rejects it before dispatch
- **THEN** the independent route restores its original full body and enforces ordinary account eligibility

#### Scenario: Genuine continuation and accepted work remain protected
- **WHEN** a request relies on client-owned continuation state or account-owned files, lacks proven full context, or has already dispatched or received response progress
- **THEN** the capacity escape is unavailable and existing ownership/replay rules remain enforced

### Requirement: Local capacity retries wake on released capacity

Bridge retries waiting on local account or session capacity MUST recheck admission when relevant local capacity is released, bounded by the original request budget. A capacity wakeup MUST NOT grant a lease or bypass eligibility checks. Upstream quota/backoff waits MUST retain their existing timing semantics.

#### Scenario: Capacity opens during a retry sleep
- **WHEN** capacity is released while a local-capacity retry is waiting
- **THEN** it rechecks admission before the original fixed retry sleep expires

#### Scenario: Competing waiter consumes the available slot
- **WHEN** another waiter acquires capacity first after a wakeup
- **THEN** the remaining request follows normal bounded admission without exceeding configured caps

## MODIFIED Requirements

### Requirement: Account-local Responses work is capped before upstream creation

For `/v1/responses`, `/backend-api/codex/responses`, and compact Responses traffic, the proxy MUST enforce account-local response-create and streaming concurrency limits in addition to process-wide admission limits, and the configured limits MUST be cluster-wide per-account targets enforced across all replicas rather than per-replica allowances. Because per-account caps are partitioned per replica via the bridge ring and cannot be safely partitioned across intra-pod worker processes, each instance MUST run a single worker process; horizontal scaling is achieved by adding replicas. The default account response-create cap MUST be 4 and the default account stream cap MUST be 8 unless operators configure a different value.

When an account is at either cap, new soft-affinity work MUST prefer another eligible account before returning local overload. A bare process-session mapping MAY supply soft locality only while the request is self-contained, pre-visible, and has no required owner. Account-cap spillover MUST NOT switch the account of an existing shared transport or rebind durable bridge ownership. A proven complete, unsent original request MAY use a separate transport under the safe original full resend capacity-escape requirement, including after a local admission race. Hard-continuity work MUST remain on its required owner and MAY fail closed when that owner is saturated. Hard Codex ownership rows MUST bypass soft sticky fallback/reallocation so pressure cannot delete or rewrite them.

#### Scenario: Soft work avoids saturated account

- **GIVEN** account A is at its account response-create cap
- **AND** account B is eligible and below cap
- **WHEN** a self-contained `/v1/responses` request has only bare process-session affinity to account A
- **THEN** the proxy selects account B instead of queueing on account A

#### Scenario: Hard continuity owner saturation fails closed

- **GIVEN** a follow-up request requires a specific previous-response owner account
- **AND** that account is at its account stream or response-create cap
- **WHEN** no safe continuity-preserving alternative exists
- **THEN** the proxy returns a bounded local overload/continuity failure
- **AND** the failure reason is stable and low-cardinality

#### Scenario: Late WebSocket cap race does not retire shared work

- **GIVEN** a request has entered an upstream WebSocket shared with another in-flight response
- **WHEN** a later account response-create lease acquisition loses a capacity race
- **THEN** the proxy rejects only the newly unadmitted request with the existing local-cap failure
- **AND** it does not retire or switch the shared upstream WebSocket to spill that request

#### Scenario: Existing bridge ownership is not replaced by cap spillover

- **GIVEN** a session header resolves to a live or durable HTTP bridge owner
- **WHEN** that owner's account or response-create gate is saturated
- **THEN** owner-bound requests follow the existing hard bridge-capacity behavior
- **AND** a proven complete, unsent original request may use an independent route without rebinding the owner
- **AND** account-cap spillover does not publish a replacement bridge under the same canonical identity

### Requirement: HTTP bridge startup admission waits are bounded

The proxy MUST apply the configured proxy admission wait timeout to each HTTP bridge startup wait attempt for per-session response-create gate acquisition, bridge capacity waiters, and in-flight session creation waiters.

For per-session response-create gate acquisition by a bridged Responses request, an expired gate acquisition attempt MUST be treated as a recoverable capacity wait rather than a terminal failure: the request MUST release its queue slot and account lease, wait with capacity-wait progress semantics, and retry gate acquisition, bounded by the bridge request budget. Requests eligible for soft-affinity reroute or proven original full resend capacity escape MUST still attempt the independent route before entering the recoverable wait. When the bridge request budget is exhausted before the gate opens, the proxy MUST reject the request locally with HTTP 429, `error.code = "response_create_gate_timeout"`, and the stable local-overload reason.

For bridge capacity waiters and in-flight session creation waiters, when the timeout expires the proxy MUST reject the request locally with HTTP 429 and an OpenAI-style `proxy_overloaded` error envelope. Timing out while observing another request's pending in-flight session creation MUST evict that in-flight marker when it is still pending so later requests can attempt a fresh bridge session instead of waiting on the same stalled future.

If a request owns in-flight bridge session creation and is cancelled or fails after publishing the in-flight marker but before registering the created session, the proxy MUST remove or settle that in-flight marker. If a session owner later finishes creation after its in-flight marker was evicted, the owner MUST NOT return an unregistered bridge session to the caller.

#### Scenario: Gate contention queues within the bridge request budget

- **GIVEN** an HTTP bridge session whose response-create gate is held by a legitimate in-flight turn
- **AND** a bridged Responses request that lacks a safe independent route (client-owned continuity or incomplete context)
- **WHEN** a gate acquisition attempt exceeds the configured proxy admission wait timeout
- **THEN** the request emits capacity-wait keepalive progress on streaming surfaces and retries gate acquisition
- **AND** the request completes normally once the in-flight turn releases the gate before the bridge request budget expires

#### Scenario: Gate contention still fails once the request budget is exhausted

- **WHEN** a bridged Responses request retries response-create gate acquisition until the bridge request budget is exhausted
- **THEN** the request is rejected locally with HTTP 429
- **AND** the error payload uses `error.code = "response_create_gate_timeout"`
- **AND** no response-create gate lease is recorded on that request state

#### Scenario: Soft-affinity requests reroute before waiting

- **GIVEN** a bridged Responses request with a soft-affinity session key and no `previous_response_id`
- **WHEN** its first gate acquisition attempt times out
- **THEN** the proxy attempts the internal soft-affinity reroute to a fresh bridge session
- **AND** the recoverable gate wait applies only when reroute is not permitted

#### Scenario: Stuck sessions are still detected between attempts

- **WHEN** a gate acquisition attempt times out while a pending bridge request has been stuck past the stuck-gate retirement threshold
- **THEN** the stuck session retirement check still runs on that attempt

#### Scenario: In-flight bridge session creation does not finish

- **WHEN** a bridged Responses request waits on another request's in-flight session creation
- **AND** the in-flight creation does not finish before the configured proxy admission wait timeout
- **THEN** the waiter is rejected locally with HTTP 429 and `error.code = "proxy_overloaded"`
- **AND** the stalled in-flight marker is evicted if it is still pending

#### Scenario: Bridge capacity waiter does not make progress

- **WHEN** the HTTP bridge is at capacity and a request waits for in-flight bridge work to free capacity
- **AND** no capacity becomes available before the configured proxy admission wait timeout
- **THEN** the waiter is rejected locally with HTTP 429 and `error.code = "proxy_overloaded"`

#### Scenario: In-flight owner is cancelled during stale session close

- **WHEN** a bridge session creation owner has published an in-flight marker
- **AND** it is cancelled while closing a stale local bridge session before creating the replacement session
- **THEN** the in-flight marker is removed or settled
- **AND** later requests do not remain blocked on that cancelled owner's future

