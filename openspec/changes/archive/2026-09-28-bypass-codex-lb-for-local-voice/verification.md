# Verification

Verified locally on 2026-09-28 against the completed implementation.

## Completeness and correctness

All five requirements have implementation and regression coverage:

| Requirement | Evidence |
| --- | --- |
| Isolated opt-in routing | Standalone script, fixed CLI upstreams, loopback-only bind; route, authentication, browser-Origin, and trailing-slash tests |
| Selected managed identity | Email/account/expiry checks; token rotation, identity switch, missing/malformed credentials, and unchanged auth-file tests |
| Bounded ownership and destinations | Location, binding, key rotation, duplicate attach, query conflict, capacity, response limit, and HTTP/WS redirect/denial tests |
| Streaming cleanup and diagnostics | Text/binary fidelity, subprotocol/query/close preservation, abrupt close, handshake cancellation/timeout, shutdown, message size, idle-lifetime, and log-privacy tests |
| Recoverable installation | Configuration helper tests cover private backups, byte-preserved provider text, existing backup refusal, and selective rollback after unrelated edits |

Focused verification passed: 136 tests across the new adapter/configuration tests and existing realtime unit/integration suites. Ruff and ty passed on all four changed Python files. The only test warning is the existing Starlette/httpx deprecation.

The change and the synced `local-voice-direct` main spec pass strict OpenSpec validation. The strict documentation build passes using the repository's pinned MkDocs 1.6.1 and Material 9.7.7 in an isolated temporary environment. `git diff --check` and Ruff format verification pass.

Repository-wide strict spec validation reports 49 passing specs and one pre-existing failure: `api-keys` requirements 23 and 24 lack SHALL/MUST in their requirement text. That file is identical to HEAD and was not changed. This limits the repository-wide result but does not leave a requirement of this change unverified.

## Coherence

Implementation follows the independent-process design. No app module, database schema, dependency declaration, provider definition, proxy setting, or base-service startup code changed. The user guide links to the new main OpenSpec capability. Credential refresh remains owned by the official client and the documentation states the expiration/re-login boundary.

## Authorized local installation evidence

- The selected existing ChatGPT login passed identity/expiry checks and an authenticated direct OpenAI account request returned HTTP 200; no microphone or voice call was created for that check.
- The new separate LaunchAgent is running with a loopback-only listener on port 2456 and readiness HTTP 200.
- Installed script hashes match the tested source. Config, backup, LaunchAgent, and log files have owner-only permissions.
- Exactly the two voice URL overrides changed. Removing those two lines from the before/after files produces identical bytes.
- The model provider and its port-2455 URL are unchanged. codex-lb retained its existing process and returned readiness HTTP 200.

## Verification boundary

The official client was not restarted or interrupted. A restart/new voice call is needed to verify client adoption and audible behavior. Neither the test suite nor the successful account probe proves that WebRTC stutter or hangups are resolved. The user was told this boundary when installation completed.
