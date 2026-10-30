## ADDED Requirements

### Requirement: Terminal authorization evidence precedes generic failover

The proxy MUST classify explicit permanent credential/account codes as non-retryable before generic transient status or message handling. It MUST NOT force an authentication refresh or replay a request after an explicit terminal authorization failure. An unknown HTTP 403 authorization denial MUST be surfaced without cross-account failover, including after a forced refresh, even when its normalized code defaults to upstream_error or its message resembles capacity rejection. Explicit rate-limit/quota and exact model/security/trusted-access fallback MUST retain their documented ownership and settlement constraints. Generic HTTP 401, including `token_expired` at the access-token boundary, MUST retain its existing bounded refresh handling. `token_expired` at the OAuth refresh boundary MUST remain a permanent refresh failure under the existing rotation guards.

#### Scenario: Unknown authorization denial
- **WHEN** HTTP or WebSocket Responses receives an unknown HTTP 403 before downstream visibility
- **THEN** the original denial is surfaced and no other account is tried

#### Scenario: Denial after refresh
- **WHEN** an initial HTTP 401 is followed by HTTP 403 after forced refresh
- **THEN** the original HTTP 403 is surfaced without another account attempt

#### Scenario: Explicitly revoked token
- **WHEN** a proxy call returns token_revoked
- **THEN** the account requires reauthentication and the call terminates without forced-refresh replay
