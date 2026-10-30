# Verification: upstream denials and usage retries

## Review correction (2026-10-30)

The archived change was rechecked against the externally visible HTTP bridge
and streamed Responses paths. The correction gates all four HTTP bridge
connection/reattachment 401 refresh decisions on the typed refreshable-auth
classification, and makes permanent streamed terminal failures await API-key
reservation settlement before account-health writes. Regression coverage now
exercises both paths with real imported accounts and API-key reservations.

On the combined October 30 branch, the HTTP bridge, Responses streaming, and
usage API integration suites passed all 253 tests. Repository-wide Ruff,
formatting, Ty, and proxy architecture checks passed. OpenSpec 1.7 strict
validation passed all 181 active changes and main specifications. These are
local checks; they do not establish live-provider or cloud CI behavior.

## Result

All six implementation/verification tasks are complete. Both owning capabilities have been synced to their main specifications, including their operational context. At the original verification, changes remained local and pre-existing local voice files and edits were preserved. Publication and deployment are tracked separately from these local verification results.

## Requirement coverage

| Behavior | Implementation | Regression evidence |
| --- | --- | --- |
| Retry-After floor on both transports and both usage operations | usage client retry policy and shared HTTP header parser | Numeric/date/malformed/missing headers, lowercase routed headers, bounded attempts and cancellation |
| Final Retry-After postpones polling | UsageFetchError metadata and existing process-local cooldown | Final error metadata and polling before/after deadline, including 401 without forced refresh |
| Revocation requires reauthentication | Shared terminal code tables, existing guarded auth manager writes and proxy retry gates | Usage cycles skip revoked accounts, guarded OAuth status handling, HTTP/compact/WebSocket call stops |
| Unknown 403 fails closed | Shared classification and terminal authorization helper before overload/failover | Both HTTP routes, post-refresh 403, capacity-like messages and WebSocket handshake denials |
| Reservation settlement precedes health/status updates | Streaming, compact and WebSocket terminal boundaries | Real API-key reservation rows are released before status or health callbacks for token_revoked and unknown 403 |
| HTTP bridge terminal auth does not replay | Bridge connection and reattachment auth gates | `test_v1_responses_http_bridge_terminal_auth_does_not_force_refresh_or_fail_over` proves a `401 token_revoked` is surfaced after one connection attempt with no forced refresh |
| Streamed terminal auth settles before health | Normal streamed `response.failed` completion and terminal stream handling | `test_terminal_auth_sse_releases_real_reservation_before_status_write` observes the reservation row as `released` inside `mark_permanent_failure` for a real `response.created` → `response.failed(token_revoked)` stream |
| Bare usage 402/404 does not deactivate | Explicit-evidence usage classifier | Bare failures retain status; explicit codes/messages still deactivate or require reauthentication |
| Native refresh and recognized fallback preserved | Access-token expiry exception and existing exact quota/model/security guards | Access token_expired refresh succeeds; OAuth token_expired stays permanent; existing quota, security, model and continuity suites pass |

## Validation

Validation used `.venv/bin/python` (CPython 3.14.7 in this checkout), Ruff, ty, and the cached OpenSpec 1.3.0 CLI. Upstream traffic was stubbed; the real WebSocket liveness check used only a local loopback server.

- Broad affected unit suites: 1,555 passed. A final rerun of the affected usage, auth classification, failover and security subset passed 242 checks.
- Final HTTP Responses, compact, files and transcription integration suites: 170 passed.
- WebSocket Responses and model-rejection integration suites: 139 passed, one local network test deselected. The deselected loopback test passed separately outside the sandbox; its sandbox failure was permission to bind 127.0.0.1, not a product assertion failure.
- Additional focused terminal-auth, Retry-After and reservation ordering checks passed. Tests for repeated generic 401 now stub refresh explicitly and prove the intended same-account refresh followed by fallback without contacting OAuth.
- Ruff check and format check, ty on affected application modules, and git diff --check passed.
- Strict OpenSpec validation: change passed and all 50 main specifications passed.

The WebSocket suite emitted a Starlette/httpx deprecation warning and an aiosqlite worker warning about a closed test event loop in an existing capability-carrier test. All assertions passed. That separate lifecycle warning was not changed by this implementation.

## Operational limits

Polling cooldowns are process-local and do not survive restarts or coordinate replicas. Valid server waits are not shortened by the local exponential cap and remain cancellable. The implementation does not identify why OpenAI terminated any account, and deployment remains a separate step.
