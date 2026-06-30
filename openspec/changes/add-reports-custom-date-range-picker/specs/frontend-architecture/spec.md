## MODIFIED Requirements

### Requirement: Reports page exposes visible filter controls

The `/reports` page SHALL expose visible filter controls for `1d`, `7d`, and `30d` quick presets, a Custom range picker, account, model, and user-agent. When an authenticated operator clicks one of the quick presets, the page SHALL visibly highlight that preset. When the operator changes the Custom range start or end date afterward, the page SHALL clear the quick-preset highlight until another quick preset is clicked. The Custom range picker SHALL keep the selected start and end date visible, SHALL update the same `startDate` and `endDate` report filter values used by `GET /api/reports`, and SHALL prevent selecting dates later than the browser's current local calendar date.

#### Scenario: Reports page shows quick presets and custom range controls

- **WHEN** an authenticated operator opens `/reports`
- **THEN** the page exposes visible filter controls for `1d`, `7d`, and `30d` quick presets, Custom range, account, model, and user-agent

#### Scenario: Quick preset highlight follows the selected preset

- **WHEN** an authenticated operator clicks the `30d` quick preset on `/reports`
- **THEN** the page visibly highlights the `30d` preset
- **AND** the page updates the start and end dates to the `30d` preset range

#### Scenario: Custom range clears the quick preset highlight

- **WHEN** an authenticated operator clicks a quick preset on `/reports`
- **AND** then changes the Custom range start or end date
- **THEN** the page clears the quick-preset highlight
- **AND** the page keeps the edited date range values

#### Scenario: Custom range disallows future dates

- **WHEN** an authenticated operator opens the Custom range picker on `/reports`
- **THEN** the picker prevents selecting a date later than the browser's current local calendar date
