## MODIFIED Requirements

### Requirement: Dashboard omits pooled quota charts

The dashboard MUST NOT render the pooled 5-hour or weekly credit charts, their credit fractions, legends or safe-line ticks, regardless of whether absolute account capacities are known. It MUST NOT replace these panels with pooled or per-account percentage charts. Account cards, account list rows and account details MUST retain their existing quota information. The separate weekly credit pace card MAY remain when its existing eligibility rules permit it and the new weekly coverage payload is absent. When the weekly coverage payload is present, the dashboard SHALL render the coverage timeline defined in `weekly-coverage` instead of the legacy pace card; this timeline encodes projected availability in time, not pooled credit or percentage balances.

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
- **AND** an eligible legacy weekly credit pace card remains available when the new weekly coverage payload is absent

#### Scenario: Coverage replaces legacy pace presentation
- **WHEN** dashboard projections include weekly coverage data
- **THEN** the coverage component renders its availability or learning state and the legacy pace card is not rendered
