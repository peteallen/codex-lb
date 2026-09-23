## Context

The restart guardian loop was removed separately. Subsequent live overloads concentrated on one account while other accounts succeeded. Raw HTTP streaming classifies overload as transient in helpers but surfaces first-event overloads without consulting that classifier. Account-wide transient counts are reset by any success. Existing retries and capacity waits differ across raw HTTP, bridged HTTP, and direct WebSocket traffic.

## Goals / Non-Goals

**Goals:** Recover explicit pre-acceptance overloads using healthy capacity, retain overloaded-account cooldown despite concurrent successes, and wait within the existing request budget when eligible capacity is temporarily unavailable.

**Non-Goals:** Retry invalid input or ambiguous accepted work; replay emitted tool actions; discard account-owned resources or conversation context; alter image handling, pricing, schemas, configuration, or frontend behavior.

## Decisions

- Add narrowly classified overload recovery for `overloaded_error`, `server_is_overloaded`, and the existing recognized model-capacity rejection. Generic server errors and timeouts retain their current replay-safety behavior.
- Preserve acceptance/progress guards: an assigned upstream response id or already visible output prevents transparent replay. A pre-acceptance overload does not consume the whole request budget.
- Use bounded account-runtime overload cooldown distinct from the generic consecutive-error counter. Success must not erase an active overload cooldown. Account selection must not bypass this cooldown through backoff fallback; normal selection after cooldown expiry acts as a recovery probe.
- Prefer alternate eligible accounts for replayable original requests. Keep true file/turn-state/continuation ownership unless existing full-history proof permits account-neutral replay. Soft affinity must not pin a recoverable failure.
- Reuse existing capacity keepalive/wait, cancellation, and request-deadline machinery. Release admission and account leases before sleeping; retain the logical API-key reservation until final settlement. Temporary overload exclusions expire for retry after a bounded wait, while permanent/request-specific exclusions remain.
- Record runtime overload admission suppression immediately while retaining that logical reservation. This scheduler state changes neither persisted account status nor generic health backoff; existing settlement-before-health-write ordering remains intact.
- Keep independent account-recovery state scoped to a request and bound retries by elapsed budget. Avoid multiplying the existing nested retry loops or adding background tasks.

## Risks / Trade-offs

- Longer waits during a broad upstream incident: keepalives and the existing client deadline/cancellation bound lifetime.
- Replaying accepted work can duplicate output: explicit acceptance and visible-output negative tests gate recovery.
- Concurrent successes could clear cooldown accidentally: mixed-success/error and probe tests verify the independent cooldown.
- Deploying affects active streams: preserve a fixed source snapshot and use a single controlled restart with readiness and PID stability verification, never a keepalive rollout job.

## Migration Plan

No database migration or dependency change. Run focused routed tests and broader proxy checks, synchronize specifications, then verify and archive the change. Preserve source/static rollback artifacts before a single live restart and verify stability beyond the old restart interval.
