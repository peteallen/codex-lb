# Proxy Admission Control Context

## Purpose and Scope

This capability protects proxy work at global, traffic-class, transport, and account boundaries. It covers where admission decisions happen and how local capacity failures remain distinguishable from upstream rate limits.

See `openspec/specs/proxy-admission-control/spec.md` for normative requirements.

## Account-cap Spillover Decision

Bare process-session affinity is locality, not ownership. When its mapped account is at a response-create or stream cap, selection may use another eligible account for the current self-contained, pre-visible request. The mapping itself is left untouched, so later work returns to the original locality account when capacity recovers.

Persistent rebind was rejected because admission completes at different points in plain streaming, compact, direct WebSocket, and HTTP bridge flows. Moving the mapping would require settlement and compensating rollback across sticky rows, durable bridge rows, local registries, and shared sockets. Request-local spillover removes that distributed transaction.

## Constraints and Failure Modes

- A late lease race does not switch a shared WebSocket or publish a replacement canonical bridge. A proven complete original HTTP request that has not dispatched can use a separate connection; true continuations retain bounded owner waits.
- Client previous-response, file, conversation, turn-state, replay, and reattach ownership remain fail-closed. A proxy-injected anchor is optional only when prefix matching, retained prior output, and account-neutral payload validation prove the original request is complete.
- A single process must run per instance because account caps are partitioned across replicas, not safely across worker processes inside one instance.
- Repeated self-contained requests may use different alternates during sustained pressure; this is an accepted cache-locality trade-off.

## Example

Session `S` is mapped to account A. A has all response-create slots in use, while account B has capacity. A new self-contained request carrying only `S` may run on B, but the stored mapping still points to A. A later request that references a response created on B follows that response's hard owner index; it does not rely on `S`.

## Operational Notes

Operators can distinguish local account pressure through the stable `account_response_create_cap` and `account_stream_cap` reasons. The spillover behavior is zero-config because it mutates no ownership state; rollback restores conservative fail-closed selection without data conversion.

Related capability: `openspec/specs/sticky-session-operations/`.

## Busy bridge capacity escape

Session-gate waiters no longer hold account startup leases. One stalled turn and three gate waiters therefore consume one startup slot, not all four. Once a gate opens, the request must still pass account and global admission.

For example, a client resends the previous input, the assistant output, and a new question under the same session/cache key. If the warm bridge is busy, the proxy sends the complete request on an independent connection to the same account. If that account is capped, it selects another eligible account. The canonical session and sticky mapping stay in place. Explicit client anchors, opaque references, file ownership, and incomplete context disable this escape. Any upstream dispatch, including an ambiguous send failure, also disables it.

Capacity retries snapshot separate startup and stream release signals before admission. Releases during an attempt remain visible to the waiter; releasing a temporary stream lease cannot repeatedly wake a startup-cap wait. When a round exhausts all candidates, temporary exclusions are cleared for the next round. Upstream quota and provider backoff keep their existing timing. No cap or timeout setting changes are needed.

## Upstream overload cooldown

Explicit upstream overloads suppress an account in runtime selection for a bounded cooldown, starting at 30 seconds and capped at 300 seconds when overlapping rejections escalate it. Successes from concurrent requests do not cancel an active hold. Expiry allows normal selection to probe recovery. The hold changes neither persisted account status nor generic health backoff and adds no settings or migrations.

For example, alternating successes and overloads on account A no longer let each success immediately return A to routing. New eligible work can use B, and requests wait when every eligible account is cooling. Local admission errors and invalid input do not create this upstream cooldown.

## Repeated overload recovery probes

Cooldown expiry only permits a new attempt; it does not prove recovery. The
runtime retains the latest overload timestamp for a fixed 15-minute recurrence
window, allowing holds to escalate through 30, 60, 120, 240, and 300 seconds even
when probes happen after expiry or some requests succeed. The count caps at
five and resets lazily after a quiet window. No operator setting is needed.

For example, overload at time zero holds the account for 30 seconds. Another
overload at second 31 holds it for 60 more seconds, so an independent request
at second 62 selects a healthy alternative. Explicit owner-bound requests still
follow their existing ownership and deadline rules. Accepted work remains
ineligible for automatic replay solely because the terminal error is overload.
