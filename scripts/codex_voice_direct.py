"""Optional loopback adapter for the official Codex client's private voice routes.

This process is independent of codex-lb. See docs/live-voice.md for setup.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import hmac
import logging
import re
import ssl
import time
import tomllib
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from urllib.parse import urlsplit

import aiohttp
import certifi
from aiohttp import web
from multidict import CIMultiDict
from pydantic import BaseModel, Field, SecretStr, ValidationError
from yarl import URL

LOG = logging.getLogger("codex_voice_direct")
BASE_PATH = "/backend-api/codex"
CALL_PATH = f"{BASE_PATH}/realtime/calls"
CALL_ID = re.compile(r"(?:rtc_[A-Za-z0-9._~-]{1,252}|[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12})\Z")
MAX_BODY = 2 * 1024 * 1024
MAX_MESSAGE = 16 * 1024 * 1024
MAX_CALLS = 32
CALL_TTL = 3600
CLOSE_TIMEOUT = 3.0
REQUEST_HEADERS = frozenset(
    {
        "accept",
        "content-type",
        "content-encoding",
        "user-agent",
        "originator",
        "version",
        "session_id",
        "session-id",
        "conversation_id",
        "thread-id",
        "openai-alpha",
        "openai-beta",
        "openai-fedramp",
        "openai-residency",
        "x-request-id",
        "x-client-request-id",
        "x-oai-attestation",
        "x-openai-federation",
        "x-openai-federation-id",
        "x-openai-residency",
        "x-openai-fedramp",
    }
)
RESPONSE_HEADERS = frozenset({"content-type", "content-encoding", "location", "retry-after", "x-request-id"})


class VoiceError(Exception):
    """Only fixed, credential-free categories may cross the HTTP/log boundary."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message


class LoginTokens(BaseModel):
    access_token: SecretStr
    account_id: str


class LoginFile(BaseModel):
    auth_mode: Literal["chatgpt"]
    tokens: LoginTokens


class AccountClaim(BaseModel):
    chatgpt_account_id: str


class ProfileClaim(BaseModel):
    email: str


class AccessClaims(BaseModel):
    exp: int
    account: AccountClaim = Field(alias="https://api.openai.com/auth")
    profile: ProfileClaim = Field(alias="https://api.openai.com/profile")


class ProviderConfig(BaseModel):
    experimental_bearer_token: SecretStr | None = None


class CodexConfig(BaseModel):
    model_provider: str
    model_providers: dict[str, ProviderConfig]


@dataclass(frozen=True)
class Settings:
    codex_home: Path
    expected_email: str
    expected_account_id: str
    call_url: str = "https://chatgpt.com/backend-api/codex/realtime/calls"
    sideband_base: str = "wss://api.openai.com/v1/live"


@dataclass(frozen=True)
class Credentials:
    token: str = field(repr=False)
    account_id: str = field(repr=False)


