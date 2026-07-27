- [x] Expose the first-upstream-event and response-created latencies on
      request-log API entries and in the dashboard schema.
- [x] Anchor throughput at first upstream event, falling back to
      `response.created` then TTFT, in both the daily report aggregate and the
      per-request dashboard table.
- [x] Count total output tokens in the numerator so it agrees with the window.
- [x] Keep TTFT meaning time-to-first-visible-token; render an approximate
      first-output value only when TTFT is absent.
- [x] Update the reports median regression for the new semantics and add a
      tool-only turn with no TTFT.
- [x] Update the dashboard TPS test and add a no-visible-token fallback test.
- [x] Run backend lint, format, type checks and affected suites; run frontend
      typecheck, lint, tests and build.
- [ ] Capture before/after dashboard screenshots for the simplicity gate.
