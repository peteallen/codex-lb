from __future__ import annotations

import asyncio
import json
import time

import pytest
from sqlalchemy import select

import app.modules.proxy.load_balancer as load_balancer_module
import app.modules.proxy.service as proxy_module
from app.core.clients.proxy import ProxyResponseError
from app.core.errors import openai_error
from app.db.models import ApiKeyUsageReservation
from app.db.session import SessionLocal
from app.dependencies import get_proxy_service_for_app
from app.modules.proxy._load_balancer.types import RuntimeState
from app.modules.proxy._service.streaming import retry as retry_module
from app.modules.proxy.load_balancer import AccountLease, LoadBalancer
from tests.integration.test_proxy_transient_retry import (
    _extract_events,
    _import_account,
    _overload_sse_event,
    _success_sse_event,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_repeated_accepted_http_overloads_keep_image_requests_on_healthy_alternate(async_client, monkeypatch):
    await _import_account(async_client, "recurring_overload", "recurring-overload@example.com")
    now = time.time()
    monkeypatch.setattr(load_balancer_module.time, "time", lambda: now)
    seen_accounts = []

    async def stream(payload, headers, access_token, account_id, **kwargs):
        seen_accounts.append(account_id)
        assert kwargs["upstream_stream_transport_override"] == "http"
        if account_id == "recurring_overload":
            # Acceptance prohibits replay of this request, but must still
            # suppress this account for future independent requests.
            yield 'data: {"type":"response.created","response":{"id":"resp_accepted"}}\n\n'
            yield _overload_sse_event("server_is_overloaded")
        else:
            yield _success_sse_event("healthy_image_response")

    monkeypatch.setattr(proxy_module, "core_stream_responses", stream)
    body = {
        "model": "gpt-5.1",
        "stream": True,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Describe this image."},
                    {"type": "input_image", "image_url": "data:image/png;base64,aGVsbG8="},
                ],
            }
        ],
    }
    for _ in range(2):
        response = await async_client.post("/v1/responses", json=body)
        assert response.status_code == 200
        assert "server_is_overloaded" in response.text
        now += 31
    assert seen_accounts == ["recurring_overload", "recurring_overload"]
    await _import_account(async_client, "healthy_alternate", "healthy-alternate@example.com")
    response = await async_client.post("/v1/responses", json=body)
    assert response.status_code == 200
    events = _extract_events(response.text.splitlines())
    assert events[-1]["type"] == "response.completed", json.dumps(events)
    assert seen_accounts == ["recurring_overload", "recurring_overload", "healthy_alternate"]
    service = get_proxy_service_for_app(async_client._transport.app)
    overloaded_runtime = next(state for state in service._load_balancer._runtime.values() if state.overload_count)
    assert overloaded_runtime.overload_count == 2
    assert overloaded_runtime.overload_cooldown_until == now + 29


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/v1/responses", "/backend-api/codex/responses"])
async def test_overload_waits_beyond_account_attempt_limit(async_client, monkeypatch, path):
    await _import_account(async_client, "overloaded", "overloaded@example.com")
    calls = 0
    waits = 0
    original_wait = retry_module._iter_account_capacity_recovery_wait

    async def short_wait(**kwargs):
        nonlocal waits
        waits += 1
        kwargs["recovery_sleep_seconds"] = 0.002
        async for event in original_wait(**kwargs):
            yield event

    # Selection/leases remain real; shorten only the operational cooldown.
    monkeypatch.setattr(load_balancer_module, "_OVERLOAD_COOLDOWN_SECONDS", 0.001)
    monkeypatch.setattr(load_balancer_module, "_OVERLOAD_COOLDOWN_MAX_SECONDS", 0.001)

    async def stream(payload, headers, access_token, account_id, **kwargs):
        nonlocal calls
        calls += 1
        if calls <= 4:
            yield _overload_sse_event("server_is_overloaded")
        else:
            yield _success_sse_event("overload_recovered")

    monkeypatch.setattr(proxy_module, "_STREAM_MAX_ACCOUNT_ATTEMPTS", 1)
    monkeypatch.setattr(proxy_module, "core_stream_responses", stream)
    monkeypatch.setattr(retry_module, "_iter_account_capacity_recovery_wait", short_wait)
    response = await async_client.post(
        path,
        json={"model": "gpt-5.1", "input": "hello", "stream": True},
    )
    assert response.status_code == 200
    events = _extract_events(response.text.splitlines())
    assert calls == 5
    assert waits >= 4
    assert any(event.get("type") == "response.completed" for event in events)
    assert not any(event.get("type") in {"error", "response.failed"} for event in events)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/v1/responses", "/backend-api/codex/responses"])