def read_credentials(settings: Settings) -> Credentials:
    try:
        login = LoginFile.model_validate_json((settings.codex_home / "auth.json").read_bytes())
        token = login.tokens.access_token.get_secret_value()
        payload = token.split(".")[1]
        claims = AccessClaims.model_validate_json(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (OSError, ValueError, IndexError, ValidationError):
        raise VoiceError(503, "voice_login_unavailable", "Sign in to the selected ChatGPT account in Codex.") from None
    if (
        claims.profile.email.casefold() != settings.expected_email.casefold()
        or claims.account.chatgpt_account_id != settings.expected_account_id
        or login.tokens.account_id != settings.expected_account_id
    ):
        raise VoiceError(503, "voice_identity_changed", "Restore the selected ChatGPT login before starting voice.")
    if claims.exp <= time.time() + 30:
        raise VoiceError(
            503, "voice_login_expired", "Refresh the selected ChatGPT login in Codex, then start a new call."
        )
    return Credentials(token, login.tokens.account_id)


def read_local_key(settings: Settings) -> str:
    try:
        config = CodexConfig.model_validate(tomllib.loads((settings.codex_home / "config.toml").read_text()))
        secret = config.model_providers[config.model_provider].experimental_bearer_token
        if secret is None:
            raise ValueError
        key = secret.get_secret_value()
        if not key or not key.isascii() or any(char.isspace() for char in key):
            raise ValueError
        return key
    except (OSError, ValueError, KeyError, ValidationError):
        raise VoiceError(
            503, "voice_provider_key_unavailable", "Restore the selected provider's configured bearer."
        ) from None


def authenticate(request: web.Request, settings: Settings) -> str:
    if "Origin" in request.headers:
        raise VoiceError(403, "voice_browser_origin_denied", "Voice requires the native Codex client.")
    expected = f"Bearer {read_local_key(settings)}".encode()
    supplied = request.headers.getall("Authorization", [])
    if len(supplied) != 1 or not hmac.compare_digest(supplied[0].encode(), expected):
        raise VoiceError(401, "voice_invalid_key", "A valid local provider bearer is required.")
    return hashlib.sha256(expected).hexdigest()


def upstream_headers(request: web.Request, credentials: Credentials) -> CIMultiDict[str]:
    connection_headers = {name.strip().lower() for name in request.headers.get("Connection", "").split(",")}
    result: CIMultiDict[str] = CIMultiDict()
    for name, value in request.headers.items():
        lower = name.lower()
        if lower in connection_headers:
            continue
        if lower in REQUEST_HEADERS or lower.startswith(("x-codex-", "x-openai-")):
            if lower in {"x-codex-api-key", "x-openai-api-key", "x-codex-account-id"}:
                continue
            if lower == "openai-beta":
                value = ", ".join(
                    part.strip()
                    for part in value.split(",")
                    if part.strip().lower() != "responses=experimental"
                    and not part.strip().lower().startswith("responses_websockets")
                )
                if not value:
                    continue
            result.add(name, value)
    result["Authorization"] = f"Bearer {credentials.token}"
    result["ChatGPT-Account-ID"] = credentials.account_id
    return result


def normalize_call_id(value: str) -> str:
    if CALL_ID.fullmatch(value) is None:
        raise VoiceError(400, "voice_invalid_call_id", "Unsupported voice call identifier.")
    return value if value.startswith("rtc_") else value.lower()


def call_id_from_location(location: str) -> str:
    try:
        parsed = urlsplit(location)
        if parsed.scheme or parsed.netloc:
            if (
                parsed.scheme != "https"
                or parsed.hostname not in {"api.openai.com", "chatgpt.com"}
                or parsed.port not in {None, 443}
                or parsed.username is not None
                or parsed.password is not None
            ):
                raise ValueError
        prefix = "/v1/realtime/calls/"
        if not parsed.path.startswith(prefix):
            raise ValueError
        return normalize_call_id(parsed.path[len(prefix) :])
    except (ValueError, VoiceError):
        raise VoiceError(502, "voice_invalid_location", "OpenAI returned an unsupported voice call Location.") from None


@dataclass
class Binding:
    key_digest: str
    account_id: str
    expires: float
    active: bool = False


@dataclass(frozen=True)
class RelayEnd:
    direction: str
    category: str
    code: int = 1011
    reason: bytes = field(default=b"", repr=False)


def close_code(code: int | None) -> int:
    if code in {1000, 1001, 1002, 1003, 1007, 1008, 1009, 1010, 1011, 1012, 1013, 1014}:
        return code
    if code is not None and 3000 <= code <= 4999:
        return code
    return 1011


type Socket = web.WebSocketResponse | aiohttp.ClientWebSocketResponse


async def pipe(source: Socket, target: Socket, direction: str) -> RelayEnd:
    while True:
        message = await source.receive()
        if message.type == aiohttp.WSMsgType.TEXT:
            await target.send_str(message.data)
        elif message.type == aiohttp.WSMsgType.BINARY:
            await target.send_bytes(message.data)
        elif message.type == aiohttp.WSMsgType.CLOSE:
            reason = (message.extra or "").encode("utf-8")[:123].decode("utf-8", errors="ignore").encode()
            return RelayEnd(direction, "peer_close", close_code(message.data), reason)
        elif message.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSING}:
            return RelayEnd(direction, "transport_closed", close_code(source.close_code))


async def close_sockets(sockets: tuple[Socket, ...], end: RelayEnd) -> None:
    try:
        async with asyncio.timeout(CLOSE_TIMEOUT):
            await asyncio.gather(*(socket.close(code=end.code, message=end.reason) for socket in sockets))
    except (TimeoutError, aiohttp.ClientError, OSError):
        LOG.warning("voice_close category=cleanup_timeout_or_transport")


async def relay(downstream: web.WebSocketResponse, upstream: aiohttp.ClientWebSocketResponse) -> None:
    started = time.monotonic()
    end = RelayEnd("adapter", "cancelled")
    tasks = {
        asyncio.create_task(pipe(downstream, upstream, "client"), name="voice-client-relay"),
        asyncio.create_task(pipe(upstream, downstream, "upstream"), name="voice-upstream-relay"),
    }
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            end = task.result()
    except (aiohttp.ClientError, OSError, RuntimeError):
        end = RelayEnd("adapter", "transport_error")
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await close_sockets((downstream, upstream), end)
        LOG.info(
            "voice_sideband_end direction=%s category=%s code=%d seconds=%.3f",
            end.direction,
            end.category,
            end.code,
            time.monotonic() - started,
        )


async def reject_redirect(
    session: aiohttp.ClientSession, context: SimpleNamespace, params: aiohttp.TraceRequestRedirectParams
) -> None:
    raise VoiceError(
        502, "voice_upstream_redirect", "OpenAI redirected the voice connection; no redirect was followed."
    )


