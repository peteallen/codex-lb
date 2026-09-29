# account-quota-presentation Specification

## Purpose
TBD - created by archiving change free-account-monthly-window. Update Purpose after archive.
## Requirements
### Requirement: Free-account quota surfaces are monthly-only

When an account's normalized quota model is monthly-only, account-facing quota surfaces SHALL present only the monthly window and MUST NOT render synthetic 5h or 7d bars for that account.

#### Scenario: Account surfaces show only monthly quota
- **WHEN** an account summary carries a normalized monthly quota window with no normalized 5h or 7d windows
- **THEN** the account card, account list row, and account detail usage panel show a single `Monthly` quota bar
- **AND** those surfaces do not render `5h` or `Weekly` bars for that account

### Requirement: Free-account overview quota hides 5h and 7d semantics

Overview and aggregate quota surfaces SHALL treat normalized monthly-only free-account quota as a 30d window and MUST NOT present that account as a weekly-only or dual-window account.

#### Scenario: Overview uses monthly semantics for free accounts
- **WHEN** overview data includes a free account with only a normalized monthly quota window
- **THEN** the overview account quota display shows only the 30d window for that account
- **AND** the account and API navigation progress logic uses monthly-only quota state for that account

### Requirement: Monthly quota remains visible in recent-trend displays

The account usage trend SHALL preserve the recent 7-day trend timeframe while identifying monthly-only quota lines as monthly quota.

#### Scenario: Monthly account trend labels the monthly line
- **WHEN** an account trend view renders a monthly-only free account
- **THEN** the trend legend identifies the quota line as `Monthly`
- **AND** the trend view still identifies itself as a 7-day trend

### Requirement: Account quota reflects the current window regime

Account cards, list rows and details MUST display the current applicable quota window and its reset. A historical monthly row superseded by a newer complete weekly observation MUST NOT replace the weekly percentage, duration or reset in account summaries.

#### Scenario: Exhausted weekly account does not show stale monthly availability
- **GIVEN** a rate-limited Pro account has historical monthly usage at zero percent and newer weekly usage at 100 percent
- **WHEN** the account list or dashboard is requested
- **THEN** the account exposes Weekly with zero percent remaining and the weekly reset
- **AND** monthly quota fields are absent
