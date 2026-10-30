## Context

Unknown Pro capacities exposed a misleading partial-pool donut. The operator
has chosen to remove both pooled quota charts instead of replacing them.

## Goals / Non-Goals

Remove the weekly and 5-hour chart panels. Preserve existing account quota
information, summaries, request logs, and the separate weekly pace card when
eligible. Other charts, APIs and pricing are outside this change.

## Decisions

Remove the `UsageDonuts` render branches from the dashboard. Keep the conditional
weekly pace card as a standalone card without a blank chart column. Delete
components and rendering tests that are exclusively owned by the removed
panels. Keep unrelated data contracts and charts unchanged.

## Verification and rollout

Regression tests cover both complete and mixed-capacity pools and the surviving
dashboard content. Inspect the built dashboard, run frontend checks, synchronize
and validate OpenSpec, and deploy the corrected static assets. The server reads
index.html per request, so the frontend-only rollout does not need a restart.
