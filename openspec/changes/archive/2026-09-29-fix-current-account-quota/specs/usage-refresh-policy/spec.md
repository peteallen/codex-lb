## ADDED Requirements

### Requirement: Current monthly quota excludes superseded observations

Account presentation, usage summaries, ordinary routing, operator probe settlement and background recovery MUST ignore a monthly usage observation when a primary or secondary observation for the same account has an observed percentage, positive window duration, reset deadline and a recorded timestamp more than the same-fetch margin later. The system MUST preserve the stored historical records. Missing timestamps, absent windows, no-data markers and incomplete observations MUST NOT supersede monthly quota. Applicable current monthly-only Pro-family quota MUST remain supported. Existing persisted cooldown and quota-recovery rules MUST remain enforced.

#### Scenario: Weekly usage supersedes historical monthly data
- **GIVEN** a Pro account has an older monthly row at zero percent used
- **WHEN** a later complete weekly observation reports 100 percent used
- **THEN** current quota consumers use the exhausted weekly window
- **AND** the old monthly row cannot conceal exhaustion

#### Scenario: Current monthly quota remains authoritative
- **WHEN** a Pro account has a newer monthly observation than its old weekly observation
- **THEN** the account continues to use monthly quota

#### Scenario: Incomplete sibling cannot replace monthly quota
- **WHEN** a newer sibling lacks a percentage, duration, reset deadline or timestamp, or is a no-data marker
- **THEN** monthly quota remains applicable

#### Scenario: Same-fetch siblings do not supersede monthly quota
- **WHEN** sibling timestamps differ by at most the existing same-fetch margin
- **THEN** the monthly observation is not discarded by timestamp ordering

### Requirement: Operator probe uses supported upstream fields

Force Probe MUST omit fields unsupported by the Codex upstream Responses endpoint, including max_output_tokens. It MUST retain a minimal single-dot request, existing timeout, immediate usage refresh and upstream HTTP status reporting. An upstream rejection by itself MUST NOT clear persisted rate limits.

#### Scenario: Probe reaches the upstream quota check
- **WHEN** the operator probes an exhausted account
- **THEN** the outgoing request omits max_output_tokens
- **AND** an upstream 429 is returned in the probe result without clearing the account's block
