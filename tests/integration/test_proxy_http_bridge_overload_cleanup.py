from __future__ import annotations

import asyncio
import contextlib

import pytest
from sqlalchemy import select

import app.modules.proxy.service as proxy_module
from app.db.models import ApiKeyUsageReservation
from app.db.session import SessionLocal
from app.dependencies import get_proxy_service_for_app
from app.modules.proxy.load_balancer import AccountSelection, LoadBalancer
from tests.integration.test_http_responses_bridge import (
    _get_account,
    _import_account,
    _install_bridge_settings,
    _PrecreatedOverloadUpstreamWebSocket,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_http_bridge_overload_cancellation_during_account_lease_release_cleans_up(
    async_client,
    app_instance,
    monkeypatch,
):
    _install_bridge_settings(monkeypatch, enabled=True)
    account_id = await _import_account(
        async_client,
        "acc_http_bridge_overload_cancel",
        "http-bridge-overload-cancel@example.com",
    )
    account = await _get_account(account_id)

    settings = (await async_client.get("/api/settings")).json()
    settings["apiKeyAuthEnabled"] = True
    assert (await async_client.put("/api/settings", json=settings)).status_code == 200
    created_key = await async_client.post(
        "/api/api-keys/",
        json={
            "name": "http-bridge-overload-cancel",
            "limits": [{"limitType": "total_tokens", "limitWindow": "weekly", "maxValue": 1_000_000}],
        },
    )
    assert created_key.status_code == 200
    key = created_key.json()

    upstream = _PrecreatedOverloadUpstreamWebSocket()

    async def select_account(self, deadline, **kwargs):
        del self, deadline, kwargs
        return AccountSelection(account=account, error_message=None, error_code=None)

    async def ensure_fresh(self, target, **kwargs):
        del self, kwargs
        return target

    async def connect_responses_websocket(headers, access_token, account_id_header, **kwargs):
        del headers, access_token, account_id_header, kwargs
        return upstream

    monkeypatch.setattr(proxy_module.ProxyService, "_select_account_with_budget", select_account)
    monkeypatch.setattr(proxy_module.ProxyService, "_ensure_fresh_with_budget", ensure_fresh)
    monkeypatch.setattr(proxy_module, "connect_responses_websocket", connect_responses_websocket)

    release_started = asyncio.Event()
    release_finished = asyncio.Event()
    release_gate = asyncio.Event()
    release_calls = []
    first_response_create_release = True
    original_release = LoadBalancer.release_account_lease

    async def release_account_lease(self, lease):
        nonlocal first_response_create_release
        if lease is not None:
            release_calls.append(lease)
        if lease is not None and lease.kind == "response_create" and first_response_create_release:
            first_response_create_release = False
            release_started.set()
            await release_gate.wait()
        try:
            await original_release(self, lease)
        finally:
            if lease is not None and lease.kind == "response_create":
                release_finished.set()

    monkeypatch.setattr(LoadBalancer, "release_account_lease", release_account_lease)

    async def consume_request() -> None:
        async with async_client.stream(
            "POST",
            "/backend-api/codex/responses",
            headers={"Authorization": f"Bearer {key['key']}"},
            json={"model": "gpt-5.1", "input": "cancel during overload cleanup", "stream": True},
        ) as response:
            assert response.status_code == 200
            async for _line in response.aiter_lines():
                pass

    request_task = asyncio.create_task(consume_request())
    service = get_proxy_service_for_app(app_instance)
    reader_task = None
    try:
        await asyncio.wait_for(release_started.wait(), timeout=5)
        async with SessionLocal() as session:
            reservations = list(
                await session.scalars(
                    select(ApiKeyUsageReservation).where(ApiKeyUsageReservation.api_key_id == key["id"])
                )
            )
            assert [reservation.status for reservation in reservations] == ["reserved"]

        sessions = list(service._http_bridge_sessions.values())
        assert sessions
        reader_task = sessions[0].upstream_reader

        request_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await request_task

        # The overload is handled by the bridge reader, so cancel that reader
        # while its account lease release is suspended. A cleanup path that
        # clears the lease reference before the await would leak capacity here.
        assert reader_task is not None
        reader_task.cancel()
        release_gate.set()
        with contextlib.suppress(asyncio.CancelledError):
            await reader_task
        await asyncio.wait_for(release_finished.wait(), timeout=5)

        if service._background_cleanup_tasks:
            await asyncio.gather(*service._background_cleanup_tasks)
        async with SessionLocal() as session:
            reservations = list(
                await session.scalars(
                    select(ApiKeyUsageReservation).where(ApiKeyUsageReservation.api_key_id == key["id"])
                )
            )
            assert [reservation.status for reservation in reservations] == ["released"]
        runtime = service._load_balancer._runtime[account_id]
        assert not runtime.leases
        assert any(lease.kind == "response_create" for lease in release_calls)
    finally:
        release_gate.set()
        if not request_task.done():
            request_task.cancel()
        await asyncio.gather(request_task, return_exceptions=True)
        if reader_task is not None and not reader_task.done():
            reader_task.cancel()
        if reader_task is not None:
            await asyncio.gather(reader_task, return_exceptions=True)
