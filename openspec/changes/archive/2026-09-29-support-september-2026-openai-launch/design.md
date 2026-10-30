## Context

The live catalog already advertises GPT-6.1 Sol and Astra Ultrafast per account. Prices are a local API-equivalent snapshot. Upstream usage exposes plan strings, window percentages and resets, but no verified absolute allowance distinguishing new and grandfathered Pro entitlements.

## Goals / Non-Goals

**Goals:** Accurate new-model and tier cost accounting, enforced Ultrafast controls, routable Pro Max accounts, and honest unknown-capacity reporting with complete quota-window semantics.

**Non-Goals:** Changing model defaults, inventing plan allowances, inferring Ultrafast access from generic Pro membership, production deployment, subscription changes, or automatically rewriting cost history.

## Decisions

1. Extend the existing ModelPrice calculator with explicit Astra Ultrafast rates and add GPT-6.1 Sol/Sol/Luna prices. Keep exact model identity, snapshot aliases, cache-write clamping, long-context thresholds and authoritative returned tiers. Test API-key reservation and settlement through existing product paths.
2. Add Ultrafast to the existing key CRUD and dashboard tier selections. Continue using authoritative per-account catalogs for tier eligibility; do not add a permissive bootstrap entitlement or silently downgrade tiers.
3. Recognize only observed Pro-family values: pro, prolite, promax. Preserve raw values. General Pro-model compatibility does not imply Ultrafast compatibility.
4. Treat Pro-family absolute allowance as unknown. Existing numeric legacy Pro allowances cannot distinguish September 29 entitlements or October 29 grandfathering. Expose unknown credit quantities as null and preserve reported percentages/resets. Do not add guessed price-based ratios, settings, or date-based guesses.
5. When a candidate pool includes unknown long-window capacity, use a common remaining-percentage basis for every candidate in capacity-dependent selection. Preserve absolute capacity weighting for fully known pools. Unknown allowance must not become zero, free capacity, or an unrelated legacy Pro value. Existing health, quota, owner-binding and service-tier filtering remain authoritative.
6. Retain monthly and weekly usage independently of knowing its absolute capacity. A complete newer usage refresh can supersede a missing short window, but an absent/incomplete/error payload cannot erase quota evidence. Cross-replica rate-limit cooldowns remain enforced.

## Risks / Trade-offs

- Relative percentages do not represent equal absolute work across tiers. This is intentional until authoritative capacities exist; unknown credit amounts remain visibly unknown.
- Nullable capacity/credit summaries require coordinated backend/frontend schemas and tests, including mixed pools.
- Removing stale five-hour evidence must depend on authoritative complete refresh data, never merely elapsed time or a plan label.
- New prices affect API-key quota admission/settlement; historical repair intentionally does not rewrite quota counters.

## Migration Plan

No schema migration or production changes. After review and normal deployment, use the existing cost-repair dry run to inspect retained GPT-6 rows before any separately authorized apply. Rolling back code restores previous behavior; no persisted plan identity is rewritten.

## Sources

Verified September 29, 2026: https://developers.openai.com/api/docs/pricing ; https://developers.openai.com/api/docs/models/gpt-6.1-sol ; https://learn.chatgpt.com/docs/pricing ; https://help.openai.com/en/articles/9793128-about-chatgpt-pro-tiers . API rates are not included subscription allowances.
