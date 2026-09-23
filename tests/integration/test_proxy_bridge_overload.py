from __future__ import annotations

import pytest

import app.modules.proxy.load_balancer as balancer_module
import app.modules.proxy.service as proxy_module
from app.dependencies import get_proxy_service_for_app
from app.modules.proxy._service.http_bridge import mixin as bridge_mixin
from tests.integration.test_http_responses_bridge import (
    _FakeBridgeUpstreamWebSocket,
    _import_account,
    _install_bridge_settings,
    _PrecreatedOverloadUpstreamWebSocket,
)
from tests.integration.test_proxy_transient_retry import _extract_events

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/v1/responses", "/backend-api/codex/responses"])
@pytest.mark.parametrize("account_count,owner_kind", [(1, None), (2, None), (2, "file"), (2, "previous_response")])
async def test_bridge_repeated_overload_waits_or_uses_alternate_capacity(
    async_client, app_instance, monkeypatch, path, account_count, owner_kind
):
    _install_bridge_settings(monkeypatch, enabled=True)
    owner_id = None
    for index in range(account_count):
        account_id = await _import_account(
            async_client, f"bridge-overload-{index}", f"bridge-overload-{index}@example.com"
        )
        owner_id = owner_id or account_id
    service = get_proxy_service_for_app(app_instance)
    accounts = []
    headers_seen = []
    waits = []

    async def ensure_fresh(account, **kwargs):
        return account

    class WarmThenOverloaded(_PrecreatedOverloadUpstreamWebSocket):
        async def send_text(self, text):
            if not self.sent_text:
                await _FakeBridgeUpstreamWebSocket.send_text(self, text)
            else:
                await super().send_text(text)

    async def connect(headers, access_token, account_id_header, **kwargs):
        accounts.append(account_id_header)
        headers_seen.append(headers)
        if owner_kind == "previous_response" and len(accounts) == 1:
            return WarmThenOverloaded()
        if len(accounts) <= 4:
            return _PrecreatedOverloadUpstreamWebSocket()
        return _FakeBridgeUpstreamWebSocket("resp_recovered_overload")

    async def wait(selection, **kwargs):
        waits.append((len(accounts), selection.error_code))
        # Advance only the overload cooldown; selection and resource leases
        # remain real, so a fresh request uses the same routing contract.
        for runtime in service._load_balancer._runtime.values():
            runtime.overload_cooldown_until = 0.0
        return True

    monkeypatch.setattr(service, "_ensure_fresh_with_budget", ensure_fresh)
    monkeypatch.setattr(proxy_module, "connect_responses_websocket", connect)
    monkeypatch.setattr(bridge_mixin, "_sleep_for_account_selection_recovery", wait)
    monkeypatch.setattr(balancer_module, "_OVERLOAD_COOLDOWN_SECONDS", 30.0)
    body = {"model": "gpt-5.1", "input": "hello", "stream": True, "prompt_cache_key": "bridge-overload"}
    if owner_kind == "file":
        assert owner_id is not None
        await service._pin_file_account("file_overload_bridge", owner_id)
        body["input"] = [{"role": "user", "content": [{"type": "input_file", "file_id": "file_overload_bridge"}]}]
    elif owner_kind == "previous_response":
        warm = await async_client.post(path, json=body, headers={"session_id": "bridge-overload-soft-session"})
        assert warm.status_code == 200
        warm_events = _extract_events(warm.text.splitlines())
        body["previous_response_id"] = warm_events[-1]["response"]["id"]
    response = await async_client.post(
        path,
        json=body,
        headers={"session_id": "bridge-overload-soft-session"},
    )
    assert response.status_code == 200, response.text
    events = _extract_events(response.text.splitlines())
    assert events[-1]["type"] == "response.completed"
    assert not any(event["type"] in {"error", "response.failed"} for event in events)
    assert len(accounts) == 5
    assert waits
    if account_count == 1 or owner_kind is not None:
        assert len(set(accounts)) == 1
        assert waits[0][0] == 1
    else:
        assert accounts[0] != accounts[1]
        assert waits[0][0] == 2
        assert "session_id" not in headers_seen[1]
