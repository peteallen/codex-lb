## ADDED Requirements

### Requirement: Unknown absolute capacity does not exclude eligible accounts

Capacity-dependent routing MUST preserve known zero capacity as distinct from unknown capacity. When any eligible candidate's long-window capacity is unknown, capacity weighting and relative-availability selection MUST use remaining percentage on a consistent basis for the complete candidate pool. Sequential-drain ordering MUST likewise avoid comparing unknown capacity with invented free or legacy Pro allowances. Fully known candidate pools MUST retain existing absolute-capacity behavior. Model/tier eligibility, quota exhaustion, health cooldowns and ownership constraints MUST remain enforced.

#### Scenario: Pro Max competes in a mixed pool
- **GIVEN** an eligible promax account with unknown absolute capacity and remaining weekly quota
- **AND** another eligible account with known capacity
- **WHEN** capacity-weighted or relative-availability selection runs
- **THEN** the promax account has nonzero eligibility weight based on remaining percentage
- **AND** both accounts use the same percentage weighting basis

#### Scenario: Exhausted account is not rescued by unknown capacity
- **GIVEN** an account with unknown absolute capacity and a current upstream exhausted window
- **WHEN** an account is selected
- **THEN** the account remains unavailable until quota recovery is established

#### Scenario: Fully known pool retains absolute weighting
- **GIVEN** every eligible account has known capacity
- **WHEN** capacity-weighted selection runs
- **THEN** selection uses remaining absolute capacity as before

## MODIFIED Requirements

### Requirement: Relative availability routing

The proxy account selector SHALL support a `relative_availability` routing strategy. The strategy SHALL evaluate only accounts that have passed the existing eligibility, health-tier, model-plan, quota, cooldown, circuit-breaker, and budget-safety gates. Re-authentication-required accounts SHALL be treated as hard-blocked routing candidates, the same as paused and deactivated accounts. For each candidate in a pool with fully known capacities, it SHALL compute a raw score from remaining secondary-window credits divided by seconds until the secondary-window reset, using bounded fallbacks for unknown or near-immediate reset times, and SHALL select from the highest weighted candidates according to the configured power and top-K cutoff. Pools containing unknown capacities SHALL substitute remaining percentage for credits consistently across the candidate pool.

#### Scenario: Soon-resetting usable credits are preferred
- **GIVEN** two healthy eligible accounts with equal remaining secondary credits
- **AND** one account's secondary window resets sooner
- **WHEN** account selection uses `relative_availability`
- **THEN** the sooner-resetting account receives the higher relative-availability score

#### Scenario: Relative availability preserves canonical gates
- **GIVEN** one account is paused, reauth-required, deactivated, rate-limited, quota-exceeded, cooling down, or outside the requested model plan
- **WHEN** account selection uses `relative_availability`
- **THEN** that account is not selected by the relative-availability strategy

### Requirement: Sequential drain routing
The proxy account selector SHALL support a `sequential_drain` routing strategy. The strategy SHALL evaluate only accounts that pass the existing eligibility, model-plan, quota, cooldown, circuit-breaker, and budget-safety gates, then select the usable account with the lowest effective secondary capacity before moving to higher-capacity accounts when all capacities are known. Pools containing unknown capacities SHALL instead drain the most-used account by the common percentage basis.

#### Scenario: Lowest-capacity usable account is drained first
- **GIVEN** multiple healthy eligible accounts with different effective secondary capacities
- **WHEN** account selection uses `sequential_drain`
- **THEN** the account with the lowest effective secondary capacity is selected

#### Scenario: Exhausted lower-capacity accounts are skipped
- **GIVEN** the lowest-capacity account has no usable quota
- **WHEN** account selection uses `sequential_drain`
- **THEN** the selector chooses the next-lowest usable capacity account
