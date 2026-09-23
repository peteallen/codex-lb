# Verification: recover overloaded requests

## Contract coverage

- Raw HTTP `/v1/responses` and `/backend-api/codex/responses`: repeated explicit pre-acceptance overloads beyond fixed attempt limits, new work while all accounts cool, soft session/cache failover, deadline expiry, owned files and previous responses, and 401-refresh overload recovery.
- Bridged HTTP: both routes use an alternate eligible account before waiting; four consecutive overloads recover; single-account, file-owned, and warmed previous-response continuations wait for their owner. Existing quota/model-capacity behavior and acceptance/visible-output no-replay safeguards remain covered.
- Direct WebSocket: repeated overloads, real-selector alternate capacity and same-owner waiting, acceptance/visible-output refusal, and release-before-reconnect ordering.
- Cancellation: stream and response-create leases, gate ownership, and real API-key reservations are reclaimed when cancellation interrupts waiting or asynchronous release. Shared release completes before cancellation propagates; owned cleanup tasks are awaited.
- Cooldown: runtime-only account suppression starts at 30 seconds and caps at 300 seconds for overlapping rejections; concurrent successes cannot erase an active hold. No schema, settings, or dependency changes.

## Validation

- Combined raw HTTP, admission, cooldown and replay-safety run: 284 passed.
- Broader capacity, files, API-key and proxy API regressions: 220 passed.
- Bridge integration/unit and alternate-capacity run: 652 passed.
- Affected bridge compatibility/cancellation rerun: 65 passed.
- Direct WebSocket regression run: 119 passed; the separately sandbox-blocked loopback watchdog passed when rerun with local-network permission.
- Final overload route/cancellation/cooldown run before shared cleanup consolidation: 41 passed; follow-up WebSocket and bridge cancellation run: 11 passed.
- Shared response-create gate cancellation regressions: 2 passed.
- Final consolidated overload, ownership, cancellation, cooldown, and transient tests: 103 passed. Shared gate release tests: 2 passed.
- Ruff, formatting, typing, architecture budgets and `git diff --check` pass.
- Strict validation passes for this change and both changed main capabilities. Repository-wide strict specs: 48 pass; unchanged `api-keys` has two existing normative-keyword errors. No changes were made to that capability.
- Live database revision: `20260904_000000_add_request_log_cache_write_tokens`; migration policy valid, schema drift absent.

## Review and delivery

Independent reviews checked retry eligibility, account ownership, settlement, selection, and cancellation. Overload suppression is runtime admission state, so recording it before logical request settlement does not mutate persisted account health. Cancellation findings were fixed with routed regressions.

Rollback source from `084ed6cf` and built static assets have fixed SHA-256 manifests under `.codex-lb/deploy-backups/overload-recovery-20260907/`. The initial rollout changed PID 88619 to 10426 and remained ready for the 171-second stability check, with a later readback still healthy. The erroneous keepalive rollout guardian remains absent. The final cleanup consolidation was deployed at 2026-09-07 07:51:46 UTC, changed PID 10426 to 23353, and passed the 179.6-second stability check. At 08:14 UTC the same PID was ready, all 17 candidate source files matched the deployment manifest, database checks passed, and the old guardian remained absent.

Live observation after initial rollout recorded hundreds of successful requests and remaining `server_is_overloaded` errors. Eighteen of nineteen sampled overload rows had response-created latency, confirming upstream acceptance and the no-replay boundary. One raw-HTTP row lacks that timing; without archived raw events its acceptance cannot be conclusively classified. These results do not establish zero possible errors or prove a broad OpenAI outage.

## Final live readback

After the final deployment and through the 08:14 UTC readback, request logs recorded 592 successes, 12 overload errors, eight `stream_incomplete` errors, and six client cancellations. All 12 overload rows had response-created timing; one also had first-token timing. The eight other errors comprise four upstream socket disconnects and four missing previous-response errors without a safe full replay. These separate failures remain visible; the deployed change does not claim zero possible failures or replay accepted/ambiguous work.

The source remains uncommitted on the existing branch, per the repository's explicit-request-only Git workflow. No migration or frontend changes were required. The pre-existing `.playwright-cli/` directory was preserved.
