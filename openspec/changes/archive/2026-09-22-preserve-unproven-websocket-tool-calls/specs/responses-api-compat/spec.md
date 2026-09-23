## ADDED Requirements

### Requirement: Anchored WebSocket trimming preserves unproven tool calls

For `/backend-api/codex/responses` and `/v1/responses` WebSocket requests with `previous_response_id`, the service MUST remove a leading replayed tool call only when existing continuity state for that exact response confirms the call ID and call type were emitted upstream. This MUST apply to `function_call`, `custom_tool_call`, and `apply_patch_call`. The service MUST preserve unconfirmed calls and all tool outputs in their relative order. Missing continuity state, a different completed response ID, or a different call type MUST NOT authorize removing a call. Existing treatment of assistant/reasoning replay prefixes and non-replay prefixes MUST remain unchanged.

#### Scenario: Client-created visualization call survives
- **WHEN** an anchored request includes a visualization function call, its output, and a user message, and the referenced upstream response did not emit that call
- **THEN** the upstream request retains all three items unchanged

#### Scenario: Confirmed upstream call is deduplicated
- **WHEN** an anchored follow-up replays a call whose ID and type match the recorded calls of that exact completed response
- **THEN** the service removes the duplicate call and retains its output

#### Scenario: Unknown or mismatched continuity preserves calls
- **WHEN** continuity is absent or identifies another response or another call type
- **THEN** the service preserves the supplied tool call and its output

#### Scenario: Mixed prefix preserves newly introduced calls
- **WHEN** a replay prefix contains both a confirmed upstream call and an unconfirmed client-created call
- **THEN** the service removes only the confirmed call and retains the unconfirmed call and every output in relative order
