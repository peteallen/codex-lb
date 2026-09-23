## Why
Repeated overloads from one account continue surfacing because overload escalation resets as soon as its current cooldown expires. A retry after 30 seconds therefore starts another 30-second hold; occasional successes also erase escalation. In the observed incident, all 16 overload errors since 04:00 UTC came from openai8 across three models.

## What Changes
- Retain overload recurrence history for 15 minutes after the latest overload, independent of cooldown expiry and intervening successes.
- Escalate recurrent cooldowns from 30 seconds through 60, 120, 240, and 300 seconds; keep the existing automatic recovery and ownership rules.
- Verify real HTTP selection across repeated failed probes and healthy alternate accounts.

## Capabilities
### Modified Capabilities
- `proxy-admission-control`: Bounded overload cooldown escalation survives failed recovery probes.

## Impact
Runtime load-balancer accounting and tests only; no persisted account status, settings, or schema changes.