async def test_fresh_request_waits_when_all_accounts_are_in_overload_cooldown(async_client, monkeypatch, path):
    account_ids = [
        await _import_account(async_client, "fresh_cooling_a", "fresh-cooling-a@example.com"),
        await _import_account(async_client, "fresh_cooling_b", "fresh-cooling-b@example.com"),
    ]
    service = get_proxy_service_for_app(async_client._transport.app)
    for account_id in account_ids:
        service._load_balancer._runtime.setdefault(
            account_id, RuntimeState()
        ).overload_cooldown_until = 30_000_000_000.0

    waits = 0
    seen_accounts: list[str | None] = []

    async def wait(**_kwargs):
        nonlocal waits
        waits += 1
        for account_id in account_ids:
            service._load_balancer._runtime[account_id].overload_cooldown_until = 0.0
        if False:
            yield ""

    async def stream(payload, headers, access_token, account_id, **kwargs):
        del payload, headers, access_token, kwargs
        seen_accounts.append(account_id)
        yield _success_sse_event("fresh_overload_recovered")

    monkeypatch.setattr(proxy_module, "core_stream_responses", stream)
    monkeypatch.setattr(retry_module, "_iter_account_capacity_recovery_wait", wait)
    response = await async_client.post(
        path,
        json={"model": "gpt-5.1", "input": "hello", "stream": True},
    )

    assert response.status_code == 200
    events = _extract_events(response.text.splitlines())
    assert waits == 1
    assert len(seen_accounts) == 1
    assert any(event.get("type") == "response.completed" for event in events)


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_stage", ["queue", "lease_release"])
async def test_overload_queue_cancellation_releases_stream_leases(async_client, monkeypatch, cancel_stage):
    await _import_account(async_client, "cancel_overloaded", "cancel_overloaded@example.com")
    settings = (await async_client.get("/api/settings")).json()
    settings["apiKeyAuthEnabled"] = True
    assert (await async_client.put("/api/settings", json=settings)).status_code == 200
    created_key = await async_client.post(
        "/api/api-keys/",
        json={
            "name": "overload-cancellation",
            "limits": [{"limitType": "total_tokens", "limitWindow": "weekly", "maxValue": 1_000_000}],
        },
    )
    assert created_key.status_code == 200
    key = created_key.json()
    waiting = asyncio.Event()
    instances: list[LoadBalancer] = []
    released_leases: list[AccountLease] = []
    original_release = LoadBalancer.release_account_lease
    release_interrupted = False

    async def release(self, lease):
        nonlocal release_interrupted
        if self not in instances:
            instances.append(self)
        if cancel_stage == "lease_release" and lease is not None and not release_interrupted:
            release_interrupted = True
            waiting.set()
            await asyncio.Event().wait()
        await original_release(self, lease)
        if lease is not None:
            released_leases.append(lease)

    async def wait(**kwargs):
        waiting.set()
        await asyncio.Event().wait()
        if False:
            yield ""

    async def stream(*args, **kwargs):
        yield _overload_sse_event("server_is_overloaded")

    monkeypatch.setattr(proxy_module, "core_stream_responses", stream)
    monkeypatch.setattr(LoadBalancer, "release_account_lease", release)
    monkeypatch.setattr(retry_module, "_iter_account_capacity_recovery_wait", wait)
    task = asyncio.create_task(
        async_client.post(
            "/backend-api/codex/responses",
            json={"model": "gpt-5.1", "input": "hello", "stream": True},
            headers={"Authorization": f"Bearer {key['key']}"},
        )
    )
    try:
        await asyncio.wait_for(waiting.wait(), timeout=5)
        async with SessionLocal() as session:
            reservations = list(
                await session.scalars(
                    select(ApiKeyUsageReservation).where(ApiKeyUsageReservation.api_key_id == key["id"])
                )
            )
            assert [reservation.status for reservation in reservations] == ["reserved"]
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    assert released_leases
    assert len(released_leases) == len({lease.lease_id for lease in released_leases})
    assert all(not state.leases for balancer in instances for state in balancer._runtime.values())
    service = get_proxy_service_for_app(async_client._transport.app)
    if service._background_cleanup_tasks:
        await asyncio.gather(*service._background_cleanup_tasks)
    async with SessionLocal() as session:
        reservations = list(
            await session.scalars(select(ApiKeyUsageReservation).where(ApiKeyUsageReservation.api_key_id == key["id"]))
        )
        assert [reservation.status for reservation in reservations] == ["released"]


@pytest.mark.asyncio
@pytest.mark.parametrize("owner_kind", ["previous_response", "file"])
async def test_overload_owner_bound_request_waits_without_crossing_accounts(async_client, monkeypatch, owner_kind):
    owner_id = await _import_account(async_client, "overloaded_owner", "owner@example.com")
    await _import_account(async_client, "healthy_alternate", "alternate@example.com")
    service = get_proxy_service_for_app(async_client._transport.app)
    seen_accounts = []
    waits = 0

    async def owner(self, **kwargs):
        return owner_id

    async def wait(**kwargs):
        nonlocal waits
        waits += 1
        # Advance just the account cooldown; keep owner lookup and selection real.
        service._load_balancer._runtime[owner_id].overload_cooldown_until = 0.0
        if False:
            yield ""

    async def stream(payload, headers, access_token, account_id, **kwargs):
        seen_accounts.append(account_id)
        if len(seen_accounts) == 1:
            yield _overload_sse_event("server_is_overloaded")
        else:
            yield _success_sse_event("owner_recovered")

    payload = {"model": "gpt-5.1", "input": [], "stream": True}
    if owner_kind == "previous_response":
        monkeypatch.setattr(proxy_module.ProxyService, "_resolve_websocket_previous_response_owner", owner)
        payload["previous_response_id"] = "resp_existing_owner"
    else:
        await service._pin_file_account("file_overload_owner", owner_id)
        payload["input"] = [{"role": "user", "content": [{"type": "input_file", "file_id": "file_overload_owner"}]}]
    monkeypatch.setattr(proxy_module, "core_stream_responses", stream)
    monkeypatch.setattr(retry_module, "_iter_account_capacity_recovery_wait", wait)
    response = await async_client.post("/backend-api/codex/responses", json=payload)
    assert response.status_code == 200
    events = _extract_events(response.text.splitlines())
    assert seen_accounts == ["overloaded_owner", "overloaded_owner"]
    assert waits >= 1
    assert any(event.get("type") == "response.completed" for event in events)


