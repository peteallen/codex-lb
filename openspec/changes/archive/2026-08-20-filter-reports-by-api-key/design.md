## Context

Reports currently sends a local filter state through `GET /api/reports`, and the backend applies account, model, and user-agent predicates to every aggregate over `request_logs`. Each request log already stores an indexed nullable `api_key_id`. The dashboard already exposes API-key records and a reusable multi-select control, so the feature needs no new table, migration, or settings surface.

The work targets v1.23.0 in an isolated branch because that release changes the Reports UI and reporting queries while the deployed v1.22 checkout contains unrelated uncommitted proxy work.

## Goals / Non-Goals

**Goals:**

- Let operators select one or more current API keys and see every Reports metric recomputed for those keys.
- Keep current, previous-period, daily, speed, and distribution aggregates on one consistent filter contract.
- Reuse existing API-key catalog and filter UI behavior, including removable stale values.
- Preserve existing behavior when no API key is selected.

**Non-Goals:**

- Adding an API-key distribution chart or returning API-key groupings in the Reports response.
- Filtering specifically for unauthenticated traffic with a null API-key ID.
- Persisting Reports filters in the URL or browser storage.
- Restoring a deleted API key to the option catalog after a page reload.

## Decisions

### Use repeatable stable IDs in the existing Reports request

`GET /api/reports` will accept repeatable `api_key_id` query parameters. The frontend state will use `apiKeyId: string[]`, serialize each selected ID separately, and treat an empty array as an omitted filter. This matches the endpoint's existing repeatable `account_id` convention and avoids using mutable display names as query identity.

Alternative considered: a single API-key selector. Multi-select is preferred because account filtering already supports unions and operators may need to analyze one client's rotated or related keys together.

### Apply one predicate through every report aggregate

The repository's shared report-condition builder and daily statement helpers will accept the selected IDs and add `RequestLog.api_key_id IN (...)` when the list is non-empty. The service will pass the same list into current and previous summaries, earliest-activity comparison eligibility, daily totals and medians, and each distribution. Multiple selected IDs therefore use OR semantics with one another and remain ANDed with date, account, model, user-agent, and normal-traffic predicates.

Alternative considered: filtering only the final response. That cannot produce correct totals, medians, comparison eligibility, or percentages and is rejected.

API-key-filtered conversation counts follow the existing filtered Reports contract: they use retained raw request logs because the v1.23 conversation presence satellite has no API-key dimension. This is exact while the underlying rows exist, but operators who opt into request-log retention can see older filtered conversation counts fall away even though the unfiltered conversation rollup survives. Adding an API-key dimension to that permanent satellite would require a migration and a larger rollup-cardinality decision, so it remains outside this focused filter change.

### Reuse the dashboard API-key catalog

The Reports page will load `listApiKeys` with the existing React Query key `['api-keys', 'list']`. Options will display `name · keyPrefix` and use the stable ID as their value. The shared cache avoids duplicate calls when another API-key surface has already loaded the catalog, and existing mutations already invalidate that key.

The catalog contains inactive keys, which is desirable for historical reporting. A deleted key disappears from the catalog, but the shared multi-select preserves an already-selected unknown value as a removable stale selection for the rest of the page session. It will not silently clear the predicate and broaden the report.

Alternative considered: adding API-key options to every Reports response. That would expand the reporting schema and run another historical grouping query solely to populate a control; the existing catalog is sufficient for the requested behavior.

### Keep filter-option queries scoped by the selected keys

The Reports page's secondary catalog request will clear model and user-agent as it does today but retain selected API-key IDs. As a result, model and user-agent options continue to describe the chosen account/API-key scope without feeding either facet's own selection back into itself.

## Risks / Trade-offs

- [The API-key list includes keys with no activity in the chosen date range] → This matches the existing all-account catalog behavior and makes historical/inactive keys discoverable; selecting an unused key correctly returns an empty report.
- [Deleting a key removes its friendly label after reload while logs retain its ID] → During the current session, stale-selection behavior preserves and exposes the raw ID; after reload, operators can no longer newly select a deleted key through this control.
- [A missed repository call could produce internally inconsistent report cards] → Backend regression coverage will seed matching and non-matching keys and assert summary, previous-period comparison, daily, speed, and distribution outputs through the public Reports API/service path.
- [Loading API-key options adds another page dependency] → Reuse the shared React Query cache, show a dedicated non-blocking error, include it in Retry, and continue rendering report data when only the catalog fails.
- [Filtered conversation history can outlive its raw API-key attribution] → Preserve the existing raw-bound filtered Reports behavior and state that retention boundary in the `query-caching` contract; a future rollup-dimension change can remove the limitation without changing this filter API.

## Migration Plan

No database or configuration migration is required. Deploy the backend and bundled frontend together. Rollback removes the optional query parameter and control; existing clients that omit `api_key_id` remain unaffected in either direction.

## Open Questions

None.
