## ADDED Requirements

### Requirement: Responses usage retains reported cache-write tokens

HTTP streaming, bridged and native WebSocket completions, compact responses, and warmup request logs MUST retain `usage.input_tokens_details.cache_write_tokens` when supplied. Completed billable API-key usage MUST use the same reported write count as the request log. Request logs predating this field MUST keep a null write count, and omission MUST remain compatible with existing callers.

#### Scenario: Completed response charges cache writes consistently
- **WHEN** a successful Astra response includes cache-write tokens
- **THEN** the persisted log retains that count
- **AND** its estimate and finalized API-key cost include the same cache-write charge
