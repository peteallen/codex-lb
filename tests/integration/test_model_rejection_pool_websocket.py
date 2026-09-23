from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import app.modules.proxy.api as proxy_api
import app.modules.proxy.service as proxy_service
from app.db.models import StickySession, StickySessionKind
from app.db.session import SessionLocal
from tests.integration.test_proxy_transient_retry import _make_auth_json
from tests.integration.test_proxy_websocket_responses import _FakeUpstreamMessage, _SequencedUpstreamWebSocket

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("path", ["/backend-api/codex/responses", "/v1/responses"])
@pytest.mark.parametrize("model", ["gpt-6-sol", "gpt-6-luna"])
@pytest.mark.parametrize("all_reject", [False, True])
def test_websocket_model_rejections_visit_each_eligible_account_once(
    app_instance, monkeypatch, path, model, all_reject
):
    opened = []
    upstreams = []
    replay_counts = []
    health_errors = []

    async def allow(*args, **kwargs):
        return None

    async def health(self, account, error, code, **kwargs):
        health_errors.append(code)

    async def open_attempt(self, account, headers, *, request_state, **kwargs):
        assert account.id not in opened
        assert request_state.excluded_account_ids == set(opened)
        opened.append(account.id)
        replay_counts.append(request_state.replay_count)
        error = {
            "type": "error",
            "status": 404,
            "error": {
                "type": "invalid_request_error",
                "code": "model_not_found",
                "message": f"The model `{model}` does not exist or you do not have access to it.",
            },
        }
        event = (
            error
            if all_reject or len(opened) < 4
            else {"type": "response.completed", "response": {"id": "resp_pool_supported", "status": "completed"}}
        )
        upstream = _SequencedUpstreamWebSocket(
            [], deferred_message_batches=[[_FakeUpstreamMessage("text", text=json.dumps(event))]]
        )
        upstreams.append(upstream)
        return account, upstream

    monkeypatch.setattr(proxy_api, "_websocket_firewall_denial_response", allow)
    monkeypatch.setattr(proxy_api, "validate_proxy_api_key_authorization", allow)
    monkeypatch.setattr(proxy_service.ProxyService, "_try_open_websocket_connect_attempt", open_attempt)
    monkeypatch.setattr(proxy_service.ProxyService, "_handle_stream_error", health)

    with TestClient(app_instance, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
        for i in range(4):
            auth = _make_auth_json(f"model-pool-{i}", f"pool-{i}@example.com")
            response = client.post(
                "/api/accounts/import", files={"auth_json": ("auth.json", json.dumps(auth), "application/json")}
            )
            assert response.status_code == 200
        with client.websocket_connect(path) as websocket:
            websocket.send_json({"type": "response.create", "model": model, "input": "hello"})
            event = websocket.receive_json()
            while event["type"] == "codex.keepalive":
                event = websocket.receive_json()

    assert len(opened) == 4
    assert replay_counts == [0, 0, 0, 0]
    assert all(len(upstream.sent_text) == 1 for upstream in upstreams)
    assert all(json.loads(upstream.sent_text[0])["model"] == model for upstream in upstreams)
    assert not health_errors
    if all_reject:
        error = event.get("error") or event["response"]["error"]
        assert error["code"] == "model_not_found"
        assert error["message"] == f"The model `{model}` does not exist or you do not have access to it."
    else:
        assert event["type"] == "response.completed"


@pytest.mark.parametrize("model", ["gpt-6-sol", "gpt-6-luna"])
def test_websocket_model_rejection_escapes_legacy_hard_session_owner(app_instance, monkeypatch, model):
    path = "/backend-api/codex/responses"
    first_raw_id = f"model-hard-owner-{model}"
    second_raw_id = f"model-hard-replacement-{model}"
    session_id = f"model-hard-session-{model}"
    opened: list[str] = []
    seen_headers: list[dict[str, str]] = []
    upstreams: list[_SequencedUpstreamWebSocket] = []

    async def allow(*args, **kwargs):
        del args, kwargs
        return None

    def import_account(client, raw_account_id: str, email: str) -> str:
        response = client.post(
            "/api/accounts/import",
            files={
                "auth_json": (
                    "auth.json",
                    json.dumps(_make_auth_json(raw_account_id, email)),
                    "application/json",
                )
            },
        )
        assert response.status_code == 200
        return response.json()["accountId"]

    async def create_legacy_mapping(first_account_id: str) -> None:
        async with SessionLocal() as session:
            session.add(
                StickySession(
                    key=session_id,
                    kind=StickySessionKind.CODEX_SESSION,
                    account_id=first_account_id,
                )
            )
            await session.commit()

    async def open_attempt(self, account, headers, *, request_state, **kwargs):
        del self, kwargs
        assert account.id not in opened
        assert request_state.excluded_account_ids == set(opened)
        opened.append(account.id)
        seen_headers.append(dict(headers))
        event = (
            {
                "type": "error",
                "status": 404,
                "error": {
                    "type": "invalid_request_error",
                    "code": "model_not_found",
                    "message": f"The model `{model}` does not exist or you do not have access to it.",
                },
            }
            if len(opened) == 1
            else {"type": "response.completed", "response": {"id": "resp_hard_session_recovered"}}
        )
        upstream = _SequencedUpstreamWebSocket(
            [], deferred_message_batches=[[_FakeUpstreamMessage("text", text=json.dumps(event))]]
        )
        upstreams.append(upstream)
        return account, upstream

    monkeypatch.setattr(proxy_api, "_websocket_firewall_denial_response", allow)
    monkeypatch.setattr(proxy_api, "validate_proxy_api_key_authorization", allow)
    monkeypatch.setattr(proxy_service.ProxyService, "_try_open_websocket_connect_attempt", open_attempt)

    with TestClient(app_instance, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
        first_account_id = import_account(client, first_raw_id, f"{first_raw_id}@example.com")
        second_account_id = import_account(client, second_raw_id, f"{second_raw_id}@example.com")
        assert client.portal is not None
        client.portal.call(create_legacy_mapping, first_account_id)
        with client.websocket_connect(path, headers={"session_id": session_id}) as websocket:
            websocket.send_json({"type": "response.create", "model": model, "input": "hello"})
            event = websocket.receive_json()
            while event["type"] == "codex.keepalive":
                event = websocket.receive_json()

    assert event["type"] == "response.completed"
    assert opened == [first_account_id, second_account_id]
    assert "session_id" in seen_headers[0]
    assert all(header.lower() != "session_id" for header in seen_headers[1])
    assert all(len(upstream.sent_text) == 1 for upstream in upstreams)
