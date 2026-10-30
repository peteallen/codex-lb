## ADDED Requirements

### Requirement: September GPT-6 models have complete API cost estimates

The pricing registry MUST recognize gpt-6.1-sol, gpt-6-sol, and gpt-6-luna and dated snapshots of those exact model families. Standard short-context input/cached-input/output USD rates per million tokens MUST be 2/0.10/10, 2/0.20/10, and 0.10/0.01/0.50 respectively. Cache writes MUST cost 1.25 times ordinary input. Above 272000 input tokens, input/cache rates MUST double and output rates MUST multiply by 1.5 for the full request. Fast/priority MUST cost twice Standard; Flex MUST cost half Standard. Reservation, settlement and request-log estimates MUST use the same rates.

#### Scenario: New Sol model settles a real cost
- **WHEN** an API-key request for gpt-6.1-sol completes with 100000 uncached input and 10000 output tokens at Standard
- **THEN** its cost usage and request estimate are 0.30 USD
- **AND** its final quota usage is not zero or the temporary reservation amount

#### Scenario: Cache discount belongs to the exact model
- **WHEN** 100000 cached input tokens are priced for gpt-6.1-sol and gpt-6-sol at Standard short context
- **THEN** the cached costs are 0.01 USD and 0.02 USD respectively

### Requirement: Astra Ultrafast has explicit API rates

The calculator MUST price gpt-6-astra Ultrafast at 60/6/300 USD per million short-context input/cached-input/output tokens and 120/12/450 for long context above 272000 input tokens. Cache writes MUST cost 1.25 times the applicable input rate. Upstream-reported billable tiers MUST take precedence over requested tiers. These API rates MUST NOT use the subscription usage multiplier.

#### Scenario: Ultrafast output does not use Standard price
- **WHEN** Astra returns one million output tokens with actual service tier ultrafast and short input
- **THEN** output cost is 300 USD
- **AND** request-log and API-key settlement use the same cost

#### Scenario: Actual Standard response overrides requested Ultrafast
- **WHEN** a request asks for ultrafast but the response reports default
- **THEN** the calculator uses Standard rates

## MODIFIED Requirements

### Requirement: API keys can enforce a service tier

The dashboard API key CRUD surface MUST allow callers to persist an optional enforced service tier including ultrafast. The service MUST normalize fast to the canonical upstream value priority before persistence and before returning the API key payload. Enforced ultrafast MUST be forwarded unchanged and MUST remain subject to model/account service-tier eligibility without silent downgrade.

#### Scenario: Create API key with fast service tier alias
- **WHEN** a dashboard client creates an API key with enforcedServiceTier fast
- **THEN** the request is accepted
- **AND** persistence and response use priority

#### Scenario: Update API key with canonical service tier
- **WHEN** a dashboard client updates an API key with enforcedServiceTier flex
- **THEN** persistence and subsequent reads return flex

#### Scenario: Ultrafast survives dashboard round trips
- **WHEN** a client creates or updates a key with enforcedServiceTier ultrafast
- **THEN** create, list and update responses preserve ultrafast
- **AND** the dashboard can select and display Ultrafast

### Requirement: API key list includes pooled credit data

The `GET /api/api-keys/` list endpoint SHALL include pooled usage across the selectable accounts assigned to each key. Unscoped keys SHALL pool all selectable accounts; an enabled assignment scope with no remaining accounts SHALL remain empty. Paused, deactivated and reauthentication-required accounts SHALL be excluded.

The response SHALL include nullable `pooled_remaining_percent_primary`, `pooled_remaining_percent_secondary`, `pooled_remaining_percent_monthly`, and `pooled_capacity_credits_primary`. A reported window whose absolute capacity is unknown SHALL retain its percentage without inventing credit quantities. Missing usage SHALL NOT be seeded as zero percent used. Incomplete-capacity pools SHALL use a consistent percentage basis for reported samples instead of a partial absolute credit sum.

When primary capacity is known zero, or no live primary sample exists, primary remaining percentage SHALL be null. Expired primary samples SHALL continue to use reset-window semantics; weekly and monthly samples SHALL retain their reported usage until refreshed.

#### Scenario: Scoped key pools assigned accounts only
- **WHEN** an API key is scoped to two selectable accounts
- **THEN** pooled usage reflects only those two accounts

#### Scenario: Unscoped key pools all accounts
- **WHEN** a key has no assignment scope
- **THEN** pooled usage reflects all selectable accounts

#### Scenario: Free-tier accounts hide primary bar
- **WHEN** assigned accounts all have known zero primary capacity
- **THEN** primary capacity is zero and primary remaining percentage is null

#### Scenario: Absent primary windows hide the pooled primary bar
- **WHEN** every primary sample is absent or expired
- **THEN** primary remaining percentage is null

#### Scenario: Paused and deactivated accounts are excluded
- **WHEN** a key includes active, paused and deactivated accounts
- **THEN** only active selectable accounts contribute to pooled usage

#### Scenario: Monthly Pro usage survives the API-key list contract
- **WHEN** a Pro-family account reports monthly usage at 65 percent
- **THEN** the key list exposes monthly remaining percentage as 35
- **AND** unknown Pro capacity does not hide that percentage
