## ADDED Requirements
### Requirement: Recurrent overload escalates across recovery probes
The proxy MUST retain account overload recurrence history for 15 minutes after the most recent explicit overload, independently of cooldown eligibility. Another overload within that window MUST escalate the cooldown through 30, 60, 120, 240, and at most 300 seconds. Cooldown expiry, selection, and intervening successes MUST NOT erase that recurrence history. After 15 minutes without an overload, the next overload MUST restart at 30 seconds. This history MUST remain runtime-only and MUST NOT change replay eligibility or persisted account status.

#### Scenario: A failed recovery probe extends the next hold
- **GIVEN** an account overloaded and its 30-second hold has expired
- **WHEN** its next request overloads within the recurrence window
- **THEN** the next hold lasts 60 seconds
- **AND** eligible independent traffic uses healthy alternatives during the hold

#### Scenario: Intermittent success preserves escalation
- **WHEN** an account succeeds after its hold expires but overloads again within 15 minutes of the last overload
- **THEN** the new hold escalates rather than restarting at 30 seconds

#### Scenario: Quiet recovery resets escalation
- **WHEN** no overload has occurred for at least 15 minutes
- **THEN** the next overload starts a 30-second hold

#### Scenario: Escalation stays bounded
- **WHEN** overloads continue recurring across expired holds
- **THEN** each new hold lasts at most 300 seconds and the retained count stays bounded
