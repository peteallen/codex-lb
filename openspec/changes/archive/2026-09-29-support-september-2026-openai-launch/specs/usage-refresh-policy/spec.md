## MODIFIED Requirements

### Requirement: Usage capacity recognizes upstream ChatGPT plan types

The system MUST recognize pro, prolite and promax account plans while preserving raw plan identity for display and logs. Absolute capacity for these Pro-family plans MUST remain unknown until authoritative entitlement data establishes it; legacy plan constants and monthly subscription prices MUST NOT be interpreted as current included allowances. Per-account and aggregate credit quantities MUST be null when required capacity is unknown, while reported usage percentages and resets MUST remain available. Aggregates with incomplete capacities MUST use a consistent percentage basis rather than omit unknown-capacity accounts or report a partial sum as the whole pool.

#### Scenario: Pro Max remains visible without an invented allowance
- **GIVEN** an active promax account with a reported weekly window at 25 percent
- **WHEN** usage is returned
- **THEN** its weekly usage is 25 percent with the reported reset time
- **AND** absolute capacity and remaining credits are null

#### Scenario: Grandfathered Pro has no guessed credit conversion
- **WHEN** two pro accounts have different included allowances but the usage source does not expose their absolute capacities
- **THEN** each retains its own upstream percentage and reset
- **AND** neither is assigned a guessed legacy absolute allowance

### Requirement: Pro Lite accounts are eligible for Pro-gated models

The system MUST treat stored prolite and promax account plan types as Pro-equivalent for general model plan eligibility, while preserving the stored plan value. This equivalence MUST NOT grant a service tier absent from authoritative account/catalog entitlement evidence.

#### Scenario: Pro-family account can select a generally Pro-gated model
- **GIVEN** an eligible prolite or promax account
- **AND** the model registry permits pro for a model
- **WHEN** general plan eligibility is checked
- **THEN** the account passes that check

#### Scenario: Generic Pro does not acquire Ultrafast entitlement
- **GIVEN** an account whose catalog does not advertise Astra Ultrafast
- **WHEN** an Ultrafast request is routed
- **THEN** general Pro-family equivalence does not add the account to the eligible Ultrafast pool

## ADDED Requirements

### Requirement: Reported windows do not depend on absolute capacity

The system MUST retain weekly-only and monthly-only reported windows, including percentages and reset times, independently of whether absolute capacity is known. A newer complete successful usage refresh that omits a prior short window MUST supersede that window's derived usage, reset and duration. Missing rate-limit objects, errors and incomplete observations MUST NOT clear quota evidence. Persisted account cooldown and health constraints MUST remain enforced.

#### Scenario: Weekly-only refresh supersedes five-hour exhaustion
- **GIVEN** a stale five-hour sample at 100 percent
- **WHEN** a newer complete usage refresh reports an available weekly window and no short window
- **THEN** subsequent selection and usage presentation no longer treat the obsolete short sample as exhausted
- **AND** a separate persisted upstream cooldown remains enforced

#### Scenario: Monthly-only Pro usage remains visible
- **WHEN** a Pro-family account reports only a monthly window
- **THEN** the window's percentage and reset remain represented even though capacity is unknown

### Requirement: Credit forecasts require known pool capacity

Weekly credit forecasts MUST be unavailable when an otherwise eligible weekly account has unknown absolute capacity. The system MUST NOT present a partial known-capacity forecast as the complete pool or convert projected shortfalls into a count of Pro subscriptions using legacy allowances. Reported usage percentages MUST remain available independently of the credit forecast.

#### Scenario: Mixed Pro and Plus pool has no guessed forecast
- **GIVEN** eligible Pro and Plus accounts with reported weekly usage
- **AND** the Pro account has unknown absolute capacity
- **WHEN** the dashboard builds weekly credit pace
- **THEN** the credit forecast is unavailable
- **AND** it does not recommend a guessed number of Pro subscriptions
