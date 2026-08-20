- [x] Add a websocket integration regression for an oversized unanchored full
      resend with inline images after the latest user message.
- [x] Extend fallback classification to admit a final oversized body with no
      `previous_response_id` while preserving the anchored and proxy-injected
      exclusions.
- [x] Verify the relayed HTTP body preserves the complete input and that no
      upstream websocket or oversized dump is produced.
- [x] Keep an integration regression for an ineligible oversized anchored
      non-tool request.
- [x] Prevent and test a second full-history resend overtaking an active HTTP
      fallback that is absent from the shared websocket pending set.
- [x] Keep nonblank `conversation` requests owner-bound and covered at the
      WebSocket product path.
- [x] Preserve synthesized turn-state classification and hard file-owner proof
      across the HTTP relay.
- [x] Transfer reservation ownership without leaking the WebSocket heartbeat or
      racing detached settlement, including preflight and post-transfer cancel
      regressions.
- [x] Route connection-level cancellation to the newest active HTTP or
      WebSocket turn.
- [x] Keep an exact client continuation of an HTTP-created response on upstream
      HTTP, and prevent that response ID from being auto-injected into an
      unanchored WebSocket request.
- [x] Compare-and-clear an upstream-rejected proxy continuity anchor and verify
      that an unanchored retry does not receive it again.
- [x] Revalidate proxy-injected continuity after all late waits and verify a
      cleared anchor is replaced with the retained fresh body before send.
- [x] Publish successful HTTP provenance before persistence, wait for its
      tracked commit attempt before terminal delivery, and verify a fresh
      service instance resolves the persisted HTTP transport.
- [x] Run focused tests, lint, format, type checks, and strict OpenSpec
      validation.
