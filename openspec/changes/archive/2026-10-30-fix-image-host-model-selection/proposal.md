# Select a routable internal image host model

## Summary

Replace the fixed `gpt-5.5` Responses host model used by the Images adapter
with a catalog-aware selection from current, image-capable Codex models.

## Motivation

The native Codex image client reaches codex-lb correctly, but the image adapter
currently routes every generation and edit through `gpt-5.5`. Once the live
account catalog withdraws that model, account selection returns
`no_plan_support_for_model` before the image tool can run. The public
`gpt-image-*` request contract remains valid and must not change.

## Scope

- Select the first unsuppressed candidate with non-empty registry plan
  visibility for both generation and edit routes.
- Prefer `gpt-5.6-luna`, then currently supported newer Codex models, while
  retaining a deterministic fallback for an uninitialized or empty registry.
- Cover native Codex aliases and canonical `/v1` generation/edit paths through
  existing route tests.
- Keep the public image model in validation, the image tool configuration, and
  response/request accounting unchanged.

## Out of Scope

- Changing account catalog eligibility or model registry refresh behavior.
- Changing default account probe model selection.
- Adding retries or a second upstream request when no candidate is routable.
