## MODIFIED Requirements

### Requirement: Responses Lite follow-up transformations fail closed

After a request is classified as Responses Lite shaped, the service MUST preserve required Lite state through compact preparation, MUST validate the final transformed compact input against the upstream JSON wire budget, MUST reject policy rewrites to catalog-confirmed non-Lite models, and MUST suppress replayed code-mode side effects without collapsing distinct call identities. Compact trimming MAY omit a complete terminal non-state, non-side-effecting tool pair only when the pair plus required anchors and trim markers cannot fit the upstream wire budget, and MUST omit the call and its output together. A latest output anchored by `previous_response_id` or a non-empty `conversation` remains required only when its matching call is absent from supplied input. A supplied call matches an output only when both `call_id` and the function/custom/apply-patch protocol variant are compatible, and only for its own occurrence in that protocol's call/output stream. An unmatched latest tool call, required text, a state-tool tail, and a terminal tool call or matching pair classified as side-effecting by the canonical tool-safety classifier remain required compact context. Historical side-effect anchors already protected by that classifier MUST NOT be dropped by terminal-delta handling. These guards MUST NOT weaken the body-derived Lite signal or trusted previous-response linkage rules.

#### Scenario: Oversized compact input keeps the Lite prelude

- **WHEN** compact input trimming is required for a Responses Lite request
- **THEN** every required `additional_tools` item remains in the upstream input
- **AND** typed and role-only system/developer state remains in the upstream input

#### Scenario: Compact input keeps a latest tool pair that fits

- **WHEN** compact trimming is required, the latest input item is a non-state, non-side-effecting tool call or tool output, and its complete pair fits with required anchors and trim markers
- **THEN** the latest item remains in the upstream input
- **AND** any matching call or output present in the supplied input is retained with it

#### Scenario: Oversized non-state tool tail leaves room for trim markers

- **WHEN** the latest input item is a non-state, non-side-effecting tool call or output whose complete pair cannot fit with required anchors and trim markers
- **THEN** the service omits the call and output together and represents the omission with a compact-trim marker
- **AND** it does not return `responses_compact_input_too_large` solely because the pair fit before marker framing
- **AND** the marker does not claim omitted terminal context was preserved

#### Scenario: Continuity-anchored latest unpaired tool output remains required

- **WHEN** a compact request carries `previous_response_id` or a non-empty `conversation` and its latest input item is a tool output without a matching call in the supplied input
- **THEN** the output remains in the upstream input because its call belongs to the prior response
- **AND** the service returns `responses_compact_input_too_large` when that required output cannot fit

#### Scenario: Self-contained anchored ordinary pair remains optional

- **WHEN** a compact request carries `previous_response_id` or a non-empty `conversation` and its latest ordinary tool output has a matching call in supplied input
- **THEN** compact trimming MAY omit the complete pair when it cannot fit

#### Scenario: Reused call ID from another tool variant does not satisfy continuity

- **WHEN** a compact request carries `previous_response_id` or a non-empty `conversation` and its latest tool output reuses the `call_id` of an incompatible function/custom/apply-patch call variant in supplied input
- **THEN** the latest output remains required as continuity from the previous response
- **AND** the incompatible supplied call is not retained as its pair

#### Scenario: Stale local occurrence of a continuity delta call id is dropped

- **WHEN** a compact request carries `previous_response_id` or a non-empty `conversation`, its latest tool output has no matching call in supplied input, and an earlier supplied call or output in the same protocol reuses that `call_id`
- **THEN** compact trimming drops those stale earlier occurrences so upstream cannot pair the delta with the wrong occurrence
- **AND** required state anchors and protected historical side-effect records are retained

#### Scenario: Oversized latest unmatched tool call fails closed

- **WHEN** the latest compact input item is an unmatched tool call that cannot fit the compact wire budget
- **THEN** the service returns `responses_compact_input_too_large` rather than representing the call with a compact-trim marker

#### Scenario: Side-effecting tail remains required

- **WHEN** the latest compact input item is an `apply_patch_call`, `apply_patch_call_output`, or a tool call or matching pair classified as side-effecting by the canonical tool-safety classifier
- **THEN** the item and any matching counterpart remain required compact context
- **AND** the service returns `responses_compact_input_too_large` rather than omitting the side-effecting record when it cannot fit

#### Scenario: Reused call IDs keep only the required occurrence

- **WHEN** an older tool call and a required state-tool call reuse the same call ID
- **THEN** compact trimming retains the output matched to the required state-call occurrence
- **AND** it does not retain an oversized historical output solely because its earlier call reused that ID
