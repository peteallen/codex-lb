# Context

On 2026-10-30 a native Codex image edit reached
`/backend-api/codex/images/edits` but failed with HTTP 503
`no_plan_support_for_model` because the adapter forced the outer Responses
model to `gpt-5.5`. The live account catalog had withdrawn that model while
advertising newer GPT-5.6, GPT-6, and GPT-6.1 models. The failure occurred
before upstream image generation, so no image bytes or public response model
were produced.

The model registry already owns account-plan visibility and suppression state.
This change reuses that evidence at image-host selection time. It does not
alter registry refresh, account eligibility, or public image model validation.

For example, a catalog with `gpt-5.6-luna` available selects that host. If
the catalog suppresses Luna but advertises `gpt-6-luna`, the adapter selects
the latter. If the registry is empty, the adapter deterministically returns
Luna and the existing account-selection error remains visible.
