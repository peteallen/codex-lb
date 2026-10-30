# Design

Use a small `app.core.openai.host_models` module for the internal host model
decision. Its ordered candidates are stable, known Codex Responses models. The
resolver asks the existing global `ModelRegistry` for plan visibility and
suppression state; it does not infer account support from public model
visibility or modify registry data.

The first candidate with non-empty plan visibility and no suppression is used.
When the registry is still on its bootstrap floor, `gpt-5.6-luna` is available
and is selected. If a refreshed catalog suppresses that candidate but advertises
the documented GPT-6 Astra image-tool host, Astra is selected. `gpt-5.5` stays
last in the list for older deployments. If every candidate is absent or
suppressed, the resolver returns `gpt-5.6-luna` so the existing downstream
selection and error handling remains authoritative. This fallback is
deterministic and does not claim that the model is available.

Only the outer Responses model changes. The public `gpt-image-*` value remains
inside the `image_generation` tool and in request accounting.
