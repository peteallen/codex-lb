from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

import app.core.clients.proxy as proxy_module
from app.core.clients.proxy import ProxyResponseError
from app.core.clients.proxy_websocket import (
    build_realtime_voice_websocket_headers,
    realtime_voice_header_diagnostics,
    realtime_voice_safe_error_code,
    realtime_voice_websocket_url,
)
from app.modules.proxy._service.realtime_voice import (
    _await_while_claim_owned,
    _safe_close_code,
    normalize_realtime_call_id,
    realtime_call_id_from_location,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("rtc_abc-123_DEF", "rtc_abc-123_DEF"),
        ("019eb97d-8e9a-7ff3-94b0-ea019babd5d7", "019eb97d-8e9a-7ff3-94b0-ea019babd5d7"),
        ("019EB97D-8E9A-7FF3-94B0-EA019BABD5D7", "019eb97d-8e9a-7ff3-94b0-ea019babd5d7"),
        ("call_123", None),
        ("rtc_", None),
        ("rtc_bad/path", None),
        ("../rtc_bad", None),
    ],
)
def test_normalize_realtime_call_id(value: str, expected: str | None) -> None:
    assert normalize_realtime_call_id(value) == expected


def test_realtime_call_id_from_location_matches_shipped_client_contract() -> None:
    assert (
        realtime_call_id_from_location(
            {"Location": "https://chatgpt.com/backend-api/codex/realtime/calls/rtc_abc-123?intent=quicksilver"}
        )
        == "rtc_abc-123"
    )
    assert (
        realtime_call_id_from_location({"Location": "https://chatgpt.com/trusted/%2Fopaque/../calls/rtc_opaque-prefix"})
        == "rtc_opaque-prefix"
    )
    assert (
        realtime_call_id_from_location({"location": "/v1/realtime/calls/019EB97D-8E9A-7FF3-94B0-EA019BABD5D7"})
        == "019eb97d-8e9a-7ff3-94b0-ea019babd5d7"
    )
    assert realtime_call_id_from_location({"location": "/v1/realtime/calls/call_123"}) is None
    assert realtime_call_id_from_location({"location": "/v1/realtime/calls/rtc_good/extra"}) is None
    assert realtime_call_id_from_location({"location": "/v1/realtime/calls/rtc_good/.."}) is None
    assert realtime_call_id_from_location({"location": "/v1/realtime/calls/rtc_good?x=1#fragment"}) is None
    assert realtime_call_id_from_location({"location": "/v1/realtime/calls/rtc_good%2Fbad"}) is None
    assert realtime_call_id_from_location({"location": "https://[invalid/rtc_good"}) is None
    assert realtime_call_id_from_location({}) is None


def test_realtime_voice_headers_replace_identity_and_strip_unsafe_transport_headers() -> None:
    headers = build_realtime_voice_websocket_headers(
        {
            "authorization": "Bearer local-codex-lb-key",
            "chatgpt-account-id": "wrong-account",
            "cookie": "session=secret",
            "connection": "upgrade, x-remove-me",
            "upgrade": "websocket",
            "sec-websocket-key": "handshake-key",
            "sec-websocket-protocol": "responses",
            "x-remove-me": "connection-nominated",
            "x-forwarded-for": "198.51.100.1",
            "openai-beta": "responses_websockets=2026-02-06, voice_other=v1",
            "openai-alpha": "quicksilver=v2",
            "x-session-id": "voice-session",
            "thread-id": "thread-1",
            "originator": "codex_chatgpt_desktop",
            "x-oai-attestation": "signed-call-attestation",
            "x-openai-device-attestation": "signed-attestation",
            "x-codex-installation-id": "bound-installation",
            "origin": "https://chatgpt.com",
            "proxy-experimental-feature": "must-not-forward",
            "x-openai-internal-admin": "must-not-forward",
            "x-random-client-header": "must-not-forward",
        },
        "upstream-access-token",
        "bound-account",
    )

    lowered = {key.lower(): value for key, value in headers.items()}
    assert lowered["authorization"] == "Bearer upstream-access-token"
    assert lowered["chatgpt-account-id"] == "bound-account"
    assert "openai-beta" not in lowered
    assert lowered["openai-alpha"] == "quicksilver=v2"
    assert lowered["x-session-id"] == "voice-session"
    assert lowered["thread-id"] == "thread-1"
    assert lowered["originator"] == "codex_chatgpt_desktop"
    assert lowered["x-oai-attestation"] == "signed-call-attestation"
    assert lowered["x-openai-device-attestation"] == "signed-attestation"
    assert lowered["origin"] == "https://chatgpt.com"
    for stripped in (
        "cookie",
        "connection",
        "upgrade",
        "sec-websocket-key",
        "sec-websocket-protocol",
        "x-codex-installation-id",
        "x-remove-me",
        "x-forwarded-for",
        "proxy-experimental-feature",
        "x-openai-internal-admin",
        "x-random-client-header",
    ):
        assert stripped not in lowered


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1000, 1000),
        (1014, 1014),
        (1005, 1011),
        (1015, 1011),
        (1016, 1011),
        (2999, 1011),
        (3000, 3000),
        (4999, 4999),
        (5000, 1011),
    ],
)
def test_realtime_voice_close_code_filters_reserved_values(value: int, expected: int) -> None:
    assert _safe_close_code(value, default=1011) == expected


