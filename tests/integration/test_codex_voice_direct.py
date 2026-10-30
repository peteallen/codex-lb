from __future__ import annotations

import asyncio
import base64
import gzip
import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from multidict import CIMultiDict
from yarl import URL

from scripts import codex_voice_direct as voice

pytestmark = pytest.mark.integration
EMAIL = "voice@example.test"
ACCOUNT = "primary-account"
LOCAL_KEY = "test-local-key"
CALL_ID = "rtc_private_call_marker"
HEADERS = {"Authorization": f"Bearer {LOCAL_KEY}"}
SIDEBAND = f"{voice.BASE_PATH}/{CALL_ID}"


def write_login(root: Path, *, email: str = EMAIL, account: str = ACCOUNT, expires: float | None = None) -> str:
    payload = {
        "exp": int(time.time() + 3600 if expires is None else expires),
        "https://api.openai.com/auth": {"chatgpt_account_id": account},
        "https://api.openai.com/profile": {"email": email},
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    token = f"e30.{encoded}.test-signature"
    (root / "auth.json").write_text(
        json.dumps(
            {
                "auth_mode": "chatgpt",
                "tokens": {"access_token": token, "account_id": account, "refresh_token": "do-not-use"},
            }
        )
    )
    return token


def write_config(root: Path, key: str = LOCAL_KEY) -> None:
    (root / "config.toml").write_text(
        'model_provider = "codex-lb"\n[model_providers.codex-lb]\n'
        f'experimental_bearer_token = "{key}"\nbase_url = "http://127.0.0.1:2455/backend-api/codex"\n'
        '[model_providers.other]\nenv_key = "OTHER_API_KEY"\n'
    )


@dataclass
class Captured:
    path: str
    headers: CIMultiDict[str]
    body: bytes


@dataclass
class FakeOpenAI:
    received: list[Captured] = field(default_factory=list)
    status: int = 201
    location: str = f"/v1/realtime/calls/{CALL_ID}?private=location-marker#fragment"
    response_body: bytes = b"sdp-answer-marker"
    sideband_status: int = 101
    mode: str = "echo"
    protocol: str | None = None
    closed: asyncio.Event = field(default_factory=asyncio.Event)
    attached: asyncio.Event = field(default_factory=asyncio.Event)
    close_code: int | None = None
    close_reason: str | None = None
    handshake_entered: asyncio.Event = field(default_factory=asyncio.Event)

    async def create(self, request: web.Request) -> web.Response:
        self.received.append(Captured(request.raw_path, CIMultiDict(request.headers), await request.read()))
        return web.Response(
            status=self.status,
            body=self.response_body,
            headers={
                "Location": self.location,
                "Content-Type": "application/sdp",
                "Set-Cookie": "upstream-secret=hidden",
            },
        )

    async def sideband(self, request: web.Request) -> web.StreamResponse:
        self.received.append(Captured(request.raw_path, CIMultiDict(request.headers), b""))
        self.handshake_entered.set()
        if self.mode == "pending_handshake":
            try:
                await asyncio.Event().wait()
            finally:
                self.closed.set()
        if self.sideband_status != 101:
            return web.Response(
                status=self.sideband_status, text="upstream-private-error-marker", headers={"Location": "/trap"}
            )
        socket = web.WebSocketResponse(protocols=[self.protocol] if self.protocol else [], autoclose=False)
        await socket.prepare(request)
        self.attached.set()
        try:
            if self.mode == "close":
                await socket.close(code=1008, message=b"test close")
                return socket
            if self.mode == "abrupt":
                assert request.transport is not None
                request.transport.abort()
                return socket
            while True:
                message = await socket.receive()
                if message.type == aiohttp.WSMsgType.TEXT:
                    await socket.send_str(message.data)
                elif message.type == aiohttp.WSMsgType.BINARY:
                    await socket.send_bytes(message.data)
                elif message.type == aiohttp.WSMsgType.CLOSE:
                    self.close_code = message.data
                    self.close_reason = message.extra
                    await socket.close(code=message.data, message=(message.extra or "").encode())
                    break
                else:
                    break
        finally:
            self.closed.set()
        return socket


@dataclass
class Harness:
    root: Path
    token: str
    fake: FakeOpenAI
    client: TestClient

    async def create(self) -> None:
        response = await self.client.post(voice.CALL_PATH, headers=HEADERS, data=b"sdp-offer-marker")
        assert response.status == 201, await response.text()
        await response.read()

    @property
    def adapter(self) -> voice.VoiceAdapter:
        return self.client.app[voice.ADAPTER_KEY]


@pytest.fixture
async def harness(tmp_path: Path) -> AsyncIterator[Harness]:
    token = write_login(tmp_path)
    write_config(tmp_path)
    fake = FakeOpenAI()
    upstream_app = web.Application(handler_args={"auto_decompress": False, "access_log": None})
    upstream_app.router.add_post(voice.CALL_PATH, fake.create)
    upstream_app.router.add_get("/v1/live/{call_id}", fake.sideband)
    upstream_app.router.add_route("*", "/trap", fake.create)
    async with TestServer(upstream_app) as upstream:
        settings = voice.Settings(
            tmp_path,
            EMAIL,
            ACCOUNT,
            call_url=str(upstream.make_url(voice.CALL_PATH)),
            sideband_base=str(upstream.make_url("/v1/live")).replace("http:", "ws:", 1),
        )
        async with TestClient(
            TestServer(voice.create_app(settings), handler_cancellation=True, auto_decompress=False)
        ) as client:
            yield Harness(tmp_path, token, fake, client)


async def test_create_preserves_body_headers_and_primary_identity(
    harness: Harness, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="codex_voice_direct")
    before_config = (harness.root / "config.toml").read_bytes()
    before_login = (harness.root / "auth.json").read_bytes()
    body = gzip.compress(b"multipart-boundary\x00sdp-private-marker")
    headers = {
        **HEADERS,
        "Content-Type": "multipart/form-data; boundary=example",
        "Content-Encoding": "gzip",
        "ChatGPT-Account-ID": "wrong-account",
        "Cookie": "secret-cookie",
        "Proxy-Authorization": "secret-proxy",
        "x-api-key": "wrong-key",
        "OpenAI-Organization": "wrong-organization",
        "OpenAI-Project": "wrong-project",
        "openai-alpha": "realtime=v3",
        "openai-fedramp": "true",
        "x-openai-residency": "us",
        "x-codex-installation-id": "local-client-installation",
        "x-oai-attestation": "private-attestation-marker",
        "Connection": "x-codex-ignore",
        "x-codex-ignore": "must-not-forward",
        "session_id": "session-marker",
    }
    response = await harness.client.post(voice.CALL_PATH + "?intent=voice&flag=a&flag=b", headers=headers, data=body)
    assert response.status == 201
    assert await response.read() == harness.fake.response_body
    assert response.headers["Location"] == harness.fake.location
    assert response.headers["Content-Type"] == "application/sdp"
    assert "Set-Cookie" not in response.headers
    sent = harness.fake.received[0]
    assert sent.body == body
    assert sent.path.endswith("?intent=voice&flag=a&flag=b")
    assert sent.headers["Authorization"] == f"Bearer {harness.token}"
    assert sent.headers["ChatGPT-Account-ID"] == ACCOUNT
    for name in (
        "Cookie",
        "Proxy-Authorization",
        "x-api-key",
        "OpenAI-Organization",
        "OpenAI-Project",
        "x-codex-ignore",
    ):
        assert name not in sent.headers
    for name in (
        "Content-Type",
        "Content-Encoding",
        "openai-alpha",
        "openai-fedramp",
        "x-openai-residency",
        "x-codex-installation-id",
        "x-oai-attestation",
        "session_id",
    ):
        assert sent.headers[name] == headers[name]
    assert (harness.root / "config.toml").read_bytes() == before_config
    assert (harness.root / "auth.json").read_bytes() == before_login
    for value in (
        harness.token,
        LOCAL_KEY,
        CALL_ID,
        ACCOUNT,
        EMAIL,
        "private-attestation-marker",
        "sdp-private-marker",
        "location-marker",
    ):
        assert value not in caplog.text


async def test_sideband_preserves_frames_query_protocol_and_close(
    harness: Harness, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="codex_voice_direct")
    harness.fake.protocol = "voice-selected"
    await harness.create()
    path = URL(SIDEBAND + "?intent=voice&tag=a%2Bb&tag=c&private=query-marker", encoded=True)
    async with harness.client.ws_connect(
        path,
        headers={
            **HEADERS,
            "ChatGPT-Account-ID": "wrong",
            "openai-beta": "responses=experimental, responses_websockets=2026, realtime=v3",
            "x-oai-attestation": "attestation-marker",
        },
        protocols=["voice-first", "voice-selected"],
    ) as socket:
        assert socket.protocol == "voice-selected"
        await socket.send_str('{"opaque":"transcript-marker"}')
        assert (await socket.receive(timeout=2)).data == '{"opaque":"transcript-marker"}'
        await socket.send_bytes(b"\x00\xffaudio-marker")
        assert (await socket.receive(timeout=2)).data == b"\x00\xffaudio-marker"
        await socket.close(code=1000, message=b"client-finished")
    await asyncio.wait_for(harness.fake.closed.wait(), timeout=2)
    sent = harness.fake.received[1]
    assert sent.path == "/v1/live/" + CALL_ID + "?intent=voice&tag=a%2Bb&tag=c&private=query-marker"
    assert sent.headers["Authorization"] == f"Bearer {harness.token}"
    assert sent.headers["ChatGPT-Account-ID"] == ACCOUNT
    assert sent.headers["OpenAI-Beta"] == "realtime=v3"
    assert sent.headers.getall("Sec-WebSocket-Protocol") == ["voice-first,voice-selected"]
    assert harness.fake.close_code == 1000
    assert harness.fake.close_reason == "client-finished"
    for value in ("transcript-marker", "audio-marker", "query-marker", "attestation-marker", CALL_ID, LOCAL_KEY):
        assert value not in caplog.text


@pytest.mark.parametrize(
    "path",
    ["/responses", f"{voice.BASE_PATH}/responses", voice.CALL_PATH + "/", SIDEBAND + "/", "/v1/realtime?call_id=rtc_a"],
)
async def test_unrelated_or_trailing_slash_routes_never_reach_upstream(harness: Harness, path: str) -> None:
    response = await harness.client.post(path, headers=HEADERS)
    assert response.status in {404, 405}
    assert not harness.fake.received


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer wrong"},
        {**HEADERS, "Origin": "https://example.test"},
        [("Authorization", "Bearer wrong"), ("Authorization", f"Bearer {LOCAL_KEY}")],
    ],
)
async def test_authentication_rejects_unauthorized_call_and_sideband(harness: Harness, headers) -> None:
    created = await harness.client.post(voice.CALL_PATH, headers=headers)
    assert created.status in {401, 403}
    with pytest.raises(aiohttp.WSServerHandshakeError) as error:
        await harness.client.ws_connect(SIDEBAND, headers=headers)
    assert error.value.status in {401, 403}
    assert not harness.fake.received


