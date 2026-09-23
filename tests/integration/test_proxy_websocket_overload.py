from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.modules.proxy.api as proxy_api_module
import app.modules.proxy.service as proxy_module
from tests.integration.test_proxy_websocket_responses import (
    _FakeUpstreamMessage,
    _SequencedUpstreamWebSocket,
    _websocket_settings,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("owner_bound", [False, True])
@pytest.mark.parametrize("error_code", ["server_is_overloaded", "overloaded_error"])
def test_websocket_repeated_overload_recovers_without_spending_replay_limit(
    app_instance, monkeypatch, owner_bound, error_code
):
    upstreams = []
    for attempt in range(5):
        event = (
            {"type": "response.failed", "response": {"error": {"code": error_code, "message": "Upstream overloaded"}}}
            if attempt < 4
            else {"type": "response.completed", "response": {"id": "resp_overload_ok", "status": "completed"}}
        )
        upstreams.append(
            _SequencedUpstreamWebSocket(
                [], deferred_message_batches=[[_FakeUpstreamMessage("text", text=json.dumps(event))]]
            )
        )
    selected = []
    states = []

    class Cache:
        async def get(self):
            return _websocket_settings()

    async def allow(*args, **kwargs):
        return None

    async def owner(self, **kwargs):
        return "owner"

    async def connect(self, headers, *, request_state, **kwargs):
        # Exercise the real downstream route and replay state. Selector/cooldown
        # scheduling is verified separately against real imported accounts.
        account_id = request_state.preferred_account_id or f"account-{len(selected)}"
        selected.append(account_id)
        states.append((request_state.replay_count, request_state.overload_recovery_count))
        if owner_bound:
            assert account_id == "owner"
            assert json.loads(request_state.request_text)["previous_response_id"] == "resp_owner"
        elif len(selected) > 1:
            assert request_state.affinity_policy.selection_key is None
        return SimpleNamespace(id=account_id), upstreams[len(selected) - 1]

    monkeypatch.setattr(proxy_api_module, "_websocket_firewall_denial_response", allow)
    monkeypatch.setattr(proxy_api_module, "validate_proxy_api_key_authorization", allow)
    monkeypatch.setattr(proxy_module, "get_settings_cache", lambda: Cache())
    monkeypatch.setattr(proxy_module.ProxyService, "_resolve_websocket_previous_response_owner", owner)
    monkeypatch.setattr(proxy_module.ProxyService, "_connect_proxy_websocket", connect)
    monkeypatch.setattr(proxy_module.ProxyService, "_write_request_log", allow)
    request = {"type": "response.create", "model": "gpt-5.1", "input": [{"role": "user", "content": "hello"}]}
    if owner_bound:
        request["previous_response_id"] = "resp_owner"
    with TestClient(app_instance, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
        with client.websocket_connect("/backend-api/codex/responses") as websocket:
            websocket.send_json(request)
            event = websocket.receive_json()
            while event["type"] == "codex.keepalive":
                event = websocket.receive_json()
    assert event["type"] == "response.completed"
    assert len(selected) == 5
    assert states == [(0, n) for n in range(5)]
    assert all(len(upstream.sent_text) == 1 for upstream in upstreams)


@pytest.mark.parametrize("accepted", [True, False])
def test_websocket_overload_after_acceptance_or_visible_progress_does_not_replay(app_instance, monkeypatch, accepted):
    events = []
    if not accepted:
        events.append({"type": "response.output_text.delta", "delta": "visible"})
    terminal = {
        "type": "response.failed",
        "response": {
            **({"id": "resp_accepted"} if accepted else {}),
            "error": {"code": "server_is_overloaded", "message": "overloaded"},
        },
    }
    events.append(terminal)
    upstream = _SequencedUpstreamWebSocket(
        [], deferred_message_batches=[[_FakeUpstreamMessage("text", text=json.dumps(e)) for e in events]]
    )
    calls = 0

    class Cache:
        async def get(self):
            return _websocket_settings()

    async def allow(*args, **kwargs):
        return None

    async def connect(self, headers, **kwargs):
        nonlocal calls
        calls += 1
        return SimpleNamespace(id="account"), upstream

    monkeypatch.setattr(proxy_api_module, "_websocket_firewall_denial_response", allow)
    monkeypatch.setattr(proxy_api_module, "validate_proxy_api_key_authorization", allow)
    monkeypatch.setattr(proxy_module, "get_settings_cache", lambda: Cache())
    monkeypatch.setattr(proxy_module.ProxyService, "_connect_proxy_websocket", connect)
    monkeypatch.setattr(proxy_module.ProxyService, "_write_request_log", allow)
    with TestClient(app_instance, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
        with client.websocket_connect("/backend-api/codex/responses") as websocket:
            websocket.send_json({"type": "response.create", "model": "gpt-5.1", "input": "hello"})
            for _ in events:
                event = websocket.receive_json()
    assert event["type"] == "response.failed"
    assert calls == 1


@pytest.mark.parametrize("account_count", [1, 2])
def test_websocket_overload_real_selection_waits_or_uses_alternate(app_instance, monkeypatch, account_count):
    import app.modules.proxy.load_balancer as balancer_module
    from tests.integration.test_proxy_transient_retry import _make_auth_json

    calls = []
    waits = []
    released_response_create_accounts = []
    original_release = balancer_module.LoadBalancer.release_account_lease
    from app.modules.proxy._service.websocket import mixin as websocket_mixin

    original_wait = websocket_mixin._sleep_for_account_selection_recovery

    async def open_attempt(self, account, headers, **kwargs):
        calls.append(account.id)
        if len(calls) > 1:
            assert calls[0] in released_response_create_accounts
        event = (
            {
                "type": "response.failed",
                "response": {"error": {"code": "server_is_overloaded", "message": "overloaded"}},
            }
            if len(calls) == 1
            else {"type": "response.completed", "response": {"id": "resp_real_selection", "status": "completed"}}
        )
        return account, _SequencedUpstreamWebSocket(
            [], deferred_message_batches=[[_FakeUpstreamMessage("text", text=json.dumps(event))]]
        )

    async def wait(selection, **kwargs):
        waits.append(selection.error_code)
        return await original_wait(selection, **kwargs)

    async def allow(*args, **kwargs):
        return None

    async def release(self, lease):
        if lease is not None and lease.kind == "response_create":
            released_response_create_accounts.append(lease.account_id)
        await original_release(self, lease)

    monkeypatch.setattr(proxy_api_module, "_websocket_firewall_denial_response", allow)
    monkeypatch.setattr(proxy_api_module, "validate_proxy_api_key_authorization", allow)
    monkeypatch.setattr(proxy_module.ProxyService, "_try_open_websocket_connect_attempt", open_attempt)
    monkeypatch.setattr(proxy_module.ProxyService, "_write_request_log", allow)
    monkeypatch.setattr(balancer_module.LoadBalancer, "release_account_lease", release)
    monkeypatch.setattr(balancer_module, "_OVERLOAD_COOLDOWN_SECONDS", 5.0)
    monkeypatch.setattr(balancer_module, "_OVERLOAD_COOLDOWN_MAX_SECONDS", 5.0)
    monkeypatch.setattr(websocket_mixin, "_sleep_for_account_selection_recovery", wait)
    with TestClient(app_instance, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
        for index in range(account_count):
            auth = _make_auth_json(f"ws-overload-{index}", f"ws-overload-{index}@example.com")
            imported = client.post(
                "/api/accounts/import", files={"auth_json": ("auth.json", json.dumps(auth), "application/json")}
            )
            assert imported.status_code == 200
        with client.websocket_connect("/backend-api/codex/responses") as websocket:
            websocket.send_json({"type": "response.create", "model": "gpt-5.1", "input": "hello"})
            event = websocket.receive_json()
            while event["type"] == "codex.keepalive":
                event = websocket.receive_json()
    assert event["type"] == "response.completed"
    assert len(calls) == 2
    if account_count == 1:
        assert calls[0] == calls[1]
        assert waits
    else:
        assert calls[0] != calls[1]
        assert not waits


def test_websocket_cancel_during_overload_cleanup_keeps_request_owned(app_instance, monkeypatch):
    import asyncio
    import threading

    from app.modules.proxy.load_balancer import LoadBalancer

    entered = threading.Event()
    readers = []
    released = []
    original_release = proxy_module.ProxyService._release_websocket_request_state_reservation
    event = {
        "type": "response.failed",
        "response": {"error": {"code": "server_is_overloaded", "message": "overloaded"}},
    }
    upstream = _SequencedUpstreamWebSocket(
        [], deferred_message_batches=[[_FakeUpstreamMessage("text", text=json.dumps(event))]]
    )

    class Cache:
        async def get(self):
            return _websocket_settings()

    async def allow(*args, **kwargs):
        return None

    async def connect(self, headers, **kwargs):
        return SimpleNamespace(id="cancel-overload"), upstream

    async def overload(self, account):
        readers.append(asyncio.current_task())
        entered.set()
        await asyncio.Event().wait()

    async def release(self, request_state, *args, **kwargs):
        released.append(request_state.request_id)
        await original_release(self, request_state, *args, **kwargs)

    monkeypatch.setattr(proxy_api_module, "_websocket_firewall_denial_response", allow)
    monkeypatch.setattr(proxy_api_module, "validate_proxy_api_key_authorization", allow)
    monkeypatch.setattr(proxy_module, "get_settings_cache", lambda: Cache())
    monkeypatch.setattr(proxy_module.ProxyService, "_connect_proxy_websocket", connect)
    monkeypatch.setattr(proxy_module.ProxyService, "_write_request_log", allow)
    monkeypatch.setattr(proxy_module.ProxyService, "_release_websocket_request_state_reservation", release)
    monkeypatch.setattr(LoadBalancer, "record_overload", overload)
    with TestClient(app_instance) as client:
        with client.websocket_connect("/backend-api/codex/responses") as websocket:
            websocket.send_json({"type": "response.create", "model": "gpt-5.1", "input": "hello"})
            assert entered.wait(timeout=5)
            assert client.portal is not None
            client.portal.call(readers[0].cancel)
    assert len(released) == 1


def test_websocket_cancel_during_overload_account_lease_release_cleans_capacity(app_instance, monkeypatch):
    import asyncio
    import threading

    from app.modules.proxy.load_balancer import LoadBalancer

    release_started = threading.Event()
    release_gate = asyncio.Event()
    readers = []
    release_calls = []
    first_response_release = True
    original_release = LoadBalancer.release_account_lease
    original_overload = LoadBalancer.record_overload
    event = {
        "type": "response.failed",
        "response": {"error": {"code": "server_is_overloaded", "message": "overloaded"}},
    }
    upstream = _SequencedUpstreamWebSocket(
        [], deferred_message_batches=[[_FakeUpstreamMessage("text", text=json.dumps(event))]]
    )

    class Cache:
        async def get(self):
            return _websocket_settings()

    async def allow(*args, **kwargs):
        return None

    async def connect(self, headers, **kwargs):
        return SimpleNamespace(id="cancel-overload-lease"), upstream

    async def release(self, lease):
        nonlocal first_response_release
        if lease is not None:
            release_calls.append(lease)
        if lease is not None and lease.kind == "response_create" and first_response_release:
            first_response_release = False
            release_started.set()
            await release_gate.wait()
        await original_release(self, lease)

    async def overload(self, account):
        readers.append(asyncio.current_task())
        await original_overload(self, account)

    monkeypatch.setattr(proxy_api_module, "_websocket_firewall_denial_response", allow)
    monkeypatch.setattr(proxy_api_module, "validate_proxy_api_key_authorization", allow)
    monkeypatch.setattr(proxy_module, "get_settings_cache", lambda: Cache())
    monkeypatch.setattr(proxy_module.ProxyService, "_connect_proxy_websocket", connect)
    monkeypatch.setattr(proxy_module.ProxyService, "_write_request_log", allow)
    monkeypatch.setattr(LoadBalancer, "release_account_lease", release)
    monkeypatch.setattr(LoadBalancer, "record_overload", overload)
    with TestClient(app_instance) as client:
        with client.websocket_connect("/backend-api/codex/responses") as websocket:
            websocket.send_json({"type": "response.create", "model": "gpt-5.1", "input": "hello"})
            assert release_started.wait(timeout=5)
            assert client.portal is not None
            client.portal.call(readers[0].cancel)
            client.portal.call(release_gate.set)

    from app.dependencies import get_proxy_service_for_app

    service = get_proxy_service_for_app(app_instance)
    runtime = service._load_balancer._runtime["cancel-overload-lease"]
    assert runtime.leases is None or not runtime.leases
    assert sum(lease.kind == "response_create" for lease in release_calls) == 1
