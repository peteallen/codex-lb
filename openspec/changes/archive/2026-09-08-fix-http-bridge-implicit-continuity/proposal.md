## Why

Plain OpenAI HTTP requests with a session header work unanchored on a live bridge, but an idle reconnect injects the durable last response ID. If that ID has expired upstream, otherwise independent requests repeatedly fail with masked `previous_response_not_found` errors.

## What Changes

- Require Codex continuity affinity or a verified stored input prefix before injecting a durable anchor on reconnect.
- Preserve explicit previous-response IDs, turn-state continuity, and prefix-proven resends.
- Cover the public HTTP route across live reuse and reconnect, including stale upstream anchors.

## Capabilities

### Modified Capabilities
- `responses-api-compat`: Session isolation alone does not establish implicit conversation continuity.

## Impact

HTTP bridge durable-anchor eligibility and regression tests. No settings, schema, or dashboard changes.