def test_realtime_voice_headers_do_not_create_responses_beta_header() -> None:
    headers = build_realtime_voice_websocket_headers(
        {"openai-alpha": "quicksilver=v2"},
        "access-token",
        "account-id",
    )
    assert all(key.lower() != "openai-beta" for key in headers)


def test_realtime_voice_headers_reject_unknown_openai_alpha_capability() -> None:
    headers = build_realtime_voice_websocket_headers(
        {"openai-alpha": "internal-admin=v1"},
        "access-token",
        "account-id",
    )
    assert all(key.lower() != "openai-alpha" for key in headers)


@pytest.mark.parametrize(
    ("attestation", "envelope_valid", "version", "status", "token_present"),
    [
        ('{"v":1,"s":0,"t":"opaque-secret"}', True, 1, 0, True),
        ('{"v":1,"s":0,"t":""}', True, 1, 0, False),
        ('{"v":1,"s":1}', True, 1, 1, False),
        ('{"v":true,"s":0,"t":"opaque-secret"}', False, None, None, False),
        ('{"v":1,"s":0,"t":"opaque-secret","extra":1}', False, None, None, False),
        ("not-json", False, None, None, False),
    ],
)
def test_realtime_voice_header_diagnostics_expose_only_safe_attestation_shape(
    attestation: str,
    envelope_valid: bool,
    version: int | None,
    status: int | None,
    token_present: bool,
) -> None:
    diagnostics = realtime_voice_header_diagnostics(
        {
            "x-oai-attestation": attestation,
            "openai-alpha": "quicksilver=v2",
            "x-session-id": "secret-session",
            "thread-id": "secret-thread",
            "originator": "secret-originator",
            "user-agent": "secret-user-agent",
        }
    )

    assert diagnostics.attestation_present is True
    assert diagnostics.attestation_envelope_valid is envelope_valid
    assert diagnostics.attestation_version == version
    assert diagnostics.attestation_status == status
    assert diagnostics.attestation_token_present is token_present
    assert diagnostics.alpha_present is True
    assert diagnostics.alpha_valid is True
    assert diagnostics.session_header_present is True
    assert diagnostics.thread_header_present is True
    assert diagnostics.originator_header_present is True
    assert diagnostics.user_agent_header_present is True


@pytest.mark.parametrize(
    "attestation",
    [
        '{"v":1,"s":' + "9" * 5_000 + "}",
        "[" * 2_000 + "]" * 2_000,
    ],
)
def test_realtime_voice_header_diagnostics_reject_pathological_json_without_raising(attestation: str) -> None:
    diagnostics = realtime_voice_header_diagnostics({"x-oai-attestation": attestation})

    assert diagnostics.attestation_present is True
    assert diagnostics.attestation_envelope_valid is False
    assert diagnostics.attestation_version is None
    assert diagnostics.attestation_status is None
    assert diagnostics.attestation_token_present is False


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("forbidden", "forbidden"),
        ("invalid_api_key", "invalid_api_key"),
        ("sk_live_ABC123SECRET", "unclassified_upstream_error"),
        ("eyJhbGciOiJIUzI1NiJ9.payload.signature", "unclassified_upstream_error"),
        ("syntactically_valid_but_unknown", "unclassified_upstream_error"),
        ("evil\nlog-injection", "unclassified_upstream_error"),
    ],
)
def test_realtime_voice_error_code_logs_only_explicit_allowlist(code: str, expected: str) -> None:
    assert realtime_voice_safe_error_code({"error": {"code": code}}) == expected


@pytest.mark.parametrize(
    ("call_id", "expected"),
    [
        (
            "rtc_abc123",
            "wss://api.openai.com/v1/live/rtc_abc123?intent=quicksilver&architecture=avas",
        ),
        (
            "019eb97d-8e9a-7ff3-94b0-ea019babd5d7",
            "wss://api.openai.com/v1/live/019eb97d-8e9a-7ff3-94b0-ea019babd5d7?intent=quicksilver&architecture=avas",
        ),
    ],
)
def test_realtime_voice_websocket_url_routes_call_generation(call_id: str, expected: str) -> None:
    assert (
        realtime_voice_websocket_url(
            "https://chatgpt.com/backend-api",
            call_id,
            "intent=quicksilver&architecture=avas",
        )
        == expected
    )


