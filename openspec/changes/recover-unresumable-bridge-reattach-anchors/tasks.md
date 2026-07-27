- [x] Add an exact-match durable repository/coordinator operation that clears a
      recorded `latest_response_id`.
- [x] Invalidate a timed-out proxy-injected reattach anchor from the eventless
      watchdog, on both the retire and quarantine paths.
- [x] Leave a client-supplied `previous_response_id` untouched.
- [x] Report the dropped continuation anchor in the affected request's terminal
      error.
- [x] Classify a surviving sibling by downstream-visible progress, not by
      queue membership or a bare `response_id`.
- [x] Fail only the expired requests and quarantine the bridge when such a
      sibling exists; keep the existing retirement path otherwise.
- [x] Fall back to the request's own API key when a reader-driven failure writes
      its request log.
- [x] Add regressions for anchor invalidation, the concurrent-anchor guard, the
      client-anchor guard, sibling survival plus quarantine, and API-key
      attribution; prove the behavior tests fail on the unmodified watchdog.
- [x] Keep the pre-existing eventless-watchdog retirement regression passing
      unchanged.
- [x] Run focused unit suites, lint, format, type checks, and strict OpenSpec
      validation.
