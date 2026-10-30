## ADDED Requirements

### Requirement: Account quota reflects the current window regime

Account cards, list rows and details MUST display the current applicable quota window and its reset. A historical monthly row superseded by a newer complete weekly observation MUST NOT replace the weekly percentage, duration or reset in account summaries.

#### Scenario: Exhausted weekly account does not show stale monthly availability
- **GIVEN** a rate-limited Pro account has historical monthly usage at zero percent and newer weekly usage at 100 percent
- **WHEN** the account list or dashboard is requested
- **THEN** the account exposes Weekly with zero percent remaining and the weekly reset
- **AND** monthly quota fields are absent
