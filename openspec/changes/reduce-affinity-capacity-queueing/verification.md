# Verification: reduce-affinity-capacity-queueing

## Requirement evidence

| Requirement | Implementation and regression evidence |
| --- | --- |
| Gate waiters hold no account startup lease | `service.py` acquires the session gate before the account lease. `test_proxy_capacity_admission.py` verifies three contending waiters, independent admission, account rejection, and cancellation at both later admission stages. |
| Complete original requests can escape capacity pressure | `http_bridge/capacity.py` checks original provenance, stored prefix, retained output, account-neutral payloads, and dispatch/progress state. `test_http_responses_bridge.py::test_full_resend_escapes_capacity_without_rebinding_warm_bridge` exercises the actual HTTP route with a busy gate, late gate race, startup cap, connection cap, and all accounts capped. |
| Canonical locality and ownership remain intact | The route regression verifies the same canonical session object and previous anchor, no second dispatch on its socket, full input on the independent connection, and the original prompt-cache key. Client anchors, turn-state headers, and incomplete follow-ups remain on the original socket. Existing file-pin tests and new opaque-reference/file/progress negative controls cover refusal to escape. |
| Capacity waits wake without granting capacity | Separate rolling startup and stream events are captured before admission. Competing-waiter tests retain the configured cap, duplicate releases do not signal a new generation, cancellation leaves no waiter, and provider backoff errors do not receive a local wakeup event. The HTTP all-accounts-cap scenario completes after capacity is released. |
| Missing-created failures reveal bounded progress | The reader records at most 16 pending request summaries with allowlisted event categories and dispatch/acknowledgment/visibility flags. A failure-path test verifies the diagnostic and absence of a private body sentinel. |

## Checks

- Latest focused capacity/bridge unit selection: 61 passed.
- Latest HTTP routing matrix: 8 passed.
- Python Ruff, formatting, type checks, and proxy architecture budgets passed.
- Strict OpenSpec validation: all 49 main specs and the active change passed.
- Isolated candidate startup on a temporary port/database passed `/health/ready`; that temporary process was then stopped.
- Live database preflight: head `20260904_000000_add_request_log_cache_write_tokens`, `migration_policy=ok`, `schema_drift=none`.
- The previously preserved frontend passed all 1,061 tests and its production build. This change adds no frontend behavior.
- Full backend verification: **7,833 passed, 93 skipped, 2 deselected** in 816 seconds. Deployment-specific dotenv settings were excluded only in that test process. The two existing metrics-import isolation tests were reproduced separately as failures; their code and production metrics code are unchanged by this work. The final preferred-account fallback adjustment was additionally verified by all eight HTTP routing matrix cases.
- Full infrastructure CI is not claimed: PostgreSQL, Docker/Trivy, Helm and kind gates are outside this local SQLite deployment verification; Helm is unavailable locally.

## Deployment

No schema or dependency changes. The source/static snapshot at `.codex-lb/deploy-backups/capacity-d5155311/source.tar.gz` preserves the previously deployed implementation. The launchd-owned rollout guardian performs the restart, requires a new healthy PID, observes it for 90 seconds, and runs the saved recovery script if startup or readiness fails. Final deployment evidence is appended after rollout.
