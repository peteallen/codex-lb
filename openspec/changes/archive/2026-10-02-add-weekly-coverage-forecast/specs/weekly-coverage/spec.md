## ADDED Requirements

### Requirement: Weekly forecast eligibility and completeness

The system SHALL forecast included weekly quota for enabled Pro-family accounts with an upstream seven-day window. It SHALL exclude paused, reauthentication-required, deactivated and non-Pro accounts, expose exclusion reasons, and retain weekly-exhausted accounts and their scheduled resets. Missing, stale, elapsed or invalid weekly observations for otherwise eligible accounts MUST prevent a reassuring complete-pool forecast.

#### Scenario: Disabled account does not contribute capacity
- **WHEN** an account is paused, requires reauthentication, is deactivated or is not Pro-family
- **THEN** it contributes neither capacity nor demand and its exclusion reason is visible

#### Scenario: Exhausted account returns at reset
- **WHEN** an enabled account is weekly-exhausted with a future reported reset
- **THEN** it remains in the pool with zero remaining allowance and replenishes at that reset

#### Scenario: Missing evidence does not mean covered
- **WHEN** an otherwise eligible account has stale, missing or incomplete evidence
- **THEN** the whole-pool result is learning or limited, with no assertion of uninterrupted coverage

### Requirement: Empirical account capacity and current-window demand

Capacity estimates SHALL be derived per account from measured quota drawdown and comparable observed work, accounting for supported model, speed, input, output and cached-token differences. The system MUST distinguish relative work units from provider credits. It MUST require meaningful evidence and reject reset-crossing, materially regressing, censored or inconsistent calibration intervals. Demand SHALL use each account's current weekly-window average, not a silent recent-activity substitution.

#### Scenario: Equal work consumes different percentages
- **WHEN** comparable observed work repeatedly consumes twice as many percentage points on one account
- **THEN** the estimated effective allowance reflects the observed difference rather than assuming equal account capacity

#### Scenario: Insufficient calibration remains learning
- **WHEN** an account has only tiny quota movements or too few usable observations
- **THEN** the forecast reports learning rather than a fabricated capacity or zero-demand safe result

#### Scenario: Counter reset is not negative consumption
- **WHEN** the reset timestamp changes by at least six hours or the used percentage decreases by at least half a percentage point
- **THEN** the estimator does not fit a capacity interval across that boundary

### Requirement: Continuous demand through staggered resets

The forecast SHALL simulate fourteen days with account-specific reset events. Total modeled demand MUST continue when an account empties and SHALL be allocated among remaining eligible accounts under the disclosed routing approximation. Reset events MUST replace an account's balance with its full estimated allowance and MUST NOT accumulate unused allowance. The result SHALL expose all modeled interruption intervals, account availability intervals and the minimum reserve where calculable. Missing capacity or unsupported allocation MUST NOT be presented as a complete safe forecast.

#### Scenario: Exhaustion transfers work
- **WHEN** one account empties while another can serve demand
- **THEN** the second account absorbs that work and pool demand does not decrease

#### Scenario: Gap ends at replenishment
- **WHEN** all accounts empty before the next scheduled reset
- **THEN** the result records a gap beginning at exhaustion and ending when quota returns

#### Scenario: Reset discards unused balance
- **WHEN** an account resets with unused quota
- **THEN** its new balance equals its estimated full allowance, not full allowance plus unused quota

### Requirement: Coverage presentation and scope

The dashboard SHALL show a weekly coverage headline, a seven-day timeline with a fourteen-day option, expandable account evidence, exclusion reasons and forecast limitations. It SHALL distinguish learning, limited evidence, no eligible accounts, predicted interruption and no predicted interruption within the stated horizon. It MUST exclude purchased/promotional credits, optional early resets and five-hour limits from this forecast and MUST NOT change routing decisions. Minimum reserve SHALL be expressed in time at forecast demand when meaningful.

#### Scenario: Gap outside default viewport
- **WHEN** the first projected interruption lies between seven and fourteen days away
- **THEN** the headline identifies it and the fourteen-day option reveals its timeline interval

#### Scenario: User can understand learning state
- **WHEN** capacity calibration is incomplete
- **THEN** the UI explains that it is learning usage and provides the affected account reasons without drawing a falsely covered pool

### Requirement: Historical validation and bounded reads

The implementation SHALL include a reproducible read-only historical validation path that separates calibration data from later validation data. It SHALL report sample coverage and held-out error or state why validation is unavailable. Dashboard reads SHALL be bounded and MUST avoid overlap between retained rollups and raw request history. Historical account credentials and identities MUST NOT appear in committed validation reports.

#### Scenario: Rollup boundary does not double count work
- **WHEN** retained hourly rollups and newer raw logs both cover the lookback
- **THEN** only rolled-up work before the fold watermark and raw work at or after it contribute

#### Scenario: Validation uses future observations only for scoring
- **WHEN** a historical prediction is evaluated
- **THEN** its capacity and demand estimates use only observations at or before the prediction time
