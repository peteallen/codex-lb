## REMOVED Requirements

### Requirement: Dashboard usage donuts present credits as stacked remaining and capacity

**Reason**: The operator requested removal of both pooled quota chart panels.
**Migration**: Use existing account quota information in the accounts section.

## ADDED Requirements

### Requirement: Dashboard omits pooled quota charts

The dashboard MUST NOT render the pooled 5-hour or weekly credit charts, their credit fractions, legends or safe-line ticks, regardless of whether absolute account capacities are known. It MUST NOT replace these panels with pooled or per-account percentage charts. Account cards, account list rows and account details MUST retain their existing quota information. The separate weekly credit pace card MAY remain when its existing eligibility rules permit it.

#### Scenario: Mixed-capacity accounts do not render quota charts

- **WHEN** the dashboard receives accounts with a mixture of known and unknown absolute credit capacities
- **THEN** neither the 5-hour nor weekly pooled chart appears
- **AND** account quota information remains available in the accounts section

#### Scenario: Known capacities do not restore the removed panels

- **WHEN** every account has complete absolute credit data
- **THEN** neither `5-Hour Credits` nor `Weekly Credits` pooled chart is rendered

#### Scenario: Other dashboard content is preserved

- **WHEN** the dashboard overview loads
- **THEN** summary cards, the accounts section and recent request logs remain available
- **AND** an eligible weekly credit pace card remains available without an empty quota-chart column

## MODIFIED Requirements

### Requirement: Dashboard projections load after the primary dashboard data

The dashboard SPA SHALL render primary dashboard content from `GET /api/dashboard/overview`
and recent request-log data without waiting for depletion or weekly-credit projection
calculations. Projection-only data, including safe-line depletion markers and weekly-credit
pace, SHALL be available from `GET /api/dashboard/projections` and fetched after overview
data is available.

#### Scenario: Main dashboard renders before projections finish

- **GIVEN** an authenticated operator opens the dashboard
- **WHEN** `GET /api/dashboard/overview` and request-log calls complete before `GET /api/dashboard/projections`
- **THEN** the dashboard renders the primary cards, account list, and request-log surface
- **AND** projection-only safe-line and weekly-credit fields may populate later when the projections response arrives

#### Scenario: Projection endpoint exposes heavy dashboard calculations

- **WHEN** the dashboard client requests `GET /api/dashboard/projections`
- **THEN** the response includes depletion safe-line data and weekly-credit pace data when those calculations are available
- **AND** the overview endpoint does not need to compute those fields for initial page render
