from __future__ import annotations

import pytest

import app.core.openai.host_models as host_models

pytestmark = pytest.mark.unit


class _FakeRegistry:
    def __init__(self, plans: dict[str, frozenset[str]], suppressed: set[str] | None = None) -> None:
        self._plans = plans
        self._suppressed = suppressed or set()

    def plan_types_for_model(self, slug: str) -> frozenset[str] | None:
        return self._plans.get(slug)

    def is_suppressed_model(self, slug: str) -> bool:
        return slug in self._suppressed


def test_resolver_uses_bootstrap_preferred_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        host_models,
        "get_model_registry",
        lambda: _FakeRegistry({"gpt-5.6-luna": frozenset({"plus"})}),
    )

    assert host_models.resolve_image_host_model() == "gpt-5.6-luna"


def test_resolver_skips_suppressed_preferred_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        host_models,
        "get_model_registry",
        lambda: _FakeRegistry(
            {
                "gpt-5.6-luna": frozenset({"plus"}),
                "gpt-6-astra": frozenset({"plus"}),
            },
            {"gpt-5.6-luna"},
        ),
    )

    assert host_models.resolve_image_host_model() == "gpt-6-astra"


def test_resolver_falls_back_deterministically_when_no_candidate_is_eligible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_models, "get_model_registry", lambda: _FakeRegistry({}, set()))

    assert host_models.resolve_image_host_model() == "gpt-5.6-luna"


def test_resolver_retains_legacy_host_for_older_catalogs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        host_models,
        "get_model_registry",
        lambda: _FakeRegistry({"gpt-5.5": frozenset({"plus"})}),
    )

    assert host_models.resolve_image_host_model() == "gpt-5.5"
