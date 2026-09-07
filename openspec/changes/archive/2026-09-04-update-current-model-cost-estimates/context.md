# Current API cost estimates

The estimates answer “what would the reported tokens cost at the published OpenAI API rate?” They are not ChatGPT subscription charges or credit usage. The registry is a verified snapshot, not a live pricing feed.

Sources fetched September 4, 2026:

- [Official API pricing](https://developers.openai.com/api/docs/pricing): Standard, Fast, Flex, and current Daybreak aliases.
- [Astra model details](https://developers.openai.com/api/docs/models/gpt-6-astra): long context begins above 272,000 input tokens; input/cache rates double and output increases by 1.5 for the full request.
- [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching): cache writes are reported as `input_tokens_details.cache_write_tokens` and cost 1.25 times ordinary input for GPT-5.6 and later.

Sol's current promotional API rate is published through at least November 21, 2026. Fast API rates for Astra and GPT-5.6 are twice Standard; ChatGPT's 2.5-times credit multiplier does not apply to API estimates. Spark has no published API price, so its estimate is unavailable.

For example, Standard Astra with 200,000 input tokens, including 100,000 cache reads and 40,000 cache writes, plus 100,000 output tokens costs $6.20. The input segment includes $0.60 ordinary input and $0.50 cache writes; cached input costs $0.10 and output costs $5.00.

## Historical repair

Updating the registry affects newly recorded requests. Previous totals use stored costs, and may also be stored in hourly and lifetime summaries. The repair utility applies only the difference for each retained row to those summaries. It preserves contributions from pruned rows, custom model-source costs, and API-key quota enforcement counters. It does not recreate unavailable history or infer previously discarded cache writes.

After migrating the target database and deploying the code, preview the exact stored model IDs to repair:

```sh
.venv/bin/python -m scripts.repair_cost_estimates --model gpt-6-astra --since 2026-09-01
```

Repeat `--model` to include aliases or other models recorded in the database. Dates are interpreted as UTC; `--since` is inclusive and `--until` is exclusive. The default is a read-only preview. Review the changed-row count, USD difference, and missing-cache-write count, back up the database, then run the identical command with `--apply`. Applied repairs commit in batches of 500 rows; rerunning safely resumes any interrupted repair. A missing aggregate stops and rolls back the current batch rather than overwriting unrelated history.

Legacy image estimates retain the existing single-input-rate approximation; modality-specific image inputs and tool fees are not reconstructed by this update. Regional uplifts, unsupported Batch routing, and negotiated pricing are outside the estimates. Models served through custom sources continue to use their configured prices.
