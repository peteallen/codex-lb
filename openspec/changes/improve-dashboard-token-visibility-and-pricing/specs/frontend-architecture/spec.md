## ADDED Requirements

### Requirement: Usage readouts expose input and output token detail

The dashboard overview, conversation list, account request-usage summary, API-key usage summary, selected API-key usage responses, and API-key self-usage response SHALL expose input and output token counts alongside their existing total-token fields. Total tokens SHALL remain input tokens plus output tokens. Cached input tokens SHALL remain a subset of input tokens and SHALL NOT be added to the total a second time.

The dashboard SHALL render compact, explicitly labelled input and output token counts on usage-summary and usage-table readouts where those fields are available. Aggregate token charts, token-distribution donuts, token-limit controls, and authentication-token labels SHALL retain their existing semantics.

#### Scenario: Dashboard token card explains the aggregate total

- **GIVEN** the selected overview window has input, cached-input, and output token totals
- **WHEN** the dashboard summary cards render
- **THEN** the Tokens card keeps the aggregate total as its headline
- **AND** its supporting text labels the input, cached-input, and output counts separately

#### Scenario: Request and conversation rows show directional usage

- **GIVEN** a request or conversation has separate input and output token counts
- **WHEN** its dashboard table row renders
- **THEN** the token cell displays the aggregate total and labelled input and output detail
- **AND** cached input is identified separately when available

#### Scenario: Usage-management summaries show directional usage

- **GIVEN** account or API-key request usage has separate input and output totals
- **WHEN** the corresponding account, API-key, or selected-key summary renders
- **THEN** the summary labels input and output counts separately
- **AND** existing request, cached-input, cost, total-token chart, and distribution information remains available

#### Scenario: API-key self-usage exposes directional totals

- **WHEN** an authenticated API key requests `/v1/usage`
- **THEN** the response includes input and output token totals alongside total and cached-input tokens
- **AND** the response remains scoped to that authenticated key

#### Scenario: Token limits retain enforcement terminology

- **WHEN** an operator views or edits a total-token, input-token, or output-token limit
- **THEN** each limit keeps the label that matches its enforced counter
- **AND** the usage-presentation change does not reinterpret the limit

### Requirement: Dashboard range and refresh toolbar remains visible while scrolling

The dashboard toolbar containing the overview/conversation date selector and refresh button SHALL remain visible below the global application header while the page scrolls. It SHALL remain readable over dashboard content and SHALL adapt to narrow screens without obscuring the selector or refresh control. The page title SHALL remain normal document content so the sticky region stays compact during long investigations.

#### Scenario: Refresh remains reachable down the dashboard

- **WHEN** an operator scrolls below the initial dashboard viewport
- **THEN** the dashboard range and refresh header remains visible below the global app header
- **AND** the refresh button preserves its accessible label, disabled state, and loading indication

#### Scenario: Sticky controls fit a narrow viewport

- **WHEN** the dashboard is rendered below the small-screen breakpoint
- **THEN** the toolbar controls wrap into the available width
- **AND** the range selector and refresh button remain operable without horizontal page overflow