@pytest.mark.parametrize(
    "kwargs,code",
    [
        ({"email": "different@example.test"}, "voice_identity_changed"),
        ({"account": "different-account"}, "voice_identity_changed"),
        ({"expires": 1}, "voice_login_expired"),
    ],
)
async def test_credentials_fail_closed_at_create_and_attach(harness: Harness, kwargs, code: str) -> None:
    await harness.create()
    write_login(harness.root, **kwargs)
    response = await harness.client.post(voice.CALL_PATH, headers=HEADERS)
    assert response.status == 503
    assert (await response.json())["error"]["code"] == code
    with pytest.raises(aiohttp.WSServerHandshakeError) as error:
        await harness.client.ws_connect(SIDEBAND, headers=HEADERS)
    assert error.value.status == 503
    assert len(harness.fake.received) == 1


async def test_missing_auth_and_malformed_provider_config_are_safe(harness: Harness) -> None:
    (harness.root / "auth.json").write_text("not valid json secret-marker")
    response = await harness.client.post(voice.CALL_PATH, headers=HEADERS)
    assert response.status == 503
    assert "secret-marker" not in await response.text()
    (harness.root / "config.toml").write_text("malformed = secret-marker")
    response = await harness.client.post(voice.CALL_PATH, headers=HEADERS)
    assert response.status == 503
    assert "secret-marker" not in await response.text()
    assert not harness.fake.received


