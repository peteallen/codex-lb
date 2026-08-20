- [x] Add a stock regression reproducing the oversized current-tool-output
      WebSocket rejection before implementing the fallback.
- [x] Classify an oversized turn as fallback-eligible only for a client-supplied
      `previous_response_id` with an all-current-tool-output input whose projected
      frame exceeds the websocket budget.
- [x] Exclude proxy-injected reattach anchors from eligibility.
- [x] Defer the websocket size check until eligibility is known, and keep the
      API-key reservation release on rejection.
- [x] Relay the eligible turn over upstream HTTP as an owned per-connection task,
      outside the shared socket's pending set.
- [x] Preserve downstream websocket identity: event shapes, Codex keepalives while
      pre-created, and `upstream_transport=http` in the request log.
- [x] Hand the resolved previous-response owner and owner-lookup session id to the
      HTTP streamer instead of re-deriving them from headers.
- [x] Attach the resolved owner-lookup session id to owner-unavailable request
      logs.
- [x] Surface the owner's original pre-visible error for a hard owner-bound
      continuation with no verified fresh replay body.
- [x] Hold the terminal frame until the stream drains; settle gate, reservation
      and task on disconnect, `response.cancel`, and connection teardown.
- [x] Keep the downstream idle-close from firing while a fallback relay owns the
      turn.
- [x] Prove the regression and the owner-error regression fail on the unmodified
      v1.22 code.
- [x] Run focused unit/integration suites, lint, format, type checks, and strict
      OpenSpec validation.
