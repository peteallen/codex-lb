# Weekly coverage

## Purpose

Forecast interruptions in included weekly quota across eligible accounts with staggered resets and visible evidence limitations.

## Requirements

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

Capacity estimates SHALL be derived per account from measured quota drawdown and comparable observed work, using locally normalized input plus output tokens, without adding cached or cache-write input again. Model prices, model names, context pricing and service-tier names MUST NOT be prerequisites for measuring work. The forecast SHALL disclose that effective capacity depends on the observed workload mix continuing. The system MUST distinguish relative work units from provider credits. It MUST require meaningful evidence and reject reset-crossing, materially regressing, censored or inconsistent calibration intervals. Demand SHALL use each account's current weekly-window average, not a silent recent-activity substitution.

#### Scenario: Equal work consumes different percentages
- **WHEN** comparable observed work repeatedly consumes twice as many percentage points on one account
- **THEN** the estimated effective allowance reflects the observed difference rather than assuming equal account capacity

#### Scenario: Insufficient calibration remains learning
- **WHEN** an account has only tiny quota movements or too few usable observations
- **THEN** the forecast reports learning rather than a fabricated capacity or zero-demand safe result

#### Scenario: Counter reset is not negative consumption
- **WHEN** the used percentage decreases meaningfully, or a material percentage drop coincides with a coherent reset-horizon jump
- **THEN** the estimator does not fit a capacity interval across that boundary
- **AND** a reset-horizon movement without a quota drop is treated as timestamp drift rather than an automatic boundary

#### Scenario: Five million tokens consume five percentage points
- **WHEN** a complete interval records five million input plus output tokens and five percentage points of drawdown
- **THEN** its estimated full-window capacity is one hundred million tokens in local work units
- **AND** readiness still requires sufficient stable independent evidence

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

The implementation SHALL include a reproducible read-only historical validation path that separates calibration data from later validation data. It SHALL report sample coverage and held-out error or state why validation is unavailable. Dashboard work reads SHALL aggregate no more than fourteen days of account-scoped raw requests in SQL, retain token totals and completeness evidence, and MUST NOT add overlapping rollup work. Historical account credentials and identities MUST NOT appear in committed validation reports.

#### Scenario: Rollup boundary does not double count work
- **WHEN** retained hourly rollups and raw logs both cover the lookback
- **THEN** the raw records with required evidence contribute exactly once
- **AND** folding those same records does not change forecast work or completeness

#### Scenario: Validation uses future observations only for scoring
- **WHEN** a historical prediction is evaluated
- **THEN** its capacity and demand estimates use only observations at or before the prediction time

### Requirement: Recoverable calibration evidence

The estimator SHALL reject incomplete intervals individually and SHALL permit sufficient stable, complete intervals to establish capacity despite earlier discarded intervals. Request failure, a missing stored price, an unknown model or an unknown service tier MUST NOT alone invalidate complete token accounting. Missing or invalid token measurements MUST remain explicit uncertainty.

#### Scenario: Clean traffic recovers calibration
- **WHEN** an account has sufficient stable clean calibration intervals and a separate incomplete interval
- **THEN** the incomplete interval is excluded without permanently preventing calibration
- **AND** the evidence limitation remains visible

#### Scenario: Unknown model still establishes capacity
- **WHEN** traffic from an unlisted model has complete token measurements and sufficient stable quota intervals
- **THEN** it contributes to account capacity and the pooled forecast without a model-pricing lookup

### Requirement: Work accounting independent of aggregation

One work unit SHALL equal one million measured input plus output tokens; when output is absent, measured reasoning tokens SHALL supply the output value. Cached input and cache-write tokens MUST NOT be counted twice. Summing requests or moving them across an hourly fold boundary MUST NOT change work or accounting completeness. Retained aggregates lacking required evidence MUST NOT be treated as equivalent complete evidence.

#### Scenario: Aggregation preserves measured work
- **WHEN** requests with different models, tiers, context sizes and cached fractions are aggregated
- **THEN** their combined work equals the sum of their individual work

#### Scenario: Fold does not manufacture complete usage
- **WHEN** zero-token or otherwise incomplete requests are folded
- **THEN** the forecast does not become more confident solely because of folding

### Requirement: Compatible capacity evidence across resets

The estimator SHALL reuse recent complete capacity observations across an ordinary scheduled weekly reset only when current-window evidence corroborates the capacity scale. It MUST NOT fit intervals across resets or silently reuse incompatible or uncorroborated capacity after a changed allowance regime. Demand MUST remain based on the current window.

#### Scenario: Normal reset with matching capacity evidence
- **WHEN** current-window evidence agrees with recent pre-reset calibration
- **THEN** those separate observations contribute to a rolling capacity estimate
- **AND** the current remaining allowance and demand use the new weekly window

### Requirement: Independent account projections during pool uncertainty

Fresh valid weekly observations SHALL produce per-account percentage pace and an exhaustion-before-reset or remaining-at-reset projection even when the pooled estimate is unavailable. The UI MUST distinguish these independent projections from a pooled simulation and disclose that transferred traffic can exhaust accounts sooner. Stale, elapsed, superseded or invalid quota data MUST NOT produce reassuring account projections.

#### Scenario: Missing token work does not hide measured quota pace
- **WHEN** an account has fresh quota observations but unknown relative capacity due to incomplete token records
- **THEN** its independent weekly projection is visible
- **AND** the UI explains why the pooled forecast remains uncertain

### Requirement: Current quota and routing configuration govern coverage

A newer incompatible nonweekly quota observation SHALL supersede historical weekly evidence. Single-account mode without a valid selected account MUST NOT simulate a usable pool.

#### Scenario: Monthly quota supersedes calibrated weekly history
- **WHEN** a newer monthly observation supersedes a calibrated weekly stream
- **THEN** the historical weekly allowance is not presented as available coverage

#### Scenario: Single account selection is absent
- **WHEN** single-account routing is enabled without a valid selection
- **THEN** no ready available pool is returned

### Requirement: Compact visual coverage overview

The default coverage card SHALL use one shared time axis, one compact pool row and one compact row per included account. Available quota, exhausted time and reset markers SHALL be visually distinct and have accessible descriptions. A single closed-by-default disclosure SHALL contain account evidence, excluded accounts with their reasons, and detailed limitations. The card MUST NOT repeat legends, status badges, reset dates or warning panels for every account. Five included accounts MUST fit in a card no taller than 400 CSS pixels at desktop width with details closed.

#### Scenario: Incomplete pool still has a useful compact overview
- **WHEN** the pool estimate is unavailable but individual account projections are usable
- **THEN** the pool row indicates uncertainty and individual rows show available and exhausted time only until their current reset
- **AND** the overview states that individual pace does not include transferred traffic
- **AND** time after each reset remains visually unknown

#### Scenario: Stale and excluded accounts do not imply coverage
- **WHEN** an account projection is unavailable or the account is excluded
- **THEN** an unavailable account has no projected available segment
- **AND** excluded accounts appear only in the details disclosure with their reasons

#### Scenario: Evidence remains accessible on demand
- **WHEN** the user opens Details using a pointer or keyboard
- **THEN** full account names, reset timing, projection explanations, calibration evidence, exclusions and limitations are available
