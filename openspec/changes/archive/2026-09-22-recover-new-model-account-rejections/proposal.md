## Why

During the GPT-6 Sol and Luna rollout, an account can advertise a model in its catalog yet reject execution with `model_not_found`, while another account serves it successfully. The proxy's existing safe account/model retry recognizes only the older unsupported-model error, so clients repeatedly hit the rejecting account.

## What Changes

- Recognize the exact upstream `model_not_found` message for the requested model as eligible for the existing bounded account/model retry.
- Preserve the requested model, account ownership, pre-acceptance checks, API-key scope, and original error when no replacement is available.
- Add regression coverage for both new models across Responses transports and unsafe replay boundaries.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `responses-api-compat`: Extend safe account/model rejection recovery to the canonical model-not-found envelope.

## Impact

Shared proxy error matching and tests for native WebSocket, HTTP streaming, and HTTP bridge Responses requests. No configuration, schema, pricing, or model alias changes.
