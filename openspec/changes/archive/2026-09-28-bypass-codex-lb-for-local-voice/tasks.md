## 1. Adapter

- [x] 1.1 Implement the independent loopback voice adapter, local authentication, pinned identity, and credential rereads.
- [x] 1.2 Implement bounded call ownership, exact HTTP forwarding, WebSocket relay, cleanup, and safe diagnostics.

## 2. Verification and documentation

- [x] 2.1 Add HTTP/WebSocket regressions for routing isolation, identity changes, token rotation/expiry, protocol fidelity, denied/redirected upstream, and disconnect cleanup.
- [x] 2.2 Document installation, credential renewal, client activation, limitations, and selective rollback with an OpenSpec backlink.
- [x] 2.3 Run focused tests, Ruff, type checks, strict OpenSpec validation, and completeness/correctness review; sync and archive verified artifacts.

## 3. Authorized local installation

- [x] 3.1 Install the standalone service pinned to the user's existing selected account and verify local readiness plus upstream authorization.
- [x] 3.2 Back up user config privately, atomically change only voice overrides, and verify unchanged model routing and codex-lb health.
- [x] 3.3 Report the client restart/new-call boundary and distinguish verified routing from unverified audible improvement.
