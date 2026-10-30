## ADDED Requirements

### Requirement: Usage requests respect upstream Retry-After

Usage fetch and reset-credit consumption MUST wait at least a valid nonnegative numeric or HTTP-date Retry-After delay before retrying a retryable HTTP response, for direct and routed transports. Missing or invalid headers MUST retain local exponential backoff. Retry attempts MUST remain bounded and waits MUST be cancellable. A final error MUST preserve the remaining Retry-After delay, and background usage refresh MUST defer subsequent process-local polling and forced-refresh retries until that delay expires.

#### Scenario: Server wait exceeds local backoff cap
- **WHEN** a retryable usage response has Retry-After of 60 seconds
- **THEN** neither transport sends the next attempt before 60 seconds

#### Scenario: HTTP-date and invalid headers
- **WHEN** a retryable usage response has a future HTTP-date Retry-After
- **THEN** the next attempt waits until at least that date
- **AND** an invalid or absent header uses local exponential backoff

### Requirement: Usage terminal state requires explicit evidence

Usage refresh MUST NOT deactivate an account solely because of HTTP 402 or 404. Explicit account deactivation codes or recognized deactivation messages MUST continue to deactivate. Explicit `token_revoked`, `session_revoked`, and `authentication_token_revoked` codes MUST require reauthentication, stop forced-refresh retries, and exclude the account from subsequent usage cycles until reauthentication. These codes MUST also be terminal at the OAuth refresh boundary under the existing token-rotation compare-and-set guards. The implementation MUST NOT automatically reactivate historical deactivated accounts.

#### Scenario: Bare usage 402 or 404
- **WHEN** usage refresh receives HTTP 402 or 404 without explicit terminal evidence
- **THEN** no terminal account status is written

#### Scenario: Explicit deactivation remains authoritative
- **WHEN** usage refresh receives a recognized deactivation code or message
- **THEN** the account is deactivated regardless of HTTP 402 or 404

#### Scenario: Revoked credentials stop polling
- **WHEN** usage refresh receives token_revoked
- **THEN** the account requires reauthentication without a forced refresh
- **AND** subsequent usage cycles skip that account

#### Scenario: Retry attempts exhausted
- **WHEN** the final usage response returns Retry-After of 60 seconds
- **THEN** the next background polling cycle skips the account before that deadline
- **AND** polling can resume after the deadline without a terminal account status write
