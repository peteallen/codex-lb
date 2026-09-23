## ADDED Requirements

### Requirement: Recoverable upstream overload waits for eligible capacity

For raw HTTP, bridged HTTP, and direct WebSocket Responses traffic, an explicit upstream overload received before acceptance or downstream-visible output MUST enter recovery instead of immediately emitting a terminal error. Recovery MUST prefer another eligible account over soft session or prompt-cache affinity. If eligible capacity is temporarily unavailable, the request MUST wait with existing keepalive semantics until capacity recovers, its request deadline expires, or the client cancels. A recoverable overload MUST NOT terminate solely because a fixed account-attempt count is exhausted.

Recovery MUST preserve file and upstream-state ownership unless a complete account-neutral request is available under the existing replay proof. An upstream response id, visible response progress, or delivered tool action MUST retain the existing no-replay guards. Generic failures MUST NOT acquire overload retry eligibility solely from a 5xx status.

#### Scenario: Initial raw HTTP overload uses another account
- **GIVEN** account A is preferred by soft affinity and account B is eligible
- **WHEN** A returns a first-event `server_is_overloaded` or `overloaded_error` without an upstream response id
- **THEN** the original request is retried safely through B without exposing A's terminal error
- **AND** the client receives B's ordinary completion events

#### Scenario: Repeated overload waits beyond the attempt-count threshold
- **WHEN** every eligible account temporarily rejects a pre-acceptance request with overload and the request budget remains
- **THEN** recovery releases attempt leases and waits before reconsidering capacity
- **AND** later restored capacity completes the same downstream request

#### Scenario: Accepted or visible work is not replayed
- **WHEN** an overload arrives with an upstream response id or after visible response progress
- **THEN** the proxy preserves the existing terminal behavior and does not repeat the request

#### Scenario: Owner-bound rejection waits without crossing accounts
- **GIVEN** a request requires an upstream owner and has no verified complete account-neutral replay
- **WHEN** that owner temporarily rejects it before acceptance with overload
- **THEN** the request waits for its owner within the request budget
- **AND** it is never dispatched on another account

#### Scenario: Cancelled overload waiter releases resources
- **WHEN** the downstream cancels while overload recovery is waiting
- **THEN** waiting stops promptly and admission, stream leases, and the logical API-key reservation are released or settled exactly once
