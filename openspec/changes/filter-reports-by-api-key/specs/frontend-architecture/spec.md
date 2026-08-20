## ADDED Requirements

### Requirement: Reports API filters every aggregate by API key

`GET /api/reports` MUST accept zero or more repeatable `api_key_id` query parameters. When one or more IDs are supplied, the endpoint MUST include only request-log rows whose `api_key_id` matches any supplied ID in the current-period summary, previous-period summary, comparison eligibility, daily totals, daily median speed metrics, model distribution, account distribution, and user-agent distribution. The API-key predicate MUST be combined with the existing date, account, model, user-agent, and normal-traffic predicates. Omitting `api_key_id` MUST preserve the unfiltered all-traffic behavior.

#### Scenario: One selected API key scopes the complete report

- **WHEN** an authenticated operator requests `GET /api/reports` with one `api_key_id`
- **THEN** every returned aggregate and comparison value is computed only from rows attributed to that API key
- **AND** rows for other API keys or for unauthenticated traffic are excluded

#### Scenario: Multiple selected API keys form a union

- **WHEN** an authenticated operator supplies more than one `api_key_id`
- **THEN** every returned aggregate includes rows attributed to any selected ID
- **AND** all other report predicates remain in effect

#### Scenario: Omitted API-key filter preserves existing behavior

- **WHEN** an authenticated operator requests `GET /api/reports` without `api_key_id`
- **THEN** the endpoint includes traffic regardless of API-key attribution subject to its existing filters

## MODIFIED Requirements

### Requirement: Reports page renders English user-facing labels

The dashboard SHALL render `/reports` with the following exact page-owned user-facing labels for the current reports surface:

- `Cost Report`
- `Usage history by date range`
- `Loading...`
- `Total Cost`
- `Requests`
- `Cost by Day`
- `Tokens by Day`
- `Distribution by Model`
- `Distribution by UserAgent`
- `Daily Breakdown`
- `Day`
- `Input Tokens`
- `Output Tokens`
- `Cost`
- `Accounts`
- `API Keys`
- `Total`
- `Failed to load report data:`
- `Failed to load model and user-agent options:`
- `Failed to load account options:`
- `Failed to load API key options:`
- `Some report data could not be loaded. Try reloading.`
- `Retry`

Backend-provided strings, account values, API-key values, model values, and raw server error payload text SHALL remain out of scope for this wording change unless `/reports` renders page-owned labels around them.

#### Scenario: Reports page shows English labels

- **WHEN** an authenticated operator opens `/reports`
- **THEN** the page title is `Cost Report`
- **AND** the subtitle is `Usage history by date range`
- **AND** the summary cards include `Total Cost` and `Requests`
- **AND** the filter controls include `Accounts` and `API Keys`
- **AND** the chart and table section titles include `Cost by Day`, `Tokens by Day`, `Distribution by Model`, `Distribution by UserAgent`, and `Daily Breakdown`
- **AND** the daily table headings include `Day`, `Input Tokens`, `Output Tokens`, `Cost`, and `Accounts`

#### Scenario: Reports page state labels are English

- **WHEN** `/reports` renders a loading, empty, or error state
- **THEN** the loading label is `Loading...`
- **AND** page-owned error wrappers use `Failed to load report data:`, `Failed to load model and user-agent options:`, `Failed to load account options:`, and `Failed to load API key options:` when those failures render
- **AND** the retry warning is `Some report data could not be loaded. Try reloading.`
- **AND** the retry button label is `Retry`

### Requirement: Reports page exposes visible filter controls

The `/reports` page SHALL expose visible filter controls for `7d`, `30d`, and `90d` quick presets, start date, end date, account, API key, and model. The API-key control MUST allow zero or more selections, MUST use stable API-key IDs for requests, and MUST display the key name and available prefix. An empty API-key selection MUST mean all traffic. A selected ID that disappears from the current option catalog MUST remain visibly removable and MUST remain applied for the current page session rather than being silently cleared. When an authenticated operator clicks one of the quick presets, the page SHALL visibly highlight that preset. When the operator manually edits the start date or end date afterward, the page SHALL clear the quick-preset highlight until another quick preset is clicked. The start and end date inputs SHALL disallow selecting dates later than the browser's current local calendar date.

#### Scenario: Reports page shows report filter controls

- **WHEN** an authenticated operator opens `/reports`
- **THEN** the page exposes visible filter controls for `7d`, `30d`, and `90d` quick presets, start date, end date, account, API key, and model

#### Scenario: API-key selection refetches the report

- **WHEN** an authenticated operator selects one or more API keys on `/reports`
- **THEN** the page refetches `GET /api/reports` with each selected stable ID as a repeatable `api_key_id`
- **AND** clearing every selected API key removes the API-key predicate

#### Scenario: Deleted selected key is not silently cleared

- **GIVEN** an API-key ID is selected on `/reports`
- **WHEN** that ID is absent from the current API-key option catalog
- **THEN** the control keeps the selected ID visible as a removable stale value
- **AND** report requests continue to include that ID until the operator removes it

#### Scenario: Quick preset highlight follows the selected preset

- **WHEN** an authenticated operator clicks the `30d` quick preset on `/reports`
- **THEN** the page visibly highlights the `30d` preset
- **AND** the page updates the start and end dates to the `30d` preset range

#### Scenario: Quick preset highlight clears after manual date edits

- **WHEN** an authenticated operator clicks a quick preset on `/reports`
- **AND** then manually edits the start date or end date afterward
- **THEN** the page clears the quick-preset highlight
- **AND** the page keeps the edited date range values

#### Scenario: Report date inputs disallow future dates

- **WHEN** an authenticated operator opens `/reports`
- **THEN** the start date and end date inputs prevent selecting a date later than the browser's current local calendar date
