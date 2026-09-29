## Context

The latest weekly sample can coexist with a monthly record from a previous quota
regime. Pro-family support made that historical monthly record applicable without
checking whether a newer complete weekly/short-window observation superseded it.
The Force Probe HTTP request also includes max_output_tokens, which the upstream
Codex endpoint rejects. Its UI notification ignores the returned upstream status.

## Goals / Non-Goals

Show the current quota window consistently and make probe outcomes accurate.
Do not clear real quota exhaustion, redeem credits, alter billing/history, change
retry policy or change the probe response schema.

## Decisions

Use a shared pure predicate over typed usage rows. Monthly data is superseded by
a primary or secondary row with real quota metadata, an observed percentage, and
a timestamp more than the existing same-fetch margin later. Missing timestamps,
absence markers and incomplete samples cannot supersede it. Apply the predicate
in account mapping, long-window selection (including probes/recovery), and usage
summary aggregation. Retain stored rows so history and rollback remain intact.

Remove max_output_tokens from the probe body, matching the main proxy's existing
unsupported-field policy. Retain the single-dot instruction, streaming, store=false
and existing request timeout. Keep upstream status in the response and show a
failure notification for non-2xx or network failure, while invalidating quota queries.

## Risks / Trade-offs

A nearby sibling can belong to the same fetch, so retain the five-second margin.
Incomplete observations must not erase exhausted quota. Cover both transition
directions, no-data markers, real rate limits and genuine monthly-only Pro plans.

## Rollout

Run targeted backend and frontend regressions, lint/type checks, build and strict
OpenSpec validation. Verify before/after dashboard rendering. Back up the local
deployment, commit, fast-forward the live checkout and restart the service to load
backend changes. Verify readiness and the affected account through the live API.
