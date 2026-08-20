## ADDED Requirements

### Requirement: Fork identity

The application MUST identify the deployment as `Codex LB (Pete's Fork)` in the
document title, authenticated header brand, and password-login brand. The Dashboard
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
remove the custom URL dates and request the preset timeframe. Custom-range
labels and accessibility text MUST use the application's supported locale
catalogs. A temporarily incomplete or inverted date-input draft MUST remain
editable without replacing the last valid range or collapsing the control to a
preset. Daily and weekly trend buckets MUST align to local calendar boundaries,
including daylight-saving transitions.

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

#### Scenario: Operator edits the start date before the end date

- **GIVEN** a valid custom range whose current end precedes the intended new start
- **WHEN** the operator enters the new start and then a later valid end
- **THEN** the start draft remains visible between the two edits
- **AND** the Dashboard requests the completed new range only after it is valid

#### Scenario: Local days remain single trend buckets across DST

- **GIVEN** a custom range in a non-UTC time zone that crosses a daylight-saving transition
- **WHEN** the Dashboard renders daily trends
- **THEN** each selected local calendar date produces exactly one trend bucket
