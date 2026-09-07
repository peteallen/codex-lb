## Context

Prices are centralized in `app/core/usage/pricing.py`. Dashboards and reports sum persisted request costs. Upstream cache-write counts are currently ignored. Existing local work in reports and proxy lifecycle code must be preserved.

## Goals / Non-Goals

**Goals:** verified current text-model prices, accurate reported cache-write accounting, and consistent retained historical estimates.

**Non-Goals:** infer unreported cache writes, invoice reconciliation, ChatGPT credit multipliers, regional uplifts, unsupported Batch routing, multimodal price redesign, live deployment, or automatic fetching of mutable price pages during requests.

## Decisions

- Use official API pricing verified 2026-09-04: https://developers.openai.com/api/docs/pricing and https://developers.openai.com/api/docs/models/gpt-6-astra . Add published text models and Daybreak aliases; preserve existing legacy rates. Remove Spark's speculative Codex alias because its API rate is unpublished.
- Add a nullable `cache_write_tokens` request-log column and typed usage field. Price reported writes at 1.25 times the effective uncached rate for Astra and GPT-5.6. Include the premium in the existing input-cost segment, preserving the dashboard response shape.
- Clamp cache reads first, then writes to the remaining input count. Missing writes mean zero known writes, never an inferred charge. Use the same counts for completed API-key settlement and request costs.
- Keep migration DDL-only. Supply a dry-run-first repair command with a model/date scope. Repair known-model retained rows and mirror cost deltas into folded hourly, demand, account, and API-key aggregates under the existing fold-state lock. Never rebuild aggregates from pruned raw history. Preserve custom model-source prices and existing API-key enforcement counters.

## Risks / Trade-offs

- Historical cache writes were discarded → explicitly report that repaired historical estimates cover retained usage only.
- Rate changes after this verification → keep the verification date and official sources alongside the central table; Sol promotional pricing is published through at least November 21, 2026.
- Folded history outlives raw rows → only apply differences for retained rows; never erase aggregate history.

## Migration Plan

Apply the nullable-column migration, deploy the code, preview historical repairs, then apply the selected repair. Back up the database before applying repairs. Rolling back code remains compatible with the additive column; migration downgrade drops only that column. Live deployment is separate from this source update.
