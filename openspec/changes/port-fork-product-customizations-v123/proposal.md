## Why

The fork has a small set of operator-facing improvements that remain useful on
the v1.23 baseline: clear fork identity, working-day-aware weekly forecasts,
calendar-range dashboard inspection, and throughput visibility for tool-only
turns. The older patches were written against pre-v1.23 dashboard and timing
contracts, so they need a focused semantic port rather than a commit replay.

## What Changes

- Brand the dashboard, sign-in screen, document title, and repository link as
  Pete's fork.
- Make weekly forecast depletion consume configured working days, while keeping
  v1.23's localized dashboard copy unchanged.
- Add a Custom calendar range to the Dashboard overview and carry its exact
  half-open window through rollup-aware activity, trend, and conversation reads,
  with localized controls and local-calendar trend buckets.
- Preserve TTFT-based throughput for visible-token responses while using
  `response.created` as the output anchor for tool-only turns.

## Capabilities

### Modified Capabilities

- `frontend-architecture`: expose fork identity and a custom Dashboard overview
  range without changing request-log filters or quota projections.
- `usage-refresh-policy`: weekly forecast burn and depletion MUST skip configured
  non-working days.
- `proxy-runtime-observability`: throughput medians and recent-request display
  MUST include output-bearing tool-only turns when response-created timing is
  available, without changing the TTFT anchor for normal turns.

## Non-Goals

- The Reports custom date picker, Responses wire-shape preservation, and beta
  import-order fix are intentionally not ported here.
- No database schema or migration changes are required.
- Existing v1.23 localized weekly-pace copy is retained, and new custom-range
  and approximate-timing copy follows the same locale catalogs.

## Impact

The change touches Dashboard API/service/repository and frontend Dashboard
components, request-log timing mappers/schemas, Reports speed aggregation, and
focused regression tests. Preset Dashboard ranges and unfiltered reports keep
their existing behavior.
