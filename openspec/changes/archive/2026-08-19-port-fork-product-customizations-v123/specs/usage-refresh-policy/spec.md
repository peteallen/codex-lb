## ADDED Requirements

### Requirement: Working-day weekly forecast

When Dashboard weekly pace working days are configured, the forecast MUST
consume quota only during those weekdays. Non-working-day wall-clock time
MUST not increase projected burn or shorten projected depletion time. An empty
working-day set MUST retain all-days behavior.

#### Scenario: Weekend forecast does not burn quota

- **GIVEN** working days are Monday through Friday
- **WHEN** a weekly forecast interval crosses Saturday or Sunday
- **THEN** forecast burn excludes those intervals
- **AND** depletion duration is expressed in wall-clock time including the skipped days
