## MODIFIED Requirements

### Requirement: Dashboard page

The Dashboard page SHALL display summary metric cards for a selectable overview range, primary and secondary usage donut charts with legends, account status cards grid, and a recent requests table with filtering and pagination. The supported overview quick presets MUST be `1d`, `7d`, and `30d`. The Dashboard page SHALL also expose a Custom overview range picker that lets an operator select start and end calendar dates, keeps future dates disabled, and refetches `GET /api/dashboard/overview` with `start_date`, `end_date`, and `timezone` query parameters for the selected custom range.

#### Scenario: Dashboard defaults to the 7d overview preset

- **WHEN** the Dashboard page is rendered without a selected overview range
- **THEN** the app fetches `GET /api/dashboard/overview?timeframe=7d`
- **AND** the `7d` preset is visibly selected

#### Scenario: Dashboard overview preset changes only the overview query

- **WHEN** a user changes the dashboard overview range from one preset to another
- **THEN** the app refetches `GET /api/dashboard/overview` with the selected `timeframe`
- **AND** the request-log filters remain unchanged

#### Scenario: Dashboard custom overview range uses explicit dates

- **WHEN** a user selects a Custom dashboard overview range
- **THEN** the app refetches `GET /api/dashboard/overview` with `start_date`, `end_date`, and `timezone`
- **AND** the Custom range control is visibly selected

#### Scenario: Dashboard custom overview range disallows future dates

- **WHEN** a user opens the Custom dashboard overview range picker
- **THEN** the picker prevents selecting a date later than the browser's current local calendar date
