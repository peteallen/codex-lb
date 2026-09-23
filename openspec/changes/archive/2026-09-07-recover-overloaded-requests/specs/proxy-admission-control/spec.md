## ADDED Requirements

### Requirement: Explicit upstream overload has a success-resistant cooldown

An explicit upstream overload MUST place its account in a bounded temporary cooldown before subsequent eligible selection. A concurrent success MUST NOT erase an active overload cooldown. Soft affinity and backoff fallback MUST NOT select an account during that cooldown when it is ineligible. After expiry, the account MUST be eligible for normal recovery selection without manual intervention. Local admission errors and account-neutral invalid requests MUST NOT trigger this upstream overload cooldown.

#### Scenario: Intermittent success does not erase an overload
- **WHEN** an account records an explicit upstream overload followed by a successful concurrent request
- **THEN** its active overload cooldown remains in effect
- **AND** new eligible work selects another healthy account

#### Scenario: Cooling accounts are queued instead of forced into service
- **WHEN** all otherwise eligible accounts are within overload cooldown
- **THEN** the recovering request waits within its deadline
- **AND** generic backoff fallback does not bypass that cooldown

#### Scenario: Recovery after cooldown expiry
- **WHEN** an account's overload cooldown expires
- **THEN** normal selection can probe that account with new work
- **AND** another overload starts a bounded cooldown again

#### Scenario: Local saturation is not an upstream account failure
- **WHEN** a request encounters local admission capacity or an account-neutral invalid input error
- **THEN** it does not place the account into upstream overload cooldown
