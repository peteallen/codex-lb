## ADDED Requirements

### Requirement: Probe notifications report the upstream outcome

The account Force Probe UI MUST show a success notification only when the returned upstream probe status is HTTP 2xx. Other HTTP statuses MUST produce an error notification containing that status; a network-failure sentinel MUST produce a connection-failure notification. Quota queries MUST be invalidated after every completed probe response, including upstream rejection.

#### Scenario: Upstream rejection is visible
- **WHEN** the local probe API succeeds but reports upstream HTTP 400 or 429
- **THEN** the UI displays the upstream failure status instead of a success toast
- **AND** it refreshes account and dashboard queries

#### Scenario: Successful probe is reported accurately
- **WHEN** the probe reports upstream HTTP 200
- **THEN** the UI shows its success notification and refreshes quota data

#### Scenario: Network failure is visible
- **WHEN** the probe returns the network-failure status sentinel
- **THEN** the UI displays a connection failure instead of a success notification
