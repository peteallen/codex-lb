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


@pytest.mark.parametrize("route", ["/backend-api/codex/responses", "/v1/responses"])
@pytest.mark.parametrize("call_type", ["function_call", "custom_tool_call", "apply_patch_call"])
@pytest.mark.parametrize("evidence", ["client_created", "confirmed", "missing", "other_response", "other_type"])
def test_anchored_websocket_preserves_calls_unless_upstream_confirmed_them(
    app_instance, monkeypatch, route, call_type, evidence
):
    call_id = "visualization_state_regression"
    call = {"type": call_type, "call_id": call_id}
    if call_type == "function_call":
        call.update(name="visualization_state", arguments="{}")
    else:
        call.update(input="state")
        if call_type == "custom_tool_call":
            call["name"] = "visualization_state"
    output = {"type": f"{call_type}_output", "call_id": call_id, "output": "state result"}
    user = {"role": "user", "content": "Fill the rest of the plate with more clips."}
    emitted_call = dict(call)
    if evidence == "other_type":
        emitted_call = {
            "type": "custom_tool_call" if call_type != "custom_tool_call" else "function_call",
            "call_id": call_id,
            "name": "different_tool",
            "input": "state",
            "arguments": "{}",
        }
    emitted = evidence in {"confirmed", "other_response", "other_type"}
    first_events = [{"type": "response.created", "response": {"id": "resp_first", "status": "in_progress"}}]
    if emitted:
        first_events.append(
            {"type": "response.output_item.done", "response_id": "resp_first", "output_index": 0, "item": emitted_call}
        )
    first_events.append(
        {
            "type": "response.completed",
            "response": {"id": "resp_first", "status": "completed", "output": [emitted_call] if emitted else []},
        }
    )

    class ValidatingUpstream(_SequencedUpstreamWebSocket):
        async def send_text(self, text):
            await super().send_text(text)
            payload = json.loads(text)
            if "previous_response_id" not in payload:
                return
            call_present = call in payload["input"]
            if call_present == (evidence != "confirmed"):
                event = {"type": "response.completed", "response": {"id": "resp_second", "status": "completed"}}
            else:
                event = {
                    "type": "error",
                    "error": {
                        "code": "invalid_request_error",
                        "message": (
                            "No tool call found for function call output" if not call_present else "Duplicate call"
                        ),
                    },
                }
            self._messages.put_nowait(_FakeUpstreamMessage("text", text=json.dumps(event)))

    upstream = ValidatingUpstream(
        [],
        deferred_message_batches=(
            [[_FakeUpstreamMessage("text", text=json.dumps(event)) for event in first_events]]
            if evidence != "missing"
            else []
        ),
    )

    class SettingsCache:
        async def get(self):
            return _websocket_settings()

    async def allow(*args, **kwargs):
        return None

    async def connect(self, headers, **kwargs):
        return SimpleNamespace(id="account_tool_trim"), upstream

    async def owner(self, **kwargs):
        return "account_tool_trim"

    monkeypatch.setattr(proxy_api_module, "_websocket_firewall_denial_response", allow)
    monkeypatch.setattr(proxy_api_module, "validate_proxy_api_key_authorization", allow)
    monkeypatch.setattr(proxy_module, "get_settings_cache", lambda: SettingsCache())
    monkeypatch.setattr(proxy_module.ProxyService, "_connect_proxy_websocket", connect)
    monkeypatch.setattr(proxy_module.ProxyService, "_resolve_websocket_previous_response_owner", owner)
    monkeypatch.setattr(proxy_module.ProxyService, "_write_request_log", allow)

    with TestClient(app_instance) as client:
        with client.websocket_connect(route) as websocket:
            if evidence != "missing":
                websocket.send_json({"type": "response.create", "model": "gpt-5.1", "input": "hello"})
                while websocket.receive_json()["type"] != "response.completed":
                    pass
            previous_response_id = "resp_other" if evidence == "other_response" else "resp_first"
            websocket.send_json(
                {
                    "type": "response.create",
                    "model": "gpt-5.1",
                    "previous_response_id": previous_response_id,
                    "input": [call, output, user],
                }
            )
            result = websocket.receive_json()
            while result["type"] == "codex.keepalive":
                result = websocket.receive_json()

    assert result["type"] == "response.completed", result
    sent = json.loads(upstream.sent_text[-1])
    assert sent["previous_response_id"] == previous_response_id
    assert sent["input"] == ([output, user] if evidence == "confirmed" else [call, output, user])
