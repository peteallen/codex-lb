"""Internal Responses model selection for image generation and edits."""

from app.core.openai.model_registry import get_model_registry

# Keep the preferred host aligned with the bundled Codex catalog, then allow
# newer catalog entries to serve as hosts when the preferred model is withdrawn.
# These are internal Responses models; the public ``gpt-image-*`` model remains
# in the image-generation tool configuration.
_IMAGE_HOST_MODEL_CANDIDATES = (
    "gpt-5.6-luna",
    "gpt-6-astra",
    # Keep the former host as a compatibility fallback for older catalogs
    # that have not advertised GPT-5.6 or GPT-6 yet.
    "gpt-5.5",
)


def resolve_image_host_model() -> str:
    """Return the first image-capable host visible to the model registry.

    Registry plan visibility is the existing account-selection contract. A
    suppressed model is skipped even if stale metadata still exposes plans.
    If the registry has no eligible candidate, retain a deterministic first
    candidate and let normal downstream account-selection errors apply.
    """

    registry = get_model_registry()
    for candidate in _IMAGE_HOST_MODEL_CANDIDATES:
        if registry.plan_types_for_model(candidate) and not registry.is_suppressed_model(candidate):
            return candidate
    return _IMAGE_HOST_MODEL_CANDIDATES[0]