async def test_token_rotation_is_picked_up_without_changing_auth_file(harness: Harness) -> None:
    await harness.create()
    token = write_login(harness.root, expires=time.time() + 7200)
    before = (harness.root / "auth.json").read_bytes()
    async with harness.client.ws_connect(SIDEBAND, headers=HEADERS) as socket:
        await socket.send_str("rotated")
        assert (await socket.receive(timeout=2)).data == "rotated"
    assert harness.fake.received[1].headers["Authorization"] == f"Bearer {token}"
    assert token != harness.token
    assert (harness.root / "auth.json").read_bytes() == before


@pytest.mark.parametrize(
    "location",
    [
        "",
        "realtime/calls/rtc_bad",
        "/v1/realtime/calls/rtc_bad/extra",
        "https://evil.test/v1/realtime/calls/rtc_bad",
        "//evil.test/v1/realtime/calls/rtc_bad",
        "https://secret@api.openai.com/v1/realtime/calls/rtc_bad",
    ],
)
async def test_invalid_success_location_is_not_exposed_or_replayed(harness: Harness, location: str) -> None:
    harness.fake.location = location
    response = await harness.client.post(voice.CALL_PATH, headers=HEADERS)
    assert response.status == 502
    assert harness.fake.response_body.decode() not in await response.text()
    assert len(harness.fake.received) == 1
    assert not harness.adapter.bindings


