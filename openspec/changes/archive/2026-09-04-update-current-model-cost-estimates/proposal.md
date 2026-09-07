## Why

Astra currently has no API cost estimate. The proxy also loses cache-write usage, and stored historical costs prevent a pricing-table update from repairing dashboard totals.

## What Changes

- Refresh supported text-model API rates and aliases from official pricing verified September 4, 2026, including Astra and Daybreak.
- Preserve and price reported cache writes through Responses HTTP, WebSocket, compact, request logs, and API-key settlement.
- Keep models without published API rates, including Spark, unpriced.
- Add a dry-run-first historical cost repair command using retained usage, preserving custom model-source costs and rebuilding affected aggregates.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-keys`: current model rates, cache-write accounting, and historical estimate repair.
- `responses-api-compat`: preserve reported cache-write usage in settlement and logs.

## Impact

Shared pricing, usage parsing, request logging, API-key accounting, and a nullable request-log database column. Existing dashboard components consume corrected costs without layout changes. Historical cache writes that were never stored cannot be reconstructed.
