## Why

The live proxy repeatedly surfaced upstream overloads from one account while other accounts completed requests. Raw HTTP first-event overloads bypass transient recovery, and intermittent successes erase the failing account's backoff history. Recoverable overload must schedule available capacity or wait rather than prematurely ending a request.

## What Changes

- Retry explicit, unaccepted upstream overload failures before emitting a terminal event, consistently across HTTP and WebSocket paths.
- Apply a bounded account overload cooldown that cannot be erased by an unrelated concurrent success.
- Prefer other eligible capacity over soft session/cache affinity; queue recoverable overloads until capacity recovers or the request deadline/cancellation ends the wait.
- Preserve upstream acceptance, visible-output, account ownership, tool side-effect, reservation settlement, and cancellation safeguards.
- Add externally routed regressions and bounded operational diagnostics without logging request contents.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `responses-api-compat`: consistent pre-visible overload recovery and deadline-bounded scheduling.
- `proxy-admission-control`: overload cooldown, soft-affinity escape, and capacity waiting semantics.

## Impact

Proxy streaming/bridge/WebSocket recovery, account runtime health, regression tests, and owning specifications. No schema changes, new configuration, frontend changes, or dependency additions.