class VoiceAdapter:
    def __init__(self, settings: Settings, session: aiohttp.ClientSession) -> None:
        self.settings = settings
        self.session = session
        self.bindings: dict[str, Binding] = {}
        self.creating = 0
        self.sockets: set[Socket] = set()

    def prune(self) -> None:
        now = time.monotonic()
        self.bindings = {
            key: binding for key, binding in self.bindings.items() if binding.active or binding.expires > now
        }

    async def health(self, request: web.Request) -> web.Response:
        read_local_key(self.settings)
        read_credentials(self.settings)
        return web.json_response({"status": "ready", "active_calls": sum(b.active for b in self.bindings.values())})

    async def create_call(self, request: web.Request) -> web.Response:
        key_digest = authenticate(request, self.settings)
        credentials = read_credentials(self.settings)
        if "call_id" in request.query:
            raise VoiceError(400, "voice_invalid_call_id", "A new call cannot supply a call identifier.")
        self.prune()
        if len(self.bindings) + self.creating >= MAX_CALLS:
            raise VoiceError(503, "voice_capacity", "Too many local voice calls; retry after existing calls expire.")
        self.creating += 1
        started = time.monotonic()
        try:
            body = await request.read()
            url = URL(
                self.settings.call_url + ("?" + request.rel_url.raw_query_string if request.query_string else ""),
                encoded=True,
            )
            async with self.session.post(
                url, data=body, headers=upstream_headers(request, credentials), allow_redirects=False
            ) as response:
                if not 200 <= response.status < 300:
                    status = response.status if 400 <= response.status < 600 else 502
                    raise VoiceError(status, "voice_call_upstream_denied", "OpenAI did not accept voice call creation.")
                location = response.headers.get("Location", "")
                call_id = call_id_from_location(location)
                output = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    output.extend(chunk)
                    if len(output) > MAX_BODY:
                        raise VoiceError(
                            502, "voice_upstream_body_limit", "OpenAI returned an oversized call response."
                        )
                digest = hashlib.sha256(call_id.encode()).hexdigest()
                if digest in self.bindings:
                    raise VoiceError(502, "voice_duplicate_call", "OpenAI returned an already bound call identifier.")
                self.bindings[digest] = Binding(key_digest, credentials.account_id, time.monotonic() + CALL_TTL)
                headers = {key: value for key, value in response.headers.items() if key.lower() in RESPONSE_HEADERS}
                LOG.info("voice_call_created status=%d seconds=%.3f", response.status, time.monotonic() - started)
                return web.Response(status=response.status, body=bytes(output), headers=headers)
        finally:
            self.creating -= 1

    async def attach(self, request: web.Request) -> web.WebSocketResponse:
        key_digest = authenticate(request, self.settings)
        credentials = read_credentials(self.settings)
        call_id = normalize_call_id(request.match_info["call_id"])
        if "call_id" in request.query:
            raise VoiceError(400, "voice_invalid_call_id", "The voice sideband must not repeat call_id in its query.")
        self.prune()
        binding = self.bindings.get(hashlib.sha256(call_id.encode()).hexdigest())
        if (
            binding is None
            or binding.expires <= time.monotonic()
            or binding.key_digest != key_digest
            or binding.account_id != credentials.account_id
        ):
            raise VoiceError(404, "voice_call_not_bound", "Start a new voice call through this adapter.")
        if binding.active:
            raise VoiceError(409, "voice_call_attached", "This voice call already has a control connection.")
        downstream = web.WebSocketResponse(
            autoclose=False, compress=False, timeout=CLOSE_TIMEOUT, max_msg_size=MAX_MESSAGE
        )
        if not downstream.can_prepare(request).ok:
            raise VoiceError(400, "voice_upgrade_required", "A WebSocket upgrade is required.")
        protocols = tuple(
            part.strip()
            for value in request.headers.getall("Sec-WebSocket-Protocol", [])
            for part in value.split(",")
            if part.strip()
        )
        url = URL(
            f"{self.settings.sideband_base}/{call_id}"
            + ("?" + request.rel_url.raw_query_string if request.query_string else ""),
            encoded=True,
        )
        binding.active = True
        upstream = None
        try:
            upstream = await self.session.ws_connect(
                url,
                headers=upstream_headers(request, credentials),
                protocols=protocols,
                autoclose=False,
                compress=0,
                max_msg_size=MAX_MESSAGE,
                # aiohttp uses attrs-generated parameters that ty cannot yet resolve.
                timeout=aiohttp.ClientWSTimeout(ws_close=CLOSE_TIMEOUT, ws_receive=None),  # ty: ignore[unknown-argument]
            )
            # aiohttp silently ignores an unoffered selection; reject the raw header too.
            selections = upstream._response.headers.getall("Sec-WebSocket-Protocol", [])
            if len(selections) > 1 or (selections and selections[0] not in protocols):
                raise VoiceError(502, "voice_invalid_protocol", "OpenAI selected an unoffered voice subprotocol.")
            downstream = web.WebSocketResponse(
                protocols=(upstream.protocol,) if upstream.protocol else (),
                autoclose=False,
                compress=False,
                timeout=CLOSE_TIMEOUT,
                max_msg_size=MAX_MESSAGE,
            )
            self.sockets.update((downstream, upstream))
            await downstream.prepare(request)
            LOG.info("voice_sideband_attached")
            await relay(downstream, upstream)
            return downstream
        except aiohttp.WSServerHandshakeError as error:
            status = error.status if 400 <= error.status < 600 else 502
            raise VoiceError(
                status, "voice_sideband_upstream_denied", "OpenAI did not accept the voice sideband."
            ) from None
        finally:
            binding.active = False
            self.sockets.discard(downstream)
            if upstream is not None:
                self.sockets.discard(upstream)
                if not upstream.closed:
                    await close_sockets((upstream,), RelayEnd("adapter", "attach_cleanup"))


