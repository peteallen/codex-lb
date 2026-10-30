## Context

Direct usage calls use aiohttp-retry; routed usage calls implement a bounded retry loop. Both must observe the same Retry-After parser. Shared permanent failure codes already distinguish reauthentication from provider account deactivation and guard concurrent token rotation.

## Decisions

- Extend ExponentialRetry timeout calculation and reuse an HTTP header parser in routed loops. A valid upstream delay is a floor; the existing local backoff remains the fallback/minimum. Do not cap or shorten valid server waits. Existing attempt limits and asyncio cancellation remain in force. Header names are case insensitive even when buffered routed responses use plain dictionaries. Final errors retain the remaining wait and extend the existing process-local polling cooldown; a positive server wait also prevents an immediate forced refresh on 401.
- Add explicit `token_revoked`, `session_revoked`, and `authentication_token_revoked` to the existing terminal reauthentication code tables. Gate 401 refresh/retry paths using a shared typed error property. Keep generic 401's existing bounded refresh handling, including access-token-only expiry. A token_expired code at the OAuth refresh boundary remains permanent.
- Classify terminal codes and unrecognized 401/403 as non-retryable before generic transient codes/message/5xx. Explicit rate-limit/quota codes retain their dedicated handling; model/security/trusted-access fallback remains subject to existing exact-match and ownership guards.
- Bare usage 402/404 only fail the observation. Explicit deactivation codes/messages still deactivate and explicit credential errors still require reauthentication.

## Risks and validation

Long upstream waits remain cancellable. No server is contacted by regression tests. Exercise direct aiohttp retry behavior, routed clients, usage updater cycles, HTTP Responses and WebSocket denial paths, plus existing token-rotation and settlement tests. Preserve account ownership and quota settlement order; no historical account is automatically reactivated.
