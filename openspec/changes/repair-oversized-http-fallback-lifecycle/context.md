# Context

The fallback keeps a client-facing Responses WebSocket open while its upstream
request is streamed over HTTP. That split means state which the normal
WebSocket reader owns must be transferred explicitly: capability routing must
be supplied to the HTTP selector, capability aliases must be persisted before
the new response ID is visible, and the detached relay must participate in
drain and cancellation cleanup.

The fallback remains fail-closed for requests that are not already eligible for
the HTTP path. No database migration or configuration flag is needed.
