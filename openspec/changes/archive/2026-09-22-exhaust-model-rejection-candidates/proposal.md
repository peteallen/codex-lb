## Why

The initial model-not-found fix recognizes the rejection but permits only one replacement. Live LAN requests can bounce between two accounts rejecting GPT-6 Sol while a third scoped account succeeds.

## What Changes

- Continue safe account/model rejection recovery through remaining eligible accounts within the original deadline, excluding each rejecting account.
- Keep generic replay limits, model selection, API-key scope, and file/continuation/acceptance safeguards unchanged.
- Cover multiple consecutive rejections followed by success and exhaustion across Responses transports.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `responses-api-compat`: Account/model rejection recovery traverses eligible candidates instead of stopping after one replacement.

## Impact

Native WebSocket, HTTP bridge, and raw HTTP recovery loops and regression tests. No new settings, schema, model aliases, or persistent account bans.