@pytest.mark.asyncio
async def test_overload_wait_stops_at_request_deadline(async_client, monkeypatch):
    await _import_account(async_client, "deadline_overloaded", "deadline@example.com")
    calls = 0

    async def wait(**kwargs):
        monkeypatch.setattr(proxy_module, "_remaining_budget_seconds", lambda deadline: 0.0)
        if False:
            yield ""

    async def stream(*args, **kwargs):
        nonlocal calls
        calls += 1
        yield _overload_sse_event("server_is_overloaded")

    monkeypatch.setattr(proxy_module, "core_stream_responses", stream)
    monkeypatch.setattr(retry_module, "_iter_account_capacity_recovery_wait", wait)
    response = await async_client.post(
        "/backend-api/codex/responses", json={"model": "gpt-5.1", "input": "hello", "stream": True}
    )
    events = _extract_events(response.text.splitlines())
    failed = [event for event in events if event.get("type") == "response.failed"]
    assert calls == 1
    assert len(failed) == 1
    assert failed[0]["response"]["error"]["code"] == "upstream_request_timeout"


@pytest.mark.asyncio
@pytest.mark.parametrize("affinity_kind", ["session", "prompt_cache"])
async def test_overload_uses_healthy_capacity_despite_soft_affinity(async_client, monkeypatch, affinity_kind):
    await _import_account(async_client, "soft_affinity_a", "soft-a@example.com")
    await _import_account(async_client, "soft_affinity_b", "soft-b@example.com")
    seen_accounts = []
    seen_headers = []

    async def stream(payload, headers, access_token, account_id, **kwargs):
        seen_accounts.append(account_id)
        seen_headers.append(dict(headers))
        if len(seen_accounts) == 2:
            yield _overload_sse_event("server_is_overloaded")
        else:
            yield _success_sse_event(f"soft_recovered_{len(seen_accounts)}")

    monkeypatch.setattr(proxy_module, "core_stream_responses", stream)
    headers = {"session_id": "overload-soft-session"} if affinity_kind == "session" else {}
    payload = {"model": "gpt-5.1", "input": "hello", "stream": True}
    if affinity_kind == "prompt_cache":
        payload["prompt_cache_key"] = "overload-soft-cache"
    for _ in range(2):
        response = await async_client.post("/backend-api/codex/responses", headers=headers, json=payload)
        assert response.status_code == 200
        events = _extract_events(response.text.splitlines())
        assert any(event.get("type") == "response.completed" for event in events)
    assert len(seen_accounts) == 3
    assert seen_accounts[0] == seen_accounts[1]
    assert seen_accounts[2] != seen_accounts[1]
    assert "session_id" not in seen_headers[2]


@pytest.mark.asyncio
async def test_overload_after_auth_refresh_uses_deadline_recovery(async_client, monkeypatch):
    await _import_account(async_client, "refresh_overload", "refresh-overload@example.com")
    calls = 0
    refreshes = []

    async def ensure_fresh(self, account, *, force=False, **kwargs):
        refreshes.append(force)
        return account

    async def stream(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ProxyResponseError(401, openai_error("invalid_api_key", "Expired token"))
        if calls <= 4:
            yield _overload_sse_event("server_is_overloaded")
        else:
            yield _success_sse_event("refreshed_overload_recovered")

    monkeypatch.setattr(proxy_module.ProxyService, "_ensure_fresh", ensure_fresh)
    monkeypatch.setattr(proxy_module, "core_stream_responses", stream)
    monkeypatch.setattr(proxy_module, "_STREAM_MAX_ACCOUNT_ATTEMPTS", 1)
    monkeypatch.setattr(load_balancer_module, "_OVERLOAD_COOLDOWN_SECONDS", 0.001)
    monkeypatch.setattr(load_balancer_module, "_OVERLOAD_COOLDOWN_MAX_SECONDS", 0.001)
    response = await async_client.post(
        "/backend-api/codex/responses", json={"model": "gpt-5.1", "input": "hello", "stream": True}
    )
    assert response.status_code == 200
    events = _extract_events(response.text.splitlines())
    assert any(event.get("type") == "response.completed" for event in events)
    assert not any(event.get("type") in {"response.failed", "error"} for event in events)
    assert calls == 5
    assert refreshes.count(True) == 1
