## Why

Usage retries ignore upstream waiting instructions, explicit revocation is not recognized everywhere, and ambiguous usage failures can falsely deactivate healthy local account slots. Authorization denials must not become generic transient fallback signals.

## What Changes

- Honor numeric and HTTP-date Retry-After on direct and routed usage requests, including reset-credit consumption.
- Recognize explicit token revocation as requiring reauthentication and avoid forced-refresh retries for terminal credentials.
- Fail closed on unknown HTTP 403 responses while preserving explicitly recognized quota and trusted-access behavior.
- Remove bare usage HTTP 402/404 as deactivation evidence.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `usage-refresh-policy`: server-directed waits and evidence-based terminal account handling.
- `responses-api-compat`: terminal authorization handling before generic retry/failover.

## Impact

Usage clients/updater, shared terminal code classification, proxy authentication retry gates, regression tests. No settings, dependencies, migrations, routing strategy changes, or automatic account reactivation.
