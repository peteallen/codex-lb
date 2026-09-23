## Why

Request-history retries share a request ID, but the dashboard uses that ID as a React row key. Refreshing the table can retain duplicate rows and display timestamps out of order, making real failures harder to diagnose.

## What Changes

- Give each displayed request-log attempt stable row identity across refreshes.
- Preserve every returned attempt exactly once and in API order when polling or changing pages.
- Add a regression covering repeated request IDs, refreshed results, and removed attempts.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `proxy-runtime-observability`: Request history preserves individual retry attempts and server ordering during refresh.

## Impact

Dashboard request-history rendering and its regression coverage. This change does not modify proxy retry behavior or establish the cause of upstream model rejections.
