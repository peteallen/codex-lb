## Why

The dashboard's `Account burn projection (5h/7d)` summary card adds a dense, hard-to-interpret estimate to the primary overview. Hiding it through a new default would not work reliably because existing browsers can have the old visibility preference persisted as enabled.

## What Changes

- The dashboard no longer constructs or renders the account burn projection summary card.
- Appearance settings no longer offer a toggle that can re-enable the removed card, and the obsolete local preference is no longer read or written.
- Projection-backed depletion indicators and the separate weekly credits pace surface remain available; the dashboard projection API and query are unchanged.
- Dashboard and settings tests assert the card and toggle stay absent.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `frontend-architecture`: the dashboard overview MUST omit the account burn projection card and its Appearance setting without removing other projection-backed surfaces.

## Impact

This is a frontend-only presentation change. It removes obsolete card-building code, preference state, settings UI, and translations. Backend routes, schemas, calculations, migrations, account data, and request routing are unchanged.
