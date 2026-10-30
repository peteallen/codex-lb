## ADDED Requirements

### Requirement: Request history preserves individual log entries across refreshes

The request-log listing API MUST return a stable, unique string `logId` for each persisted log entry. The dashboard MUST render each returned entry exactly once and in API order across polling, filtering, and pagination updates, including entries sharing a request ID, account ID, or timestamp. Request IDs MUST remain available for correlating attempts.

#### Scenario: Retry attempts share a request ID

- **GIVEN** multiple persisted attempts share one request ID
- **WHEN** the API lists those attempts and the dashboard refreshes
- **THEN** each attempt has a distinct, stable `logId`
- **AND** the dashboard displays each returned attempt once in API order

#### Scenario: Log entries share all correlation fields

- **GIVEN** two persisted entries share a request ID, account ID, and timestamp
- **WHEN** those entries are listed repeatedly
- **THEN** their `logId` values remain distinct and unchanged

#### Scenario: Refreshed or paginated results remove previous attempts

- **GIVEN** the dashboard displays multiple attempts with shared request IDs
- **WHEN** the next result set replaces or removes some attempts
- **THEN** the table contains exactly the next result set in API order
- **AND** removed attempts do not remain visible
