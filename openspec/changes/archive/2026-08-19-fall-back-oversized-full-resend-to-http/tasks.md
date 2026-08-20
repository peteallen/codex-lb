- [x] Extend oversized WebSocket fallback classification to admit a complete
      resend with no `previous_response_id` and no nonblank `conversation`.
- [x] Preserve the complete unanchored input, including inline images, across
      the HTTP relay.
- [x] Keep anchored current-tool-output fallback support and proxy-injected
      anchor exclusion unchanged.
- [x] Keep conversation-backed and anchored non-tool oversized requests on the
      local `payload_too_large` path.
- [x] Keep a complete resend outside the shared WebSocket pending set and
      reject a second unanchored resend while the first relay is active.
- [x] Preserve synthesized turn-state classification and resolved file-owner
      proof across the HTTP relay.
- [x] Transfer reservation ownership without leaking the WebSocket heartbeat
      or racing detached settlement, including cancellation before preflight.
- [x] Route connection-level cancellation to the newest active HTTP or
      WebSocket turn.
- [x] Record upstream transport provenance for WebSocket continuity responses.
- [x] Keep exact continuations of HTTP-created responses on upstream HTTP and
      prevent HTTP-created responses from becoming injected WebSocket anchors.
- [x] Persist HTTP provenance before terminal delivery and make it available to
      a fresh service instance after request-log persistence.
- [x] Add unit and WebSocket product-path regression coverage for eligibility,
      routing, lifecycle, provenance, and preserved input.
- [x] Run focused tests, lint, format, diff checks, and OpenSpec validation
      where the local toolchain is available.
