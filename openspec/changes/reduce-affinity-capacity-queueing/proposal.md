## Why

A stalled shared bridge currently consumes account response-create slots for requests that are only waiting on its session gate. In the observed incident, an injected stored-context continuation stalled for 303 seconds while three unsent waiters filled the rest of the account's four-slot allowance. Full client resends also become ineligible for capacity spillover after the proxy injects its optional continuation anchor.

## What Changes

- Reserve account startup capacity only after the session gate is acquired, with complete cancellation and failure cleanup.
- Preserve a proof-gated original full resend for local capacity escape before upstream dispatch. Prefer a fresh connection on the same account, then another eligible account when the preferred account is capped; preserve prompt-cache keys and existing canonical ownership.
- Avoid deliberately waiting for a busy bridge when a request has a safe independent route; retain bounded waits for true owner-bound work and when no eligible capacity exists.
- Wake bridge capacity retries on lease release instead of always waiting through fixed local-backpressure sleeps.
- Add body-free diagnostics for missing-created bridge failures and distinguish unsent waiters from upstream startup pressure.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `proxy-admission-control`: gate acquisition order, safe original-resend capacity escape, and capacity-release wakeups.
- `proxy-runtime-observability`: bounded protocol-progress diagnostics without prompt or credential content.

## Impact

Proxy admission, HTTP bridge routing, account lease notifications, and regression tests. No database migration, new configuration, default cap increase, or global affinity disablement. Keep upstream work that may already have produced output protected from duplicate replay. Implement on the fork's main branch as explicitly requested; the 240-commit upstream upgrade is a separate concern.
