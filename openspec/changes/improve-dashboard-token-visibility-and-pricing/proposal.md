# Improve dashboard token visibility and pricing

## Why

Several usage surfaces show one aggregate token count even though codex-lb already records input and output separately. That hides the main driver of model cost. The dashboard refresh control also scrolls out of view during long investigations, and the built-in OpenAI pricing registry has drifted from the rates published on August 26, 2026.

## What Changes

- Keep total tokens as a stable headline and compatibility field while showing input and output token counts on usage-summary and usage-table readouts where the underlying data is available.
- Keep token-limit configuration, aggregate comparison charts, and authentication-token labels unchanged.
- Keep the dashboard range/refresh header visible below the global app header while the operator scrolls, including on narrow screens.
- Refresh the canonical built-in OpenAI model prices from the official OpenAI API pricing table, including applicable short-context, long-context, Standard, Flex, and Fast rates.
- Preserve the existing limitation that cache-write, regional-processing, Batch, and modality-specific image token accounting are not represented unless their usage dimensions are available to the current cost contract.

## Capabilities

### Modified Capabilities

- `frontend-architecture`: dashboard and usage-management readouts expose useful input/output token detail, and the dashboard refresh header remains reachable while scrolling.
- `api-keys`: built-in OpenAI cost accounting uses the currently published prices for models represented by the canonical registry.

## Impact

- Backend usage response schemas gain additive input/output token fields while retaining existing totals.
- Dashboard, account, API-key, and API detail readouts gain compact input/output labels.
- The pricing registry and focused pricing tests are updated; no database migration or new setting is required.
