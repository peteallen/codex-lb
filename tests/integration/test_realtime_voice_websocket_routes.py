from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import app.modules.proxy.api as proxy_api_module
from app.modules.proxy.service import ProxyService

pytestmark = pytest.mark.integration


def test_realtime_voice_websocket_routes_reach_dedicated_service(app_instance, monkeypatch) -> None:
    captured: list[tuple[str, str, object]] = []

    async def allow_auth(_websocket):
        return None, None

    async def proxy_voice(self, websocket, *, call_id, headers, query, api_key):
        del self, headers
        captured.append((call_id, query, api_key))
        await websocket.accept()
        await websocket.send_text(call_id)
        await websocket.close(code=1000)

    monkeypatch.setattr(proxy_api_module, "_validate_proxy_websocket_request", allow_auth)
    monkeypatch.setattr(ProxyService, "proxy_realtime_voice_websocket", proxy_voice)

    with TestClient(app_instance) as client:
        with client.websocket_connect(
            "/backend-api/codex/rtc_route_test?intent=quicksilver&intent=second&architecture=avas"
        ) as websocket:
            assert websocket.receive_text() == "rtc_route_test"
        with client.websocket_connect(
            "/backend-api/codex/019EB97D-8E9A-7FF3-94B0-EA019BABD5D7?architecture=avas"
        ) as websocket:
            assert websocket.receive_text() == "019eb97d-8e9a-7ff3-94b0-ea019babd5d7"

    assert captured == [
        ("rtc_route_test", "intent=quicksilver&intent=second&architecture=avas", None),
        ("019eb97d-8e9a-7ff3-94b0-ea019babd5d7", "architecture=avas", None),
    ]


def test_realtime_voice_does_not_capture_arbitrary_backend_websocket_path(app_instance) -> None:
    with TestClient(app_instance) as client:
        with pytest.raises(WebSocketDisconnect) as caught:
            with client.websocket_connect("/backend-api/codex/not-a-realtime-call"):
                pass

    assert caught.value.code == 1000
