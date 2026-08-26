# Improve dashboard token visibility and pricing tasks

- [x] Extend usage aggregation and response contracts with additive input/output token totals while preserving existing total and cached-input fields.
- [x] Render compact input/output detail on the dashboard, conversations, accounts, API-key summaries, and selected-key usage surfaces; keep reports, aggregate charts, donuts, and limit semantics unchanged.
- [x] Make the dashboard date/refresh controls toolbar sticky below the global app header and responsive on narrow screens without changing refresh behavior.
- [x] Update the canonical OpenAI pricing registry for all currently represented models whose official rates changed, including explicit long-context Fast handling.
- [x] Add focused backend and frontend regression coverage for token contracts, token readouts, sticky controls, alias resolution, service tiers, long context, and image prices.
- [x] Run focused Python and frontend tests, lint/type checks for changed files, and strict OpenSpec validation when the CLI is available.

No task is complete until its verification command passes or an environment limitation is recorded. The focused Python and frontend checks passed; formal OpenSpec validation could not run because the `openspec` executable is unavailable in this checkout.
