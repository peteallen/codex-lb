# Hide Account Burn Projection Context

## Purpose and scope

The five-hour/seven-day account burn estimate is being removed from the dashboard's top metric grid to make the overview easier to scan. This change also removes the Appearance toggle that previously controlled that card.

## Decision and alternatives

The card is omitted unconditionally instead of changing the preference default. A default-only change would leave it visible for users whose browser already persisted `true`, while keeping a toggle for a surface the product intends to hide would be misleading.

## Constraints and non-goals

- The backend dashboard projection contract remains unchanged.
- The dashboard continues fetching projection data because depletion indicators and the weekly credits pace surface still consume it.
- Account usage calculations, request routing, storage, and migrations are out of scope.

## Failure modes and edge cases

An old local-storage value may remain in a browser, but the application no longer reads it and it cannot make the card reappear. Removing the projection query would be a regression because other dashboard surfaces still depend on its response.

## Example

When an operator opens the dashboard after previously enabling the burn projection setting, the top grid shows Requests, Tokens, estimated cost, Conversations when available, and Error rate. It does not show `Account burn projection (5h/7d)`, and Appearance settings contain no control for it.

Normative behavior is defined in `specs/frontend-architecture/spec.md`.
