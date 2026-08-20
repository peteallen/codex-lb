## Why

Operators can currently narrow Reports by account, model, user agent, and date, but cannot isolate the cost, usage, latency, and error totals produced by a specific downstream client key. API-key filtering makes the existing Reports metrics usable for per-client investigation and spend analysis.

## What Changes

- Add a visible multi-select API-key filter to the Reports page.
- Allow `GET /api/reports` to accept repeated API-key IDs and apply them consistently to every current-period, comparison-period, daily, and distribution aggregate.
- Load API-key labels from the existing dashboard API-key catalog and keep an empty selection equivalent to all traffic.
- Preserve selected IDs that disappear from the catalog as removable stale selections so a deleted key is never silently broadened to all traffic during the current page session.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontend-architecture`: Extend the Reports filter contract and reports endpoint behavior to support filtering by one or more API keys.
- `query-caching`: Keep API-key-filtered conversation counts on the existing raw-retention-bound path used by every filtered Reports read.

## Impact

- Reports API route, service, and request-log aggregate queries.
- Reports React filter state, API request serialization, API-key option loading, error states, and translations.
- Backend and frontend regression coverage; no database migration or new setting.
