## Context

The local service is also the assistant's provider. Preserve deployed commit d5155311 and its source/static snapshot, avoid dependency or schema changes, and run restart plus health verification with an independent rollback watchdog. The live incident joined one missing-created response with three gate waiters, enough to saturate a four-slot account. The original client supplied full context; a proxy-injected anchor changed its routing constraints.

## Goals / Non-Goals

Preserve cache keys, warm account preference, stored-context reuse on ready sessions, request ownership, and settlement. Remove artificial account pressure and permit independent unsent full-context work to use ready capacity. Do not replay accepted or output-bearing requests, strip client-owned state, change account caps, disable affinity, or incorporate the whole upstream release.

## Decisions

1. Acquire the narrow session gate before an account startup lease. On later admission failure, release the gate and every acquired lease. Waiting on a busy session holds no account startup lease.
2. Prove capacity mobility from original request provenance, before optimization. Require complete replay-safe input, no client previous response, no conversation, no file references/pin, and no client turn state. An injected anchor is removable only while this request has not dispatched or received output. Reuse the full-body replay proof already established by prefix matching; never infer safety merely from input length.
3. Extend the existing independent soft-reroute path rather than changing canonical bridge ownership. A fresh independent connection first prefers the warm account; a local account-cap rejection removes that preference once and reselects. Preserve the original prompt-cache key and existing stored mapping. The alternate's response ownership follows the existing response-owner machinery.
4. Detect a closed gate before beginning a deliberate admission wait for eligible work; repeat the same mobility check for admission races. Owner-bound requests retain bounded waits and no unsafe account changes.
5. Use a generation/event-style capacity-release signal with bounded timeout and normal rechecking. Wakeups grant no lease themselves and cannot bypass per-account, API-key, quota, or security checks. Preserve upstream backoff durations.
6. Report bounded event-type/progress metadata on missing-created failures; do not log payloads or invent a shorter model-output timeout. The existing proven-failure quarantine remains intact.

## Risks / Trade-offs

- Alternate accounts can lose prompt-cache hits. Prefer same-account fresh connections and retain canonical locality for later work.
- A full resend can still contain account-owned objects. Existing explicit ownership and file checks remain mandatory.
- Duplicate dispatch after upstream activity would be unsafe. Restrict capacity escape to locally rejected, unsent requests; preserve all acceptance/visibility guards.
- Lease ordering changes cancellation paths. Cover gate timeout, cancellation at both stages, account-cap rejection, and successful release with deterministic tests.

## Validation and deployment

Reproduce the real bridge path under a blocked gate and available second account, as well as true owner-bound and output-bearing negative controls. Run focused proxy/integration checks, type/lint checks, strict OpenSpec validation, and available broader CI. Before restart publish the saved recovery command and arm a detached health-check rollback process. No database restoration is needed because this change contains no schema or data mutations.
