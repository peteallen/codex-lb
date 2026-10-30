## ADDED Requirements

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