@pytest.mark.parametrize("call_id", ["rtc_with.~_chars", "12345678-1234-1234-1234-123456789abc"])
async def test_supported_location_identifiers_attach(harness: Harness, call_id: str) -> None:
    harness.fake.location = f"https://api.openai.com/v1/realtime/calls/{call_id}"
    await harness.create()
    async with harness.client.ws_connect(f"{voice.BASE_PATH}/{call_id}", headers=HEADERS) as socket:
        await socket.send_str("ok")
        assert (await socket.receive(timeout=2)).data == "ok"


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
async def test_http_denial_and_redirect_are_not_replayed(harness: Harness, status: int) -> None:
    harness.fake.status = status
    harness.fake.location = "/trap"
    harness.fake.response_body = b"private-upstream-body"
    response = await harness.client.post(voice.CALL_PATH, headers=HEADERS)
    assert response.status == (502 if status == 302 else status)
    assert "private-upstream-body" not in await response.text()
    assert len(harness.fake.received) == 1


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
async def test_sideband_denial_and_redirect_do_not_replay(harness: Harness, status: int) -> None:
    await harness.create()
    harness.fake.sideband_status = status
    with pytest.raises(aiohttp.WSServerHandshakeError) as error:
        await harness.client.ws_connect(SIDEBAND, headers=HEADERS)
    assert error.value.status == (502 if status == 302 else status)
    assert len(harness.fake.received) == 2
    assert not any(binding.active for binding in harness.adapter.bindings.values())


@pytest.mark.parametrize("mode", ["unknown", "expired", "key-rotated", "duplicate-query", "active"])
async def test_unbound_or_conflicting_attachments_fail(harness: Harness, mode: str) -> None:
    await harness.create()
    path = SIDEBAND
    headers = HEADERS
    existing = None
    if mode == "unknown":
        path += "_unknown"
    elif mode == "expired":
        for binding in harness.adapter.bindings.values():
            binding.expires = 0
    elif mode == "key-rotated":
        write_config(harness.root, "new-key")
        headers = {"Authorization": "Bearer new-key"}
    elif mode == "duplicate-query":
        path += "?call_id=" + CALL_ID
    else:
        existing = await harness.client.ws_connect(path, headers=headers)
    try:
        with pytest.raises(aiohttp.WSServerHandshakeError) as error:
            await harness.client.ws_connect(path, headers=headers)
        assert error.value.status in {400, 404, 409}
        assert len(harness.fake.received) == (2 if existing else 1)
    finally:
        if existing:
            await existing.close()


