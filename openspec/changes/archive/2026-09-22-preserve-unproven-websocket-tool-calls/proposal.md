## Why

Anchored WebSocket follow-ups can include tool calls created by the client, such as visualization state, that the upstream response never emitted. Removing those calls while retaining their outputs produces an upstream `No tool call found` error and stops the task.

## What Changes

- Require matching completed-response continuity evidence before removing replayed tool calls.
- Preserve unproven calls and their outputs, including when continuity is absent or refers to a different response.
- Cover the actual WebSocket routes and known-duplicate behavior with regression tests.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `responses-api-compat`: Preserve tool-call dependencies during anchored WebSocket replay trimming.

## Impact

WebSocket request preparation and its existing replay-trimming helper. No new settings, dependencies, database changes, or account-routing behavior.
