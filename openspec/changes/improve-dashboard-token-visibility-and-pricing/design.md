# Improve dashboard token visibility and pricing

## Scope

This change improves the accuracy and usability of existing usage surfaces. It does not add a navigation item, setting, database column, or pricing service. Reports already present input, cached input, and output totals and remain unchanged.

## Token presentation

Existing aggregate `tokens` / `totalTokens` fields remain the compatibility and headline values. The backend propagates the input and output sums it already computes through dashboard overview metrics, conversation rows, account request-usage summaries, and API-key usage summaries. Request-log responses already expose the two fields.

The UI uses compact, explicitly labelled input and output values in the main dashboard token card, request rows, conversation rows, account usage, API-key lifetime usage, and selected-key usage. Cached input stays a separate detail because it is a priced subset of input, not a third additive component of total tokens. Total-token charts and by-key distribution donuts remain aggregate views; splitting those series would add visual noise without improving the comparison they are designed to make. Token limit controls retain their current names because total, input, and output are distinct enforcement choices.

Missing additive fields are rendered as unavailable rather than reconstructed from an incomplete legacy payload. New bundled frontend/backend versions provide the fields together.

## Sticky dashboard controls

The dashboard title remains normal page content. A separate compact toolbar containing the date selector and refresh button becomes sticky below the existing 53-pixel global app header. It uses a lower stacking layer than the global header and a translucent background, border, shadow, and backdrop blur so scrolled content cannot obscure the controls. The toolbar wraps naturally on narrow screens without forcing the title, date selector, and refresh action into one cramped row. Existing refresh semantics, accessible label, disabled state, and range controls stay unchanged.

## Pricing source and mapping

The source is the official OpenAI API pricing page fetched on August 26, 2026: `https://developers.openai.com/api/docs/pricing`. Prices remain isolated in `app/core/usage/pricing.py` and are stored as USD per one million tokens.

The registry models only dimensions present in completed-request usage: uncached input, cached input, and output. It therefore does not invent charges for cache-write tokens, regional processing, or Batch requests. Fast long-context rates are represented explicitly because the current table publishes them separately. Flex long-context rates are also explicit where the table publishes them; unsupported tier/context combinations use that tier's configured short-context rate rather than an invented multiplier. The existing `priority` spelling remains an accepted synonym for OpenAI's renamed `fast` service tier.

Image-generation entries keep the registry's documented single-input-rate approximation: text input is the input rate, image cached input is the cached rate, and image output is the output rate. Each supported image model uses its own current published values instead of copying GPT Image 2 prices to legacy models.

## Failure modes and verification

- A sticky header with `top: 0` would sit under the global app header, so the offset and stacking order require regression coverage.
- A broad model alias can silently select an older family price, so exact, bare, and suffixed model resolution remains covered.
- Snapshot aliases accept dated suffixes only. Distinct public model IDs such as Pro, Mini, Nano, Search, and Cyber variants do not inherit a family price unless the registry contains an explicit supported entry. The repo-supported `gpt-5.3-codex-spark` compatibility ID resolves explicitly to the published GPT-5.3-Codex row.
- Long-context Fast requests can be mispriced if they reuse short-context Fast values, so every GPT-5.6 personality needs an explicit long-context Fast calculation test.
- Additive token fields must equal the existing total contract (`input + output`) in backend fixtures, while cached input remains clamped within input.
- Folded dashboard activity must use the rollup's output-or-reasoning measure so reasoning-only output matches the raw request-log path before and after retention folding.

Example: a request readout with 120,000 input tokens, 20,000 cached input tokens, and 8,000 output tokens keeps `128K` as its total headline and shows `Input 120K · Cache 20K · Output 8K` as detail.
