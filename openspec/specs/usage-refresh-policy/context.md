# Usage Refresh Policy Context

## Purpose

This context explains how codex-lb derives an account's usage and status, and
how to diagnose disagreements between codex-lb and Codex Desktop or the Codex
CLI quota pill.

codex-lb treats `/wham/usage` as the source of truth for account usage. Other
OpenAI account surfaces can display reset state earlier than `/wham/usage`,
especially during team reset windows, so the dashboard can temporarily show an
account as `rate_limited` even when Codex Desktop says the quota has reset.

## September 2026 Pro entitlements

The September 29 Pro tiers and grandfathered Pro allowances cannot be converted
to absolute credits from plan labels or subscription prices. The observed
`pro`, `prolite` and `promax` identifiers retain their identities and upstream
window percentages; their estimated capacity and remaining credit quantities
are null until an authoritative source provides an allowance. See the
[requirements](spec.md) and [official Pro tier guidance](https://help.openai.com/en/articles/9793128-about-chatgpt-pro-tiers).

For example, a Pro Max account with 25% monthly usage still displays 75%
remaining and its upstream reset, without claiming a numeric credit balance.
Mixed pools use a common remaining-percentage basis for capacity-dependent
selection. A genuine known zero allowance remains distinct from an unknown
allowance. Whole-pool credit forecasts and legacy Pro-account purchase
equivalents are unavailable when the required capacities are unknown.

Successful complete usage responses can explicitly supersede an omitted short
window. Missing rate-limit objects, incomplete windows and failed refreshes do
not erase earlier quota evidence; independent cooldowns remain enforced. No
schema migration or subscription-price setting is required.

## Upstream Usage Source

codex-lb refreshes account usage by calling:

```http
GET https://chatgpt.com/backend-api/wham/usage
```

The call is made per account on the configured refresh tick, which defaults to
60 seconds. The client lives in
[`app/core/clients/usage.py`](../../../app/core/clients/usage.py), and the
scheduler lives in
[`app/core/usage/refresh_scheduler.py`](../../../app/core/usage/refresh_scheduler.py).

## Status Derivation

The fetched usage is fed through
[`apply_usage_quota`](../../../app/core/usage/quota.py), which derives account
status from `primary_window.used_percent`:

- `secondary_used >= 100`, regardless of `primary_used`: `QUOTA_EXCEEDED`
- `used_percent >= 100` on the primary rate-limit window: `RATE_LIMITED`
- `used_percent < 100`: `ACTIVE`

There is no manual reset step inside codex-lb. Recovery is driven by the next
refresh tick that observes a sub-100 value from `/wham/usage`.

## Why Codex Settings Can Disagree

Codex Desktop's Settings -> Account view and `/wham/usage` are fed by different
OpenAI-side data sources:

- `/wham/usage` exposes the rate limiter's internal counter. It updates lazily,
  typically on the next chargeable request through that account, or when its
  internal window crosses `reset_at`.
- Settings -> Account is fed by a separate account/quota view that often picks
  up team-side reset events earlier.

During a reset window it is normal for Settings -> Account to show the reset
state while `/wham/usage` still returns `used_percent: 100` for a short period
afterwards. codex-lb mirrors `/wham/usage` during that window, so the account
stays `RATE_LIMITED` or `QUOTA_EXCEEDED` until upstream catches up.

## Limit Warm-Up Exhaustion Threshold

Reset-confirmed limit warm-up compares the usage sample from before a refresh
with the sample written after that refresh. The pre-refresh sample must be at
or above the configured exhausted threshold, the post-refresh sample must be
below `100`, and `reset_at` must move forward.

The exhausted threshold defaults to `99.0` because some upstream usage payloads
plateau at 99 percent for windows that are practically exhausted. This avoids
missing reset-confirmed warm-ups for those accounts while keeping the reset
confirmation requirement intact. Operators who want the historical strict
behavior can set the threshold to `100.0`.

## Operational Notes

- Wait first. The next request through that account usually wakes the upstream
  rate limiter; codex-lb auto-recovers on the next refresh tick after the
  upstream payload changes.
- The dashboard Force Probe action fires one minimal `responses.create` against
  the selected account and immediately refreshes its usage. An accepted 2xx
  probe also contributes to that replica's probing-health recovery streak;
  non-2xx results do not restore routing health. Settlement reloads and
  normalizes weekly/monthly and zero-primary-capacity usage like ordinary
  routing and is discarded when newer replica-local runtime activity arrives
  during that snapshot load.
- Do not manually flip the codex-lb account state to `ACTIVE` while
  `/wham/usage` still reports the account as fully used. That only masks the
  upstream state and can route traffic back to an account that the upstream
  limiter will reject.

## Verification Example

To confirm that the disagreement is upstream rather than codex-lb's mirror,
call `/wham/usage` directly with the same account token codex-lb is using:

```bash
ACCESS_TOKEN=...
ACCOUNT_ID=...   # chatgpt-account-id UUID, not codex-lb's id

curl -s https://chatgpt.com/backend-api/wham/usage \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "chatgpt-account-id: ${ACCOUNT_ID}" \
  -H "Accept: application/json" | jq '.rate_limit'
```

If `primary_window.used_percent` is still `100` here while Settings -> Account
shows the account as reset, codex-lb has nothing fresher to mirror. The account
is inside the upstream propagation window, and the practical fix is to wait or
use the Force Probe action. Check its `probe_status_code`: a non-2xx response
does not count as evidence that the account is healthy.

## Related Work

- [#676 - initial bug report on `/wham/usage` vs. Settings UI divergence](https://github.com/Soju06/codex-lb/issues/676)
- [#677 - dashboard per-account force-probe action](https://github.com/Soju06/codex-lb/issues/677)

## Working-day weekly forecast

The weekly pace schedule already defines which weekdays can consume quota.
Forecast simulation applies that same calendar to burnable intervals, then
maps the resulting burn duration back to wall-clock time. A Friday forecast
that needs two working days to deplete therefore lands on Tuesday rather than
Sunday when Saturday and Sunday are excluded.

Non-working days do not add projected burn, but they remain part of the
operator-visible elapsed depletion time. An empty working-day set intentionally
preserves the earlier all-days behavior, so this fork customization adds no
required configuration or migration.

## Authorization evidence and server-directed waits

Bare usage HTTP 402/404 can reflect payment or endpoint failures without proving account termination. They leave the local account status unchanged; explicit account deactivation codes/messages remain authoritative. Explicit token/session revocation requires reauthentication and uses the existing guarded credential failure path. Historical deactivated slots are not automatically repaired by this change.

Both usage transports, including reset-credit consumption, observe numeric and HTTP-date Retry-After as a minimum wait, with the existing exponential delay as fallback. A final usage error carries its remaining wait to the process-local refresh cooldown so a scheduler tick cannot immediately start a new attempt series. For example, a 503 with Retry-After: 60 postpones both a client retry and, if attempts are exhausted, the next polling cycle. Waits remain cancellable and the existing retry count remains bounded. Cooldowns do not persist across service restarts or coordinate replicas.