@web.middleware
async def safe_errors(
    request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]
) -> web.StreamResponse:
    try:
        return await handler(request)
    except VoiceError as error:
        failure = error
    except web.HTTPException as error:
        failure = VoiceError(error.status, "voice_request_rejected", "Unsupported voice request.")
    except TimeoutError:
        failure = VoiceError(504, "voice_upstream_timeout", "OpenAI voice connection setup timed out.")
    except (aiohttp.ClientError, OSError):
        failure = VoiceError(502, "voice_upstream_transport", "OpenAI voice connection failed.")
    except Exception:
        failure = VoiceError(500, "voice_internal_error", "The local voice adapter failed.")
    LOG.warning("voice_request_failed category=%s status=%d", failure.code, failure.status)
    return web.json_response({"error": {"code": failure.code, "message": failure.message}}, status=failure.status)


ADAPTER_KEY = web.AppKey("voice_adapter", VoiceAdapter)


def create_app(settings: Settings) -> web.Application:
    app = web.Application(
        middlewares=[safe_errors],
        client_max_size=MAX_BODY,
        handler_args={"auto_decompress": False, "handler_cancellation": True, "access_log": None},
    )

    async def lifecycle(app: web.Application) -> AsyncIterator[None]:
        trace = aiohttp.TraceConfig()
        trace.on_request_redirect.append(reject_redirect)
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=certifi.where()), limit=MAX_CALLS + 4)
        async with aiohttp.ClientSession(
            connector=connector,
            cookie_jar=aiohttp.DummyCookieJar(),
            trust_env=False,
            auto_decompress=False,
            timeout=aiohttp.ClientTimeout(total=60, connect=15, sock_read=45),
            trace_configs=[trace],
        ) as session:
            app[ADAPTER_KEY] = VoiceAdapter(settings, session)
            yield

    async def shutdown(app: web.Application) -> None:
        await close_sockets(tuple(app[ADAPTER_KEY].sockets), RelayEnd("adapter", "shutdown", 1001))

    async def health(request: web.Request) -> web.Response:
        return await request.app[ADAPTER_KEY].health(request)

    async def create_call(request: web.Request) -> web.Response:
        return await request.app[ADAPTER_KEY].create_call(request)

    async def attach(request: web.Request) -> web.WebSocketResponse:
        return await request.app[ADAPTER_KEY].attach(request)

    app.cleanup_ctx.append(lifecycle)
    app.on_shutdown.append(shutdown)
    app.router.add_get("/health/ready", health)
    app.router.add_post(CALL_PATH, create_call)
    app.router.add_get(BASE_PATH + "/{call_id}", attach, allow_head=False)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--expected-email", required=True)
    parser.add_argument("--expected-account-id", required=True)
    parser.add_argument("--port", type=int, default=2456)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    for name in ("aiohttp.access", "aiohttp.server", "aiohttp.client", "aiohttp.internal", "aiohttp.websocket"):
        logging.getLogger(name).disabled = True
    settings = Settings(args.codex_home, args.expected_email, args.expected_account_id)
    try:
        read_local_key(settings)
        read_credentials(settings)
    except VoiceError as error:
        LOG.error("voice_start_failed category=%s", error.code)
        raise SystemExit(1) from None
    LOG.info("voice_adapter_start port=%d", args.port)
    web.run_app(
        create_app(settings),
        host="127.0.0.1",
        port=args.port,
        access_log=None,
        print=None,
        shutdown_timeout=CLOSE_TIMEOUT,
        handler_cancellation=True,
        auto_decompress=False,
    )


if __name__ == "__main__":
    main()