@pytest.mark.parametrize("mode,code", [("close", 1008), ("abrupt", 1011)])
async def test_upstream_disconnect_closes_client(harness: Harness, mode: str, code: int) -> None:
    await harness.create()
    harness.fake.mode = mode
    async with harness.client.ws_connect(SIDEBAND, headers=HEADERS) as socket:
        message = await socket.receive(timeout=2)
        assert message.type == aiohttp.WSMsgType.CLOSE
        assert message.data == code
        if mode == "close":
            assert message.extra == "test close"
    await asyncio.wait_for(harness.fake.closed.wait(), timeout=2)


async def test_shutdown_closes_owned_sockets_and_tasks(harness: Harness) -> None:
    await harness.create()
    socket = await harness.client.ws_connect(SIDEBAND, headers=HEADERS)
    await asyncio.wait_for(harness.fake.attached.wait(), timeout=2)
    await asyncio.wait_for(harness.client.close(), timeout=5)
    assert socket.closed
    await asyncio.wait_for(harness.fake.closed.wait(), timeout=2)
    assert not harness.adapter.sockets
    assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("voice-") and not task.done()]


async def test_body_and_registry_limits_prevent_unbounded_work(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = await harness.client.post(voice.CALL_PATH, headers=HEADERS, data=b"a" * (voice.MAX_BODY + 1))
    assert response.status == 413
    assert not harness.fake.received
    monkeypatch.setattr(voice, "MAX_CALLS", 1)
    await harness.create()
    response = await harness.client.post(voice.CALL_PATH, headers=HEADERS)
    assert response.status == 503
    assert len(harness.fake.received) == 1


async def test_websocket_lifetime_has_no_http_or_idle_timeout(harness: Harness) -> None:
    await harness.create()
    # Shrink setup timeout to expose any accidental whole-session deadline.
    harness.adapter.session._timeout = aiohttp.ClientTimeout(total=0.05, connect=0.05, sock_read=0.05)
    async with harness.client.ws_connect(SIDEBAND, headers=HEADERS) as socket:
        await asyncio.sleep(0.15)
        await socket.send_str("still-connected")
        assert (await socket.receive(timeout=2)).data == "still-connected"


async def test_cancelled_handshake_releases_binding_and_upstream(harness: Harness) -> None:
    await harness.create()
    harness.fake.mode = "pending_handshake"
    connecting = asyncio.create_task(harness.client.ws_connect(SIDEBAND, headers=HEADERS))
    await asyncio.wait_for(harness.fake.handshake_entered.wait(), timeout=2)
    connecting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await connecting
    await asyncio.wait_for(harness.fake.closed.wait(), timeout=2)
    assert not any(binding.active for binding in harness.adapter.bindings.values())
    assert not harness.adapter.sockets


async def test_connect_timeout_is_fixed_and_never_replayed(harness: Harness) -> None:
    await harness.create()
    harness.fake.mode = "pending_handshake"
    harness.adapter.session._timeout = aiohttp.ClientTimeout(total=0.05)
    with pytest.raises(aiohttp.WSServerHandshakeError) as error:
        await harness.client.ws_connect(SIDEBAND, headers=HEADERS)
    assert error.value.status == 504
    await asyncio.wait_for(harness.fake.closed.wait(), timeout=2)
    assert len(harness.fake.received) == 2
    assert not any(binding.active for binding in harness.adapter.bindings.values())


async def test_oversize_response_is_not_exposed_or_bound(harness: Harness) -> None:
    harness.fake.response_body = b"a" * (voice.MAX_BODY + 1)
    response = await harness.client.post(voice.CALL_PATH, headers=HEADERS)
    assert response.status == 502
    assert not harness.adapter.bindings
    assert len(harness.fake.received) == 1


async def test_oversize_frame_closes_sideband(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(voice, "MAX_MESSAGE", 64)
    await harness.create()
    async with harness.client.ws_connect(SIDEBAND, headers=HEADERS) as socket:
        await socket.send_bytes(b"a" * 65)
        message = await socket.receive(timeout=2)
        assert message.type == aiohttp.WSMsgType.CLOSE
        assert message.data == 1009
    await asyncio.wait_for(harness.fake.closed.wait(), timeout=2)