@pytest.mark.asyncio
async def test_claim_owned_wait_cleans_resource_completed_during_cancellation() -> None:
    claim_renewal = asyncio.create_task(asyncio.sleep(60))
    cleanup = AsyncMock()
    waiter: asyncio.Task[object]
    resource = object()

    async def acquire_resource() -> object:
        # Queue cancellation before this task's completion wakes the waiter.
        # This deterministically exercises the ownership-transfer race.
        asyncio.get_running_loop().call_soon(waiter.cancel)
        return resource

    waiter = asyncio.create_task(
        _await_while_claim_owned(
            acquire_resource(),
            claim_renewal,
            on_abandoned=cleanup,
        )
    )
    with pytest.raises(asyncio.CancelledError):
        await waiter

    cleanup.assert_awaited_once_with(resource)
    claim_renewal.cancel()
    await asyncio.gather(claim_renewal, return_exceptions=True)


@pytest.mark.asyncio
async def test_claim_owned_wait_prioritizes_claim_loss_when_operation_also_completed() -> None:
    resource = object()
    cleanup = AsyncMock()

    async def acquire_resource() -> object:
        return resource

    async def lose_claim() -> None:
        raise RuntimeError("claim lost")

    operation = asyncio.create_task(acquire_resource())
    claim_renewal = asyncio.create_task(lose_claim())
    await asyncio.sleep(0)

    with pytest.raises(RuntimeError, match="claim lost"):
        await _await_while_claim_owned(
            operation,
            claim_renewal,
            on_abandoned=cleanup,
        )

    cleanup.assert_awaited_once_with(resource)


@pytest.mark.asyncio
async def test_realtime_call_payload_is_never_emitted_to_upstream_debug_log(monkeypatch) -> None:
    captured: list[dict[str, object]] = []

    class _FailingSession:
        def request(self, *_args, **_kwargs):
            raise RuntimeError("stop after request-start logging")

    monkeypatch.setattr(
        proxy_module,
        "get_settings",
        lambda: SimpleNamespace(
            upstream_base_url="https://chatgpt.com/backend-api",
            proxy_request_budget_seconds=75.0,
            upstream_connect_timeout_seconds=7.0,
            trace_channels=("upstream_summary", "upstream_payload"),
        ),
    )
    monkeypatch.setattr(proxy_module, "_maybe_log_upstream_request_start", lambda **kwargs: captured.append(kwargs))
    monkeypatch.setattr(proxy_module, "_maybe_log_upstream_request_complete", lambda **_kwargs: None)

    with pytest.raises(RuntimeError, match="stop after request-start logging"):
        await proxy_module.codex_control_request(
            "realtime/calls",
            method="POST",
            payload=b'{"sdp":"private-offer","session":{"instructions":"private"}}',
            query_params=[("intent", "quicksilver")],
            headers={"content-type": "application/json"},
            access_token="upstream-token",
            account_id="account-id",
            session=cast(Any, _FailingSession()),
        )

    assert len(captured) == 1
    assert captured[0]["kind"] == "codex_control_realtime_calls"
    assert captured[0]["payload_json"] is None
    assert captured[0]["payload_summary"] == ""


@pytest.mark.asyncio
async def test_realtime_call_echoed_error_is_not_emitted_to_upstream_debug_log(monkeypatch) -> None:
    sentinel = "private-sdp-or-session-sentinel"
    completed: list[dict[str, object]] = []

    class _ErrorResponse:
        status_code = 400
        headers = {"content-type": "application/json"}
        content = json.dumps({"error": {"code": "invalid_sdp", "message": sentinel}}).encode()

    class _ErrorClient:
        async def request(self, *_args, **_kwargs):
            return _ErrorResponse()

    monkeypatch.setattr(
        proxy_module,
        "get_settings",
        lambda: SimpleNamespace(
            upstream_base_url="https://chatgpt.com/backend-api",
            proxy_request_budget_seconds=75.0,
            upstream_connect_timeout_seconds=7.0,
            trace_channels=("upstream_summary", "upstream_payload"),
        ),
    )
    monkeypatch.setattr(proxy_module, "_maybe_log_upstream_request_start", lambda **_kwargs: None)
    monkeypatch.setattr(proxy_module, "_maybe_log_upstream_request_complete", lambda **kwargs: completed.append(kwargs))

    with pytest.raises(ProxyResponseError) as caught:
        await proxy_module.codex_control_request(
            "realtime/calls",
            method="POST",
            payload=b'{"sdp":"private-offer","session":{"instructions":"private"}}',
            query_params=[("intent", "quicksilver")],
            headers={"content-type": "application/json"},
            access_token="upstream-token",
            account_id="account-id",
            session=cast(Any, object()),
            route=cast(Any, object()),
            codex_client=cast(Any, _ErrorClient()),
        )

    assert caught.value.payload["error"]["message"] == sentinel
    assert len(completed) == 1
    assert completed[0]["error_code"] == "invalid_sdp"
    assert completed[0]["error_message"] is None
