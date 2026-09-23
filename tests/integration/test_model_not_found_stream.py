from __future__ import annotations

import json

import pytest

import app.modules.proxy.load_balancer as load_balancer_module
import app.modules.proxy.service as proxy_module
from app.core.clients.proxy import ProxyResponseError
from app.core.errors import openai_error
from app.db.models import Account, AccountStatus, StickySession, StickySessionKind
from app.db.session import SessionLocal
from tests.integration.test_proxy_transient_retry import (
    _extract_events,
    _import_account,
    _overload_sse_event,
    _success_sse_event,
)

pytestmark = pytest.mark.integration

_RESPONSE_PATHS = ("/v1/responses", "/backend-api/codex/responses")
_NEW_MODELS = ("gpt-6-sol", "gpt-6-luna")


@pytest.fixture(autouse=True)
async def _force_usage_weighted_routing(async_client) -> None:
    current = await async_client.get("/api/settings")
    assert current.status_code == 200
    payload = current.json()
    payload["routingStrategy"] = "usage_weighted"
    response = await async_client.put("/api/settings", json=payload)
    assert response.status_code == 200


def _model_not_found_error(model: str) -> ProxyResponseError:
    return ProxyResponseError(
        404,
        openai_error(
            "model_not_found",
            f"The model `{model}` does not exist or you do not have access to it.",
            error_type="invalid_request_error",
        ),
        failure_phase="status",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("path", _RESPONSE_PATHS)
@pytest.mark.parametrize("model", _NEW_MODELS)
async def test_raw_http_model_not_found_retries_same_model_on_another_account(
    async_client,
    monkeypatch,
    path,
    model,
):
    raw_account_ids = ("model-not-found-a", "model-not-found-b")
    account_ids = [
        await _import_account(async_client, raw_account_ids[0], "model-not-found-a@example.com"),
        await _import_account(async_client, raw_account_ids[1], "model-not-found-b@example.com"),
    ]
    account_id_by_raw_id = dict(zip(raw_account_ids, account_ids, strict=True))
    seen_account_ids: list[str | None] = []

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        assert payload.model == model
        del headers, access_token, base_url, raise_for_status, kwargs
        seen_account_ids.append(account_id)
        if len(seen_account_ids) == 1:
            raise _model_not_found_error(model)
        yield _success_sse_event(f"resp_{model.replace('-', '_')}_recovered")

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    async with async_client.stream(
        "POST",
        path,
        json={"model": model, "instructions": "retry safely", "input": [], "stream": True},
    ) as response:
        assert response.status_code == 200
        events = _extract_events([line async for line in response.aiter_lines() if line])

    completed = [event for event in events if event.get("type") == "response.completed"]
    assert len(completed) == 1
    assert len(seen_account_ids) == 2
    assert seen_account_ids[0] in raw_account_ids
    assert seen_account_ids[1] in raw_account_ids
    assert seen_account_ids[0] != seen_account_ids[1]

    async with SessionLocal() as session:
        rejected = await session.get(Account, account_id_by_raw_id[seen_account_ids[0]])
        assert rejected is not None
        assert rejected.status == AccountStatus.ACTIVE


@pytest.mark.asyncio
@pytest.mark.parametrize("model", _NEW_MODELS)
async def test_raw_http_model_not_found_can_escape_legacy_hard_session_affinity(
    async_client,
    monkeypatch,
    model,
):
    first_raw_id = "model-not-found-legacy-owner"
    second_raw_id = "model-not-found-legacy-replacement"
    first_account_id = await _import_account(async_client, first_raw_id, "model-not-found-legacy-owner@example.com")
    await _import_account(
        async_client,
        second_raw_id,
        "model-not-found-legacy-replacement@example.com",
    )
    session_id = "legacy-model-rejection-session"
    async with SessionLocal() as session:
        session.add(
            StickySession(
                key=session_id,
                kind=StickySessionKind.CODEX_SESSION,
                account_id=first_account_id,
            )
        )
        await session.commit()

    seen_account_ids: list[str | None] = []
    seen_headers: list[dict[str, str]] = []

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        assert payload.model == model
        del access_token, base_url, raise_for_status, kwargs
        seen_account_ids.append(account_id)
        seen_headers.append(dict(headers))
        if len(seen_account_ids) == 1:
            raise _model_not_found_error(model)
        yield _success_sse_event("resp_legacy_affinity_recovered")

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    async with async_client.stream(
        "POST",
        "/v1/responses",
        headers={"session_id": session_id},
        json={"model": model, "instructions": "escape stale session owner", "input": [], "stream": True},
    ) as response:
        assert response.status_code == 200
        events = _extract_events([line async for line in response.aiter_lines() if line])

    assert [event for event in events if event.get("type") == "response.completed"]
    assert seen_account_ids == [first_raw_id, second_raw_id]
    assert "session_id" in seen_headers[0]
    assert all(key.lower() != "session_id" for key in seen_headers[1])


@pytest.mark.asyncio
@pytest.mark.parametrize("path", _RESPONSE_PATHS)
@pytest.mark.parametrize("model", _NEW_MODELS)
async def test_raw_http_model_not_found_sweeps_multiple_rejecting_accounts(
    async_client,
    monkeypatch,
    path,
    model,
):
    raw_account_ids = tuple(f"model-not-found-sweep-{index}" for index in range(3))
    for index, raw_account_id in enumerate(raw_account_ids):
        await _import_account(
            async_client,
            raw_account_id,
            f"model-not-found-sweep-{index}@example.com",
        )
    seen_account_ids: list[str | None] = []

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        assert payload.model == model
        del headers, access_token, base_url, raise_for_status, kwargs
        seen_account_ids.append(account_id)
        if len(seen_account_ids) <= 2:
            raise _model_not_found_error(model)
        yield _success_sse_event(f"resp_{model.replace('-', '_')}_sweep_recovered")

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    async with async_client.stream(
        "POST",
        path,
        json={"model": model, "instructions": "retry across the pool", "input": [], "stream": True},
    ) as response:
        assert response.status_code == 200
        events = _extract_events([line async for line in response.aiter_lines() if line])

    assert [event for event in events if event.get("type") == "response.completed"]
    assert len(seen_account_ids) == len(raw_account_ids)
    assert len(set(seen_account_ids)) == len(raw_account_ids)


@pytest.mark.asyncio
async def test_raw_http_model_not_found_sweep_is_not_fixed_at_three_candidates(async_client, monkeypatch):
    model = "gpt-6-sol"
    raw_account_ids = tuple(f"model-not-found-four-{index}" for index in range(4))
    for index, raw_account_id in enumerate(raw_account_ids):
        await _import_account(
            async_client,
            raw_account_id,
            f"model-not-found-four-{index}@example.com",
        )
    seen_account_ids: list[str | None] = []

    # Model-rejection recovery must remain available even when the generic
    # transient account-attempt allowance is exhausted.
    monkeypatch.setattr(proxy_module, "_STREAM_MAX_ACCOUNT_ATTEMPTS", 1)

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        assert payload.model == model
        del headers, access_token, base_url, raise_for_status, kwargs
        seen_account_ids.append(account_id)
        if len(seen_account_ids) < len(raw_account_ids):
            raise _model_not_found_error(model)
        yield _success_sse_event("resp_gpt_6_sol_fourth_candidate")

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    async with async_client.stream(
        "POST",
        "/v1/responses",
        json={"model": model, "instructions": "reach the fourth candidate", "input": [], "stream": True},
    ) as response:
        assert response.status_code == 200
        events = _extract_events([line async for line in response.aiter_lines() if line])

    assert [event for event in events if event.get("type") == "response.completed"]
    assert len(seen_account_ids) == len(raw_account_ids)
    assert len(set(seen_account_ids)) == len(raw_account_ids)


@pytest.mark.asyncio
async def test_raw_http_model_not_found_sweep_preserves_original_error_when_all_reject(async_client, monkeypatch):
    model = "gpt-6-luna"
    raw_account_ids = tuple(f"model-not-found-exhaust-{index}" for index in range(4))
    for index, raw_account_id in enumerate(raw_account_ids):
        await _import_account(
            async_client,
            raw_account_id,
            f"model-not-found-exhaust-{index}@example.com",
        )
    seen_account_ids: list[str | None] = []

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        assert payload.model == model
        del headers, access_token, base_url, raise_for_status, kwargs
        seen_account_ids.append(account_id)
        raise _model_not_found_error(model)
        if False:  # pragma: no cover
            yield ""

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    async with async_client.stream(
        "POST",
        "/backend-api/codex/responses",
        json={"model": model, "instructions": "preserve the last rejection", "input": [], "stream": True},
    ) as response:
        assert response.status_code == 404
        body = json.loads(await response.aread())
        assert body["error"] == {
            "message": f"The model `{model}` does not exist or you do not have access to it.",
            "type": "invalid_request_error",
            "code": "model_not_found",
        }

    assert len(seen_account_ids) == len(raw_account_ids)
    assert len(set(seen_account_ids)) == len(raw_account_ids)


@pytest.mark.asyncio
async def test_raw_http_model_rejection_stays_excluded_after_overload_recovery(async_client, monkeypatch):
    model = "gpt-6-sol"
    raw_account_id = "model-not-found-after-overload"
    await _import_account(async_client, raw_account_id, "model-not-found-after-overload@example.com")
    seen_account_ids: list[str | None] = []

    monkeypatch.setattr(load_balancer_module, "_OVERLOAD_COOLDOWN_SECONDS", 0.001)
    monkeypatch.setattr(load_balancer_module, "_OVERLOAD_COOLDOWN_MAX_SECONDS", 0.001)

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        assert payload.model == model
        del headers, access_token, base_url, raise_for_status, kwargs
        seen_account_ids.append(account_id)
        if len(seen_account_ids) == 1:
            yield _overload_sse_event("server_is_overloaded")
            return
        raise _model_not_found_error(model)
        if False:  # pragma: no cover
            yield ""

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    async with async_client.stream(
        "POST",
        "/v1/responses",
        json={"model": model, "instructions": "preserve request-local exclusions", "input": [], "stream": True},
    ) as response:
        assert response.status_code == 404
        body = json.loads(await response.aread())
        assert body["error"]["code"] == "model_not_found"

    assert seen_account_ids == [raw_account_id, raw_account_id]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", _RESPONSE_PATHS)
@pytest.mark.parametrize("model", _NEW_MODELS)
async def test_raw_http_model_not_found_preserves_original_error_without_replacement(
    async_client,
    monkeypatch,
    path,
    model,
):
    raw_account_id = "model-not-found-only"
    account_id = await _import_account(async_client, raw_account_id, "model-not-found-only@example.com")
    seen_account_ids: list[str | None] = []

    async def fake_stream(payload, headers, access_token, account_id, base_url=None, raise_for_status=False, **kwargs):
        assert payload.model == model
        del headers, access_token, base_url, raise_for_status, kwargs
        seen_account_ids.append(account_id)
        raise _model_not_found_error(model)
        if False:  # pragma: no cover
            yield ""

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    async with async_client.stream(
        "POST",
        path,
        json={"model": model, "instructions": "preserve error", "input": [], "stream": True},
    ) as response:
        assert response.status_code == 404
        body = json.loads(await response.aread())
        assert body["error"] == {
            "message": f"The model `{model}` does not exist or you do not have access to it.",
            "type": "invalid_request_error",
            "code": "model_not_found",
        }
    assert seen_account_ids == [raw_account_id]

    async with SessionLocal() as session:
        account = await session.get(Account, account_id)
        assert account is not None
        assert account.status == AccountStatus.ACTIVE
