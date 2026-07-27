# Tasks: support-realtime-voice-sideband

## 1. OpenSpec contract

- [x] 1.1 Add proposal, design, context, and delta specs for the Voice
      sideband and its migration; run strict OpenSpec validation.

## 2. Durable call binding

- [x] 2.1 Add the `RealtimeCallBinding` model and shared repository operations
      for insert, lookup, atomic claim, holder-matched renew/release/delete,
      and expired-row cleanup.
- [x] 2.2 Add one Alembic revision on
      `20260713_040000_add_account_refresh_claims` with reversible SQLite and
      PostgreSQL-compatible schema, foreign keys, and expiry index.
- [x] 2.3 Add a no-op Alembic merge revision joining the binding revision and
      `20260722_000000_backfill_request_log_useragent_families` so the graph has
      one head and an already-stamped database can catch up without a stamp.
- [x] 2.4 Extend migration upgrade/downgrade, policy, and schema-drift coverage
      for both supported database families, including the already-stamped
      catch-up path.

## 3. Call-create binding

- [x] 3.1 Retain the exact final account used by Codex control requests after
      refresh/failover without running a second account selection.
- [x] 3.2 On realtime-call `201`, strictly parse `Location` and commit the
      call/account/API-key binding before returning; fail closed on malformed
      locations, duplicate IDs, or persistence errors, and never bind failed
      responses.
- [x] 3.3 Pass the computed control request kind into logging and prove realtime
      call rows use `codex_control_realtime_calls` rather than `normal`.

## 4. Sideband join and bound upstream connection

- [x] 4.1 Add only the validated `rtc_*` and canonical UUID backend Codex
      WebSocket route shapes, preserving ordered and repeated query parameters.
- [x] 4.2 Run the existing WebSocket auth guard before lookup; require exact
      API-key identity, current account-assignment scope, unexpired binding,
      and a winning atomic claim before any upstream request.
- [x] 4.3 Load and refresh only the bound account, and apply that account's
      existing upstream proxy/direct-egress routing without account failover.
- [x] 4.4 Renew long-lived claims, release claims on all pre-open failures, and
      delete holder-owned bindings after every terminal opened relay.

## 5. Voice handshake and transparent relay

- [x] 5.1 Add a dedicated case-insensitive Voice header builder that replaces
      authorization/account identity, preserves allowlisted Voice/session/
      thread/originator/attestation headers (including `quicksilver=v2` and
      `x-session-id`), and strips cookies, forwarding, hop-by-hop, proxy, and
      downstream WebSocket handshake headers.
- [x] 5.2 Prove the Voice builder never injects or forwards the Responses
      WebSocket beta token and does not change the existing Responses builder.
- [x] 5.3 Implement an owned two-task text/binary relay with close-code/reason
      propagation, sibling cancellation/awaiting, socket closure, and exactly
      once binding cleanup; do not parse or archive frames.
- [x] 5.4 Translate path-based Frameless joins to
      `wss://api.openai.com/v1/live/<call-id>` for both accepted call-ID forms,
      preserving the downstream query rather than reusing the ChatGPT
      call-create base.

## 6. Regression and integration coverage

- [x] 6.1 Cover final-account binding after create failover, valid `rtc_*` and
      UUID locations, malformed/missing locations, non-201 responses, duplicate
      IDs, persistence failure, and dedicated request logging.
- [x] 6.2 Prove malformed, unknown, expired, already-claimed, wrong-key,
      revoked-key, and newly out-of-scope joins make no upstream request.
- [x] 6.3 Simulate create on replica A and join on replica B, plus simultaneous
      joins where exactly one atomic claim opens upstream.
- [x] 6.4 Cover same-account pre-open retry, freshness success/failure, strict
      no-account-failover behavior, configured upstream-proxy routing, and
      direct egress.
- [x] 6.5 Cover query and safe-header preservation, auth/account replacement,
      stripped unsafe headers, text/binary fidelity, both close directions,
      relay cancellation, pre-open release, heartbeat renewal/loss, and
      holder-fenced cleanup.
- [x] 6.6 Prove `/backend-api/codex/responses` and `/v1/responses` WebSockets
      retain their existing header, routing, event, and cleanup behavior.
- [x] 6.7 Add phase-specific sideband diagnostics for local authentication,
      binding lookup/key match/claim, bound-account refresh/route, and upstream
      handshake outcomes, including upstream status and sanitized error code.
- [x] 6.8 Prove diagnostics contain only safe header-presence and attestation
      envelope metadata and never contain header values, tokens, IDs, SDP,
      queries, response bodies, or frames.
- [x] 6.9 Prove both accepted path-based call-ID forms target OpenAI's Live
      endpoint and do not regress direct or configured-proxy routing.

## 7. Verification

- [x] 7.1 Run focused unit/integration suites, formatting, lint, type checks,
      strict OpenSpec validation, migration checks, and the broader proxy and
      Responses WebSocket suites.
- [ ] 7.2 Exercise the current ChatGPT/Codex live-voice create plus sideband
      sequence end to end against a non-live local codex-lb instance, including
      a routed-proxy account and a direct-egress account, without restarting the
      active service.
- [x] 7.3 Run the focused observability unit/integration suites, formatting,
      lint, type checks, and manual OpenSpec artifact/heading/task structure
      checks.
- [x] 7.4 Run a fresh strict OpenSpec validation covering the observability
      amendment and the migration-merge amendment.
