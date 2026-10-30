## Why

OpenAI's September 29 launch adds GPT-6.1 Sol, Astra Ultrafast, and revised Pro entitlements. The fork discovers the catalog entries, but missing prices undercount API-key settlement and an unrecognized `promax` plan receives zero routing capacity.

## What Changes

- Price GPT-6.1 Sol, GPT-6 Sol, and GPT-6 Luna at current published API rates, including cache writes, Fast/Flex, and long context; price Astra Ultrafast explicitly.
- Allow API keys to enforce Ultrafast through backend and dashboard controls while preserving upstream model/account entitlement checks.
- Recognize Pro Max and handle unknown absolute subscription capacity without excluding eligible accounts or presenting guessed allowances as known.
- Preserve authoritative weekly-only usage and remove superseded five-hour exhaustion evidence when a complete newer usage response omits that window.
- Cover externally observable routing, key CRUD, reservation/settlement, and reporting with regressions; document historical cost repair as an explicit operational step.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-keys`: Current GPT-6 family pricing, Astra Ultrafast cost accounting, and enforced tier persistence.
- `usage-refresh-policy`: Pro-family plan recognition, unknown absolute allowances, and authoritative absent-window handling.
- `account-routing`: Fair selection when capacity is unknown and preserved quota/entitlement constraints.

## Impact

Changes affect the existing pricing calculator, API-key schemas/service/dashboard, plan normalization, usage aggregation and account selection. No new model default, environment setting, provider credential, database migration, production restart, or automatic historical repair is required.
