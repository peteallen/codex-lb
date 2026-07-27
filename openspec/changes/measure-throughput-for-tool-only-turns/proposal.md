## Why

TTFT is defined as time to the first *client-visible* token, and the dashboard
uses it as the sole anchor for generation throughput. That definition is correct
for chat-shaped traffic and wrong for agentic traffic.

An agentic Codex turn is usually hidden reasoning followed by a tool call. It
emits no client-visible token, so no TTFT is recorded, so no throughput is
computed. Measured on a real 200,904-request deployment: only 11.5% of requests
had TTFT, and TPS was computable for the same 11.5%. Restricted to successful
requests that actually generated tokens, 82,322 had no TTFT at all -- 73,316 of
those had spent reasoning tokens.

The signal needed to fix this is already recorded.
`latency_first_upstream_event_ms` is populated for ~100% of current requests but
is not exposed by the request-log API, so no consumer can use it.

## What Changes

- Expose `latency_first_upstream_event_ms` and `latency_response_created_ms` on
  request-log API entries.
- Anchor generation throughput at the first upstream event, falling back to
  `response.created` and then TTFT. Measured coverage on recent real traffic:
  18.4% -> 96.6%.
- Count total output tokens in the throughput numerator. Reasoning time lies
  inside the new window, so excluding reasoning tokens while spanning the
  reasoning phase would understate throughput on exactly the turns that reason
  most. This changes the metric's meaning from visible throughput to total
  generation throughput.
- Keep TTFT's definition unchanged. Where it is absent, show time to first output
  marked as approximate, so a tool-only turn stops rendering as `--` without the
  two meanings being conflated.

## Impact

- Affected capability: `proxy-runtime-observability`.
- Dashboard-visible: the TPS column populates for nearly every request instead of
  a small minority, and the TTFT column shows an approximate value where no
  visible token exists.
- Reported median TPS drops (72.6 -> 42.2 tok/s on the measured deployment)
  because the metric now includes reasoning-heavy tool turns that were previously
  excluded from the sample entirely. This is a truer figure, not a regression.
- No migration and no new setting: every column involved already exists and is
  already populated.
