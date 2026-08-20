## MODIFIED Requirements

### Requirement: Fork identity

The application document title, authenticated header brand, and password-login
brand MUST identify the deployment as `Codex LB (Pete's Fork)`. The Dashboard
status-bar repository link MUST target `https://github.com/peteallen/codex-lb`.

#### Scenario: Fork identity is visible before authentication

- **WHEN** the password login screen is rendered
- **THEN** its application title is `Codex LB (Pete's Fork)`

#### Scenario: Fork repository link is used

- **WHEN** an operator activates the status-bar GitHub link
- **THEN** the link targets the Pete Allen fork

### Requirement: Dashboard overview range

The Dashboard MUST retain `1d`, `7d`, and `30d` presets and MUST provide a
Custom range control with local calendar start and end dates. Future dates MUST
be disabled. A custom selection MUST refetch the overview with
`start_date`, `end_date`, and the browser `timezone`; selecting a preset MUST
remove the custom URL dates and request the preset timeframe.

#### Scenario: Default overview remains a preset

- **WHEN** the Dashboard URL has no overview range
- **THEN** the app requests `timeframe=7d`

#### Scenario: Custom overview uses explicit dates

- **WHEN** an operator selects a custom calendar range
- **THEN** the app requests the selected local dates and timezone
- **AND** the response timeframe is marked `custom`

#### Scenario: Future custom dates are unavailable

- **WHEN** an operator opens the custom range picker
- **THEN** dates later than the browser's current local day cannot be selected
