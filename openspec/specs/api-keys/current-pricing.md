# Current API cost estimates

The estimates answer “what would the reported tokens cost at the published OpenAI API rate?” They are not ChatGPT subscription charges or credit usage. The registry is a verified snapshot, not a live pricing feed.

Sources fetched September 29, 2026:

- [Official API pricing](https://developers.openai.com/api/docs/pricing): Standard, Fast, Flex, and Ultrafast rates for the current flagship models.
- [GPT-6.1 Sol model details](https://developers.openai.com/api/docs/models/gpt-6.1-sol): 1,050,000-token context, long-context threshold and tier multipliers.
- [GPT-6 Sol model details](https://developers.openai.com/api/docs/models/gpt-6-sol): model identity and supported API tiers.
- [GPT-6 Luna model details](https://developers.openai.com/api/docs/models/gpt-6-luna): model identity and supported API tiers.
- [Astra model details](https://developers.openai.com/api/docs/models/gpt-6-astra): long context begins above 272,000 input tokens; input/cache rates double and output increases by 1.5 for the full request.
- [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching): cache writes are reported as `input_tokens_details.cache_write_tokens` and cost 1.25 times ordinary input for GPT-5.6 and later.

The September 29 Standard short-context rates are `$2/$0.10/$10` per million input/cached-input/output tokens for GPT-6.1 Sol, `$2/$0.20/$10` for GPT-6 Sol, and `$0.10/$0.01/$0.50` for GPT-6 Luna. Cache writes are 1.25 times the applicable input rate. Above 272,000 input tokens, input and cache rates double and output is multiplied by 1.5 for the full request. Fast is twice Standard and Flex is half Standard.

Astra Ultrafast is a separate API tier at `$60/$6/$300` per million short-context input/cached-input/output tokens and `$120/$12/$450` above the long-context threshold. Ultrafast cache writes are 1.25 times the applicable input rate. Fast API rates for Astra and GPT-5.6 are twice Standard; ChatGPT's subscription usage multipliers do not apply to API estimates. GPT-5.6 Sol's current promotional API rate is published through at least November 21, 2026. Spark has no published API price, so its estimate is unavailable.

For example, Standard Astra with 200,000 input tokens, including 100,000 cache reads and 40,000 cache writes, plus 100,000 output tokens costs $6.20. The input segment includes $0.60 ordinary input and $0.50 cache writes; cached input costs $0.10 and output costs $5.00. The same usage at Astra Ultrafast costs $37.20.

The ChatGPT pricing page documents subscription credits and included usage separately from API token pricing. Pro 100, Pro 200 and Pro 500 are subscription plans; Astra Ultrafast is included only with Pro 500 and eligible Enterprise/Edu plans. Those subscription allowances and multipliers are not converted into API-key quota capacity or API USD estimates. When upstream usage exposes a Pro-family plan without an absolute allowance, the fork keeps the reported percentage/reset and exposes absolute capacity as unknown rather than applying a legacy or price-derived allowance.

## Historical repair

Updating the registry affects newly recorded requests. Previous totals use stored costs, and may also be stored in hourly and lifetime summaries. The repair utility applies only the difference for each retained row to those summaries. It preserves contributions from pruned rows, custom model-source costs, and API-key quota enforcement counters. It does not recreate unavailable history or infer previously discarded cache writes.

After migrating the target database and deploying the code, preview the exact stored model IDs to repair. Include the new families and any dated/snapshot IDs that actually occur in retained rows:

```sh
.venv/bin/python -m scripts.repair_cost_estimates \
  --model gpt-6-astra \
  --model gpt-6.1-sol \
  --model gpt-6-sol \
  --model gpt-6-luna \
  --since 2026-09-01
```

Repeat `--model` to include aliases or other models recorded in the database. Dates are interpreted as UTC; `--since` is inclusive and `--until` is exclusive. The default is a read-only preview. Review the changed-row count, USD difference, and missing-cache-write count, back up the database, then run the identical command with `--apply`. Applied repairs commit in batches of 500 rows; rerunning safely resumes any interrupted repair. A missing aggregate stops and rolls back the current batch rather than overwriting unrelated history.

Legacy image estimates retain the existing single-input-rate approximation; modality-specific image inputs and tool fees are not reconstructed by this update. Regional uplifts, unsupported Batch routing, and negotiated pricing are outside the estimates. Models served through custom sources continue to use their configured prices.

## Verification

The September 29 update matches the published Standard and Ultrafast rows for the GPT-6 family and Astra against the fetched official tables. Regression coverage includes mixed cache reads/writes, context boundaries, authoritative response tiers, HTTP/compact/WebSocket usage propagation, API-key reservation and settlement, request-log API costs, historical cost repair with retained/pruned aggregates, and SQLite migration round trips and legacy bootstrap. PostgreSQL-only migration tests require a PostgreSQL test database. Historical repair remains an explicit preview/apply operation; code deployment does not rewrite retained cost rows automatically.
