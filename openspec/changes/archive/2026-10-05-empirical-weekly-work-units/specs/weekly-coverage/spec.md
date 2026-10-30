## MODIFIED Requirements

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

### Requirement: Independent account projections during pool uncertainty

Fresh valid weekly observations SHALL produce per-account percentage pace and an exhaustion-before-reset or remaining-at-reset projection even when the pooled estimate is unavailable. The UI MUST distinguish these independent projections from a pooled simulation and disclose that transferred traffic can exhaust accounts sooner. Stale, elapsed, superseded or invalid quota data MUST NOT produce reassuring account projections.

#### Scenario: Missing token work does not hide measured quota pace
- **WHEN** an account has fresh quota observations but unknown relative capacity due to incomplete token records
- **THEN** its independent weekly projection is visible
- **AND** the UI explains why the pooled forecast remains uncertain
