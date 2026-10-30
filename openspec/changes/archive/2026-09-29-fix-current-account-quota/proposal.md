## Why

A Pro account with exhausted weekly quota displays an obsolete monthly balance
from an earlier quota regime. Force Probe also sends an unsupported parameter,
receives HTTP 400, and displays a success notification despite upstream rejection.

## What Changes

- Select current monthly quota consistently across account views, routing,
  probe settlement, recovery and summary totals. A newer complete non-monthly
  observation supersedes historical monthly data without deleting history.
- Remove the unsupported probe request field and display upstream probe failures
  as failures, while still refreshing account data.
- Preserve genuine upstream quota limits and normal recovery conditions.

## Capabilities

### Modified Capabilities
- `usage-refresh-policy`: current monthly-window selection and valid probes.
- `account-quota-presentation`: quota displays follow the current window.
- `frontend-architecture`: probe notifications reflect upstream outcomes.

## Impact

Backend quota readers, the account probe request, and frontend probe notifications.
No schema migration, quota reset, historical-row deletion or automatic credit redemption.
