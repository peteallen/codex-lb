# Proxy Runtime Observability Context

## Purpose and Scope

This capability defines what operators should be able to see in the live server console while debugging proxy traffic.

See `openspec/specs/proxy-runtime-observability/spec.md` for normative requirements.

## Decisions

- **Timestamps are always on:** timestamped console logs are a baseline operator need, not a debug-only feature.
- **Request tracing is opt-in:** outbound request summary and payload tracing remain configurable because payload logs can be noisy or sensitive. Since issue #1340 phase 1 the switch is the single `CODEX_LB_TRACE` comma-separated channel list (`shape`, `shape_raw_cache_key`, `payload`, `service_tier`, `upstream_summary`, `upstream_payload`); empty default = all off. It is an incident-debugging knob for interactive use only.
- **Error logs must be correlated:** request id, endpoint, status, code, and message are the minimum useful fields for debugging 4xx/5xx failures.
- **Prewarm observability is outcome-only:** the Codex HTTP-bridge prewarm canary experiment finished, so its bucket/cohort dimensions were retired (issue #1340 phase 4). The `codex_lb_http_bridge_prewarm_total` counter is labelled by `outcome` only, request logs record `prewarm_status` / `prewarm_latency_ms` (statuses: `not_applicable`, `skipped`, `success`, `timeout`, `error` — `canary_miss` no longer occurs), and the legacy `prewarm_canary_bucket` / `prewarm_eligible_reason` request-log columns stay declared but unwritten for one release for rolling-upgrade safety; the Alembic drop revision ships next release (see the next-release queue in `openspec/specs/deployment-installation/context.md`).

## Operational Notes

- Use request ids to correlate inbound proxy logs, outbound upstream traces, and client-visible failures.
- Prefer summary tracing in normal debugging sessions; enable payload tracing only when the exact normalized outbound request matters.
- For direct compact `5xx` failures, look for `proxy_compact_failure` alongside `upstream_request_complete`; together they show the compact failure phase, failure detail, exception type, retry metadata, and affinity source.

## Throughput anchor semantics

Normal token-producing rows preserve the historical product meaning of TPS:
persisted output tokens divided by generation time after TTFT. Earlier
first-upstream-event and response-created timings remain transport diagnostics
and do not replace TTFT when it exists, even when all three fields are present.

Tool-only turns may have positive persisted output tokens but no visible-token
TTFT. Those rows can contribute throughput from `response.created` to
completion, and the recent-request table labels the corresponding timing as an
approximate first-output value rather than calling it TTFT.
`first_upstream_event` is never a throughput anchor because transport activity
may precede response creation. Missing TTFT and response-created timing leaves
TPS blank for a request row and excludes that row from the daily median sample.

For example, a 1,000 ms request with 200 output tokens and 200 ms TTFT reports
250 TPS regardless of a 100 ms response-created or 50 ms first-upstream-event
timing. The same row without TTFT uses response-created and reports the 200 ms
timing as approximate first output.
