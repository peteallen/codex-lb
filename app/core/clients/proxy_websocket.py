from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Mapping, NoReturn, Protocol, cast
from urllib.parse import urlparse, urlunparse

import aiohttp
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.client import connect as websocket_connect
from websockets.datastructures import Headers
from websockets.exceptions import (
    ConnectionClosedError,
    ConnectionClosedOK,
    InvalidHandshake,
    InvalidProxy,
    InvalidStatus,
)
from websockets.typing import Origin

from app.core.clients.codex import (
    CodexClient,
    CodexTransportError,
    codex_transport_error_message,
    create_codex_session,
    require_route_or_direct_egress_opt_in,
)
from app.core.clients.proxy import (
    _CHATGPT_ACCOUNT_ID_HEADER,
    _HOP_BY_HOP_HEADER_NAMES,
    CODEX_INSTALLATION_ID_HEADER,
    ProxyResponseError,
    _is_native_codex_request,
    _normalize_non_native_upstream_fingerprint,
    filter_inbound_headers,
)
from app.core.config.settings import get_settings
from app.core.conversation_archive import archive_bytes, archive_text
from app.core.errors import OpenAIErrorDetail, OpenAIErrorEnvelope, openai_error
from app.core.openai.models import OpenAIError
from app.core.openai.parsing import parse_error_payload
from app.core.resilience.network_recovery import (
    PROCESS_NETWORK_UNAVAILABLE_CODE,
    process_network_error_code,
    rotate_shared_http_transport,
)
from app.core.upstream_proxy import ResolvedUpstreamRoute
from app.core.utils.proxy_env import resolve_websocket_proxy_from_env
from app.core.utils.request_id import get_request_id

logger = logging.getLogger(__name__)

_WEBSOCKET_HOP_BY_HOP_HEADERS = _HOP_BY_HOP_HEADER_NAMES | frozenset(
    {
        "accept-encoding",
        "cookie",
        "sec-websocket-extensions",
        "sec-websocket-key",
        "sec-websocket-protocol",
        "sec-websocket-version",
    }
)
_RESPONSES_WEBSOCKET_BETA_HEADER = "responses_websockets=2026-02-06"
_RESPONSES_WEBSOCKET_INCOMPATIBLE_BETA_HEADERS = frozenset({"responses=experimental"})
_REALTIME_VOICE_FRAMELESS_BASE_URL = "https://api.openai.com/v1/live"
_REALTIME_VOICE_ALPHA_VALUES = frozenset({"quicksilver=v1", "quicksilver=v2"})
_REALTIME_VOICE_LOG_ERROR_CODES = frozenset(
    {
        "account_stream_concurrency_exceeded",
        "forbidden",
        "global_admission_timeout",
        "invalid_api_key",
        "invalid_request_error",
        "invalid_realtime_call_id",
        "invalid_upstream_response",
        "ip_forbidden",
        "rate_limit_exceeded",
        "realtime_call_account_scope_changed",
        "realtime_call_account_unavailable",
        "realtime_call_already_joined",
        "realtime_call_binding_unavailable",
        "realtime_call_forbidden",
        "realtime_call_id_conflict",
        "realtime_call_not_found",
        "upstream_error",
        "upstream_proxy_unavailable",
        "upstream_request_timeout",
        "upstream_unavailable",
    }
)
_REALTIME_VOICE_HEADER_ALLOWLIST = frozenset(
    {
        "chatgpt-conversation-id",
        "openai-alpha",
        "origin",
        "originator",
        "request-id",
        "session-id",
        "session_id",
        "thread-id",
        "user-agent",
        "x-chatgpt-conversation-id",
        "x-codex-conversation-id",
        "x-codex-session-id",
        "x-codex-turn-metadata",
        "x-openai-client-arch",
        "x-openai-client-id",
        "x-openai-client-os",
        "x-openai-client-user-agent",
        "x-openai-client-version",
        "x-openai-device-attestation",
        "x-openai-device-id",
        "x-openai-device-os",
        "x-openai-internal-codex-residency",
        "x-oai-attestation",
        "x-request-id",
        "x-session-id",
        "x-stainless-arch",
        "x-stainless-async",
        "x-stainless-lang",
        "x-stainless-os",
        "x-stainless-package-version",
        "x-stainless-retry-count",
        "x-stainless-runtime",
        "x-stainless-runtime-version",
        "x-stainless-timeout",
        "x-thread-id",
    }
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UpstreamWebSocketMessage:
    kind: str
    text: str | None = None
    data: bytes | None = None
    close_code: int | None = None
    close_reason: str | None = None
    error: str | None = None
    error_code: str | None = None


class UpstreamWebSocketTransportError(RuntimeError):
    """Credential-safe post-connect transport failure with stable classification."""

    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


def _websocket_transport_error_code(exc: BaseException, *, uses_proxy: bool) -> str:
    return process_network_error_code(
        exc,
        fallback="upstream_unavailable",
        include_permanent_dns=not uses_proxy,
    )


def _relay_receive_error_code(error_code: str) -> str | None:
    """Expose only account-neutral process failures across the adapter boundary."""

    # Relay owners map an absent code to their established stream_incomplete
    # contract. Leaking the adapter's generic fallback would bypass that path.
    return error_code if error_code == PROCESS_NETWORK_UNAVAILABLE_CODE else None


async def _rotate_after_websocket_network_failure(error_code: str) -> None:
    if error_code != PROCESS_NETWORK_UNAVAILABLE_CODE:
        return
    try:
        await rotate_shared_http_transport(transport="websocket", request_id=get_request_id())
    except Exception:
        # Rotation is best-effort here: never replace the credential-safe
        # socket failure that the owning request must surface.
        logger.warning("Failed to rotate shared HTTP state after websocket network failure", exc_info=True)


async def _raise_websocket_send_error(
    exc: Exception,
    *,
    endpoint_id: str | None = None,
    uses_proxy: bool,
) -> NoReturn:
    error_code = _websocket_transport_error_code(exc, uses_proxy=uses_proxy)
    await _rotate_after_websocket_network_failure(error_code)
    # A send exception does not prove whether the peer received the complete
    # frame. The typed error lets every caller fail closed instead of replaying.
    raise UpstreamWebSocketTransportError(
        codex_transport_error_message("websocket send", endpoint_id, exc),
        error_code=error_code,
    ) from None


@dataclass(frozen=True, slots=True)
class RealtimeVoiceHeaderDiagnostics:
    """Metadata-only Voice handshake shape; never contains header values."""

    attestation_present: bool
    attestation_envelope_valid: bool
    attestation_version: int | None
    attestation_status: int | None
    attestation_token_present: bool
    alpha_present: bool
    alpha_valid: bool
    session_header_present: bool
    thread_header_present: bool
    originator_header_present: bool
    user_agent_header_present: bool


class UpstreamResponsesWebSocket(Protocol):
    async def send_text(self, text: str) -> None: ...

    async def send_bytes(self, data: bytes) -> None: ...

    async def receive(self) -> UpstreamWebSocketMessage: ...

    async def close(self, *, code: int = 1000, reason: str = "") -> None: ...

    def response_header(self, name: str) -> str | None: ...


class WebsocketsResponsesWebSocket:
    def __init__(self, connection: ClientConnection, *, uses_proxy: bool = False) -> None:
        self._connection = connection
        self._uses_proxy = uses_proxy

    async def send_text(self, text: str) -> None:
        try:
            await self._connection.send(text)
        except Exception as exc:
            await _raise_websocket_send_error(exc, uses_proxy=self._uses_proxy)

    async def send_bytes(self, data: bytes) -> None:
        try:
            await self._connection.send(data)
        except Exception as exc:
            await _raise_websocket_send_error(exc, uses_proxy=self._uses_proxy)

    async def receive(self) -> UpstreamWebSocketMessage:
        try:
            message = await self._connection.recv()
        except ConnectionClosedOK as exc:
            return UpstreamWebSocketMessage(
                kind="close",
                close_code=_close_code_from_exception(exc),
                close_reason=_close_reason_from_exception(exc),
            )
        except ConnectionClosedError as exc:
            error_code = _websocket_transport_error_code(exc, uses_proxy=self._uses_proxy)
            await _rotate_after_websocket_network_failure(error_code)
            # ConnectionClosedError describes an incomplete close handshake,
            # not generic transport provenance. Let relay owners map ordinary
            # closes to stream_incomplete while preserving classified network failures.
            return UpstreamWebSocketMessage(
                kind="error",
                close_code=_close_code_from_exception(exc),
                close_reason=_close_reason_from_exception(exc),
                error=str(exc),
                error_code=_relay_receive_error_code(error_code),
            )
        except Exception as exc:
            error_code = _websocket_transport_error_code(exc, uses_proxy=self._uses_proxy)
            await _rotate_after_websocket_network_failure(error_code)
            return UpstreamWebSocketMessage(
                kind="error",
                error=codex_transport_error_message("websocket receive", None, exc),
                error_code=_relay_receive_error_code(error_code),
            )

        if isinstance(message, str):
            return UpstreamWebSocketMessage(kind="text", text=message)
        if isinstance(message, bytes):
            return UpstreamWebSocketMessage(kind="binary", data=message)
        return UpstreamWebSocketMessage(kind="error", error=f"Unexpected websocket message type: {type(message)!r}")

    async def close(self, *, code: int = 1000, reason: str = "") -> None:
        await self._connection.close(code=code, reason=reason)

    def response_header(self, name: str) -> str | None:
        response = getattr(self._connection, "response", None)
        headers = getattr(response, "headers", None)
        if headers is None:
            return None
        value = headers.get(name)
        if value is None:
            return None
        return str(value)


class CodexResponsesWebSocket:
    def __init__(
        self,
        websocket: Any,
        *,
        context: Any | None = None,
        codex_client: CodexClient | None = None,
        owns_codex_client: bool = False,
        endpoint_id: str | None = None,
        response_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._websocket = websocket
        self._context = context
        self._codex_client = codex_client
        self._owns_codex_client = owns_codex_client
        self._endpoint_id = endpoint_id
        self._response_headers = _normalize_response_headers(response_headers)

    async def send_text(self, text: str) -> None:
        try:
            result = self._websocket.send_str(text)
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            await _raise_websocket_send_error(exc, endpoint_id=self._endpoint_id, uses_proxy=True)

    async def send_bytes(self, data: bytes) -> None:
        try:
            result = self._websocket.send_bytes(data)
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            await _raise_websocket_send_error(exc, endpoint_id=self._endpoint_id, uses_proxy=True)

    async def receive(self) -> UpstreamWebSocketMessage:
        try:
            msg = await self._websocket.receive()
        except Exception as exc:
            error_code = _websocket_transport_error_code(exc, uses_proxy=True)
            await _rotate_after_websocket_network_failure(error_code)
            return UpstreamWebSocketMessage(
                kind="error",
                error=codex_transport_error_message("websocket receive", self._endpoint_id, exc),
                error_code=_relay_receive_error_code(error_code),
            )
        if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
            return UpstreamWebSocketMessage(
                kind="close",
                close_code=_aiohttp_ws_close_code(self._websocket, msg),
                close_reason=_aiohttp_ws_close_reason(msg),
            )
        if msg.type == aiohttp.WSMsgType.ERROR:
            exception = msg.data if isinstance(msg.data, BaseException) else None
            error_code = (
                _websocket_transport_error_code(exception, uses_proxy=True)
                if exception is not None
                else "upstream_unavailable"
            )
            await _rotate_after_websocket_network_failure(error_code)
            return UpstreamWebSocketMessage(
                kind="error",
                error=(
                    codex_transport_error_message("websocket receive", self._endpoint_id, exception)
                    if exception is not None
                    else "Upstream websocket error"
                ),
                error_code=_relay_receive_error_code(error_code),
            )
        if msg.type == aiohttp.WSMsgType.TEXT:
            text = msg.data if isinstance(msg.data, str) else str(msg.data)
            return UpstreamWebSocketMessage(kind="text", text=text)
        if msg.type == aiohttp.WSMsgType.BINARY:
            return UpstreamWebSocketMessage(kind="binary", data=bytes(msg.data) if isinstance(msg.data, bytes) else b"")
        return UpstreamWebSocketMessage(kind="error", error=f"Unexpected ws type: {msg.type!r}")

    async def close(self, *, code: int = 1000, reason: str = "") -> None:
        try:
            if code == 1000 and not reason:
                result = self._websocket.close()
            else:
                result = self._websocket.close(code=code, message=reason.encode("utf-8"))
            if asyncio.iscoroutine(result):
                await result
        finally:
            try:
                if self._context is not None:
                    await self._context.__aexit__(None, None, None)
            finally:
                # Context and client ownership are independent: a failed
                # websocket exit must not leak the session this wrapper owns.
                if self._owns_codex_client and self._codex_client is not None:
                    await self._codex_client.close()

    def response_header(self, name: str) -> str | None:
        return self._response_headers.get(name.lower())


class ArchivingResponsesWebSocket:
    def __init__(
        self,
        wrapped: UpstreamResponsesWebSocket,
        *,
        url: str,
        headers: dict[str, str],
        account_id: str | None,
        route: ResolvedUpstreamRoute | None = None,
        fallback_used: bool | None = None,
        direct_egress: bool = False,
    ) -> None:
        self._wrapped = wrapped
        self._url = url
        self._headers = headers
        self._account_id = account_id
        self.upstream_proxy_route_mode = route.mode if route is not None else ("direct" if direct_egress else None)
        self.upstream_proxy_pool_id = route.pool_id if route is not None else None
        self.upstream_proxy_endpoint_id = route.endpoint_id if route is not None else None
        self.upstream_proxy_fallback_used = fallback_used if route is not None else None

    async def send_text(self, text: str) -> None:
        archive_text(
            direction="codex_to_server",
            kind="responses",
            transport="websocket",
            text=text,
            account_id=self._account_id,
            method="GET",
            url=self._url,
            headers=self._headers,
            extra={"frame_type": "text"},
        )
        await self._wrapped.send_text(text)

    async def send_bytes(self, data: bytes) -> None:
        archive_bytes(
            direction="codex_to_server",
            kind="responses",
            transport="websocket",
            data=data,
            account_id=self._account_id,
            method="GET",
            url=self._url,
            headers=self._headers,
            extra={"frame_type": "binary"},
        )
        await self._wrapped.send_bytes(data)

    async def receive(self) -> UpstreamWebSocketMessage:
        message = await self._wrapped.receive()
        return message

    def archive_received(self, message: UpstreamWebSocketMessage) -> None:
        if message.kind == "text" and message.text is not None:
            archive_text(
                direction="server_to_codex",
                kind="responses",
                transport="websocket",
                text=message.text,
                account_id=self._account_id,
                method="GET",
                url=self._url,
                headers=self._headers,
                extra={"frame_type": "text"},
            )
        elif message.kind == "binary" and message.data is not None:
            archive_bytes(
                direction="server_to_codex",
                kind="responses",
                transport="websocket",
                data=message.data,
                account_id=self._account_id,
                method="GET",
                url=self._url,
                headers=self._headers,
                extra={"frame_type": "binary"},
            )
        else:
            archive_text(
                direction="server_to_codex",
                kind="responses",
                transport="websocket",
                text=message.error or "",
                account_id=self._account_id,
                method="GET",
                url=self._url,
                headers=self._headers,
                extra={"frame_type": message.kind, "close_code": message.close_code},
            )

    async def close(self, *, code: int = 1000, reason: str = "") -> None:
        if code == 1000 and not reason:
            await self._wrapped.close()
        else:
            await self._wrapped.close(code=code, reason=reason)

    def response_header(self, name: str) -> str | None:
        return self._wrapped.response_header(name)


def _connection_header_tokens(headers: Mapping[str, str]) -> set[str]:
    tokens: set[str] = set()
    for key, value in headers.items():
        if key.lower() != "connection":
            continue
        tokens.update(token.strip().lower() for token in value.split(",") if token.strip())
    return tokens


def filter_inbound_websocket_headers(headers: Mapping[str, str]) -> dict[str, str]:
    filtered = filter_inbound_headers(headers)
    blocked_header_names = _WEBSOCKET_HOP_BY_HOP_HEADERS | _connection_header_tokens(filtered)
    return {key: value for key, value in filtered.items() if key.lower() not in blocked_header_names}


def _build_upstream_websocket_headers(
    inbound: dict[str, str],
    access_token: str,
    account_id: str | None,
) -> dict[str, str]:
    headers = filter_inbound_websocket_headers(inbound)
    # ``filter_inbound_websocket_headers`` strips ``x-codex-installation-id`` because it
    # lives in ``IGNORE_INBOUND_HEADERS``. Callers normalize the selected account's
    # canonical installation id onto the inbound headers before connecting (mirroring the
    # HTTP ``/codex/responses`` egress, where ``apply_codex_installation_headers`` runs as
    # the final post-filter step). Re-add it here so the websocket handshake keeps header
    # parity instead of losing the standalone installation header to this second filter.
    installation_id = next(
        (value for key, value in inbound.items() if key.lower() == CODEX_INSTALLATION_ID_HEADER),
        None,
    )
    if installation_id:
        headers[CODEX_INSTALLATION_ID_HEADER] = installation_id
    native = _is_native_codex_request(headers)
    lower_keys = {key.lower() for key in headers}
    if "x-request-id" not in lower_keys and "request-id" not in lower_keys:
        request_id = get_request_id()
        if request_id:
            headers["x-request-id"] = request_id
    # Normalize a non-native client's fingerprint on the client-facing
    # ``/v1/responses`` websocket egress too. This builder is the upstream egress
    # for a direct websocket caller, so without normalization an OpenAI SDK that
    # speaks the responses websocket protocol would reach upstream with its
    # ``OpenAI/Python`` / ``x-openai-client-*`` / ``x-stainless-*`` fingerprint
    # intact and trigger the priority downgrade this change exists to prevent.
    if not native:
        _normalize_non_native_upstream_fingerprint(headers)
    headers["Authorization"] = f"Bearer {access_token}"
    if account_id:
        if native:
            headers["chatgpt-account-id"] = account_id
        else:
            headers[_CHATGPT_ACCOUNT_ID_HEADER] = account_id
    _ensure_responses_websocket_beta_header(headers)
    return headers


def build_realtime_voice_websocket_headers(
    inbound: Mapping[str, str],
    access_token: str,
    account_id: str | None,
) -> dict[str, str]:
    """Build the raw Voice sideband handshake without Responses mutations."""

    allowlisted = {key: value for key, value in inbound.items() if key.lower() in _REALTIME_VOICE_HEADER_ALLOWLIST}
    headers = filter_inbound_websocket_headers(allowlisted)
    for key in tuple(headers):
        if key.lower() == "openai-alpha" and headers[key].strip().lower() not in _REALTIME_VOICE_ALPHA_VALUES:
            headers.pop(key)
    headers["Authorization"] = f"Bearer {access_token}"
    if account_id:
        headers["chatgpt-account-id"] = account_id
    return headers


def realtime_voice_header_diagnostics(headers: Mapping[str, str]) -> RealtimeVoiceHeaderDiagnostics:
    """Return only nonsecret presence and attestation-envelope metadata."""

    normalized = {key.lower(): value for key, value in headers.items()}
    attestation = normalized.get("x-oai-attestation")
    envelope_valid = False
    attestation_version: int | None = None
    attestation_status: int | None = None
    attestation_token_present = False
    # Released Codex app-server envelopes the opaque token as compact JSON
    # ``{"v": 1, "s": <status>, "t": <opaque>}``. Parse only bounded input
    # and expose only the nonsecret integer version/status fields. Never retain
    # or log the token, its value, or its length.
    if attestation is not None and len(attestation) <= 16_384:
        try:
            envelope = json.loads(attestation)
        except (ValueError, RecursionError, UnicodeError):
            envelope = None
        if isinstance(envelope, dict) and set(envelope).issubset({"v", "s", "t"}):
            version = envelope.get("v")
            status = envelope.get("s")
            token = envelope.get("t")
            if (
                isinstance(version, int)
                and not isinstance(version, bool)
                and 0 <= version <= 255
                and isinstance(status, int)
                and not isinstance(status, bool)
                and 0 <= status <= 255
                and ("t" not in envelope or isinstance(token, str))
            ):
                envelope_valid = True
                attestation_version = version
                attestation_status = status
                attestation_token_present = isinstance(token, str) and bool(token)

    alpha = normalized.get("openai-alpha")
    return RealtimeVoiceHeaderDiagnostics(
        attestation_present=attestation is not None,
        attestation_envelope_valid=envelope_valid,
        attestation_version=attestation_version,
        attestation_status=attestation_status,
        attestation_token_present=attestation_token_present,
        alpha_present=alpha is not None,
        alpha_valid=alpha is not None and alpha.strip().lower() in _REALTIME_VOICE_ALPHA_VALUES,
        session_header_present=any(
            name in normalized for name in ("session-id", "session_id", "x-session-id", "x-codex-session-id")
        ),
        thread_header_present=any(name in normalized for name in ("thread-id", "x-thread-id")),
        originator_header_present="originator" in normalized,
        user_agent_header_present="user-agent" in normalized,
    )


def realtime_voice_safe_error_code(payload: Mapping[str, object]) -> str | None:
    """Extract an error code only when it is an explicitly safe log token."""

    error = payload.get("error")
    if not isinstance(error, Mapping):
        return None
    code = error.get("code")
    if not isinstance(code, str):
        return None
    return realtime_voice_safe_log_token(code)


def realtime_voice_safe_log_token(value: str | None) -> str | None:
    """Allow only static Voice error codes; collapse every unknown value."""

    if value is None:
        return None
    if value in _REALTIME_VOICE_LOG_ERROR_CODES:
        return value
    return "unclassified_upstream_error"


def _ensure_responses_websocket_beta_header(headers: dict[str, str]) -> None:
    header_key = next((key for key in headers if key.lower() == "openai-beta"), "openai-beta")
    current_value = headers.get(header_key, "")
    beta_tokens = [
        token.strip()
        for token in current_value.split(",")
        if token.strip() and token.strip().lower() not in _RESPONSES_WEBSOCKET_INCOMPATIBLE_BETA_HEADERS
    ]
    if _RESPONSES_WEBSOCKET_BETA_HEADER.lower() not in {token.lower() for token in beta_tokens}:
        beta_tokens.append(_RESPONSES_WEBSOCKET_BETA_HEADER)
    headers[header_key] = ", ".join(beta_tokens)


def _pop_header_case_insensitive(headers: dict[str, str], name: str) -> str | None:
    lowered = name.lower()
    for key in tuple(headers):
        if key.lower() != lowered:
            continue
        return headers.pop(key)
    return None


def _aiohttp_ws_close_code(websocket: Any, message: aiohttp.WSMessage) -> int | None:
    if isinstance(message.data, int):
        return message.data
    close_code = getattr(websocket, "close_code", None)
    return close_code if isinstance(close_code, int) else None


def _aiohttp_ws_close_reason(message: aiohttp.WSMessage) -> str | None:
    reason = getattr(message, "extra", None)
    return reason if isinstance(reason, str) and reason else None


def _responses_websocket_url(base_url: str) -> str:
    parsed = urlparse(f"{base_url.rstrip('/')}/codex/responses")
    if parsed.scheme == "https":
        scheme = "wss"
    elif parsed.scheme == "http":
        scheme = "ws"
    else:
        scheme = parsed.scheme
    return urlunparse(parsed._replace(scheme=scheme))


def realtime_voice_websocket_url(base_url: str, call_id: str, query: str = "") -> str:
    # Codex creates ChatGPT-authenticated V3 calls through the ChatGPT backend,
    # but Frameless Bidi sideband control deliberately joins the resulting
    # call on OpenAI's direct Live endpoint. Path-based joins are the Frameless
    # transport regardless of whether upstream issued an ``rtc_*`` or UUID
    # identifier. Reusing the ChatGPT call-create base reaches an unsupported
    # path that Cloudflare rejects before the Realtime application sees it.
    del base_url
    parsed = urlparse(f"{_REALTIME_VOICE_FRAMELESS_BASE_URL}/{call_id}")
    if parsed.scheme == "https":
        scheme = "wss"
    elif parsed.scheme == "http":
        scheme = "ws"
    else:
        scheme = parsed.scheme
    return urlunparse(parsed._replace(scheme=scheme, query=query))


async def connect_responses_websocket(
    headers: dict[str, str],
    access_token: str,
    account_id: str | None,
    *,
    base_url: str | None = None,
    route: ResolvedUpstreamRoute | None = None,
    codex_client: CodexClient | None = None,
    allow_direct_egress: bool = False,
) -> UpstreamResponsesWebSocket:
    settings = get_settings()
    upstream_base = (base_url or settings.upstream_base_url).rstrip("/")
    url = _responses_websocket_url(upstream_base)
    upstream_headers = _build_upstream_websocket_headers(headers, access_token, account_id)
    require_route_or_direct_egress_opt_in(
        route=route,
        allow_direct_egress=allow_direct_egress,
        operation="responses websocket",
    )
    if route is not None:
        owns_codex_client = codex_client is None
        active_codex_client = codex_client or CodexClient(create_codex_session())
        endpoint_id = route.endpoint_id
        active_route = route
        fallback_used = False
        try:
            opener = getattr(active_codex_client, "open_ws_with_route_metadata", None)
            if callable(opener):
                result = await opener(
                    url,
                    route=route,
                    headers=upstream_headers,
                    timeout=settings.upstream_connect_timeout_seconds,
                    max_msg_size=settings.max_sse_event_bytes,
                )
                context = result.context
                websocket = result.websocket
                endpoint_id = result.route.endpoint_id
                active_route = result.route
                fallback_used = result.fallback_used
            else:
                context = await active_codex_client.ws_connect(
                    url,
                    route=route,
                    headers=upstream_headers,
                    timeout=settings.upstream_connect_timeout_seconds,
                    max_msg_size=settings.max_sse_event_bytes,
                )
                websocket = await context.__aenter__() if hasattr(context, "__aenter__") else context
                if not hasattr(context, "__aenter__"):
                    context = None
                endpoint_id = route.endpoint_id
        except CodexTransportError as exc:
            if owns_codex_client:
                await active_codex_client.close()
            error_code = exc.error_code or "upstream_unavailable"
            raise ProxyResponseError(
                502,
                openai_error(error_code, str(exc), error_type="server_error"),
                failure_phase="connect",
                retryable_same_contract=error_code == PROCESS_NETWORK_UNAVAILABLE_CODE,
            ) from exc
        except Exception:
            if owns_codex_client:
                await active_codex_client.close()
            raise
        return ArchivingResponsesWebSocket(
            CodexResponsesWebSocket(
                websocket,
                context=context if hasattr(context, "__aenter__") else None,
                codex_client=active_codex_client,
                owns_codex_client=owns_codex_client,
                endpoint_id=endpoint_id,
                response_headers=_codex_websocket_response_headers(websocket, context),
            ),
            url=url,
            headers=upstream_headers,
            account_id=account_id,
            route=active_route,
            fallback_used=fallback_used,
        )
    origin = cast(Origin | None, _pop_header_case_insensitive(upstream_headers, "origin"))
    user_agent = _pop_header_case_insensitive(upstream_headers, "user-agent")
    proxy_env = (
        settings.upstream_websocket_proxy_env() if hasattr(settings, "upstream_websocket_proxy_env") else os.environ
    )
    proxy_url = resolve_websocket_proxy_from_env(url, proxy_env) if settings.upstream_websocket_trust_env else None
    connect_kwargs: dict[str, Any] = {
        "origin": origin,
        "additional_headers": upstream_headers or None,
        "user_agent_header": user_agent,
        "open_timeout": settings.upstream_connect_timeout_seconds,
        # Long Codex turns can spend minutes in upstream reasoning without
        # sending application frames. Keep transport pings enabled so
        # intermediaries still see liveness, but disable the library's pong
        # watchdog so codex-lb's own request/idle budgets decide when a
        # healthy long turn has stalled.
        "ping_timeout": None,
        "max_size": settings.max_sse_event_bytes,
    }
    connect_kwargs["proxy"] = proxy_url
    try:
        response = await websocket_connect(url, **connect_kwargs)
    except asyncio.TimeoutError as exc:
        raise ProxyResponseError(
            502,
            openai_error("upstream_unavailable", "Request to upstream timed out"),
        ) from exc
    except InvalidStatus as exc:
        response = exc.response
        message = response.reason_phrase or f"Upstream websocket error: HTTP {response.status_code}"
        raise ProxyResponseError(
            response.status_code,
            _handshake_error_payload(response.status_code, message, response.headers, response.body),
        ) from exc
    except InvalidHandshake as exc:
        message = str(exc) or "Invalid upstream websocket handshake"
        raise ProxyResponseError(
            502,
            openai_error("upstream_unavailable", message, error_type="server_error"),
        ) from exc
    except InvalidProxy as exc:
        message = str(exc) or "Invalid upstream websocket proxy configuration"
        raise ProxyResponseError(
            502,
            openai_error("upstream_unavailable", message, error_type="server_error"),
        ) from exc
    except OSError as exc:
        error_code = process_network_error_code(
            exc,
            fallback="upstream_unavailable",
            include_permanent_dns=proxy_url is None,
        )
        raise ProxyResponseError(
            502,
            openai_error(error_code, str(exc)),
            failure_phase="connect",
            retryable_same_contract=error_code == PROCESS_NETWORK_UNAVAILABLE_CODE,
        ) from exc

    return ArchivingResponsesWebSocket(
        WebsocketsResponsesWebSocket(response, uses_proxy=proxy_url is not None),
        url=url,
        headers=upstream_headers,
        account_id=account_id,
        direct_egress=allow_direct_egress,
    )


async def connect_realtime_voice_websocket(
    headers: Mapping[str, str],
    access_token: str,
    account_id: str | None,
    *,
    call_id: str,
    query: str = "",
    base_url: str | None = None,
    route: ResolvedUpstreamRoute | None = None,
    codex_client: CodexClient | None = None,
    allow_direct_egress: bool = False,
) -> UpstreamResponsesWebSocket:
    """Open a transparent Voice sideband websocket for an existing call."""

    settings = get_settings()
    upstream_base = (base_url or settings.upstream_base_url).rstrip("/")
    url = realtime_voice_websocket_url(upstream_base, call_id, query)
    upstream_headers = build_realtime_voice_websocket_headers(headers, access_token, account_id)
    header_diagnostics = realtime_voice_header_diagnostics(upstream_headers)
    route_mode = "configured_proxy" if route is not None else "direct"
    logger.info(
        "Realtime Voice upstream connect started route_mode=%s"
        " attestation_present=%s attestation_envelope_valid=%s"
        " attestation_version=%s attestation_status=%s attestation_token_present=%s"
        " alpha_present=%s alpha_valid=%s session_header_present=%s"
        " thread_header_present=%s originator_header_present=%s user_agent_header_present=%s",
        route_mode,
        header_diagnostics.attestation_present,
        header_diagnostics.attestation_envelope_valid,
        header_diagnostics.attestation_version,
        header_diagnostics.attestation_status,
        header_diagnostics.attestation_token_present,
        header_diagnostics.alpha_present,
        header_diagnostics.alpha_valid,
        header_diagnostics.session_header_present,
        header_diagnostics.thread_header_present,
        header_diagnostics.originator_header_present,
        header_diagnostics.user_agent_header_present,
    )
    require_route_or_direct_egress_opt_in(
        route=route,
        allow_direct_egress=allow_direct_egress,
        operation="realtime Voice sideband websocket",
    )
    if route is not None:
        owns_codex_client = codex_client is None
        active_codex_client = codex_client or CodexClient(create_codex_session())
        endpoint_id = route.endpoint_id
        try:
            opener = getattr(active_codex_client, "open_ws_with_route_metadata", None)
            if callable(opener):
                result = await opener(
                    url,
                    route=route,
                    headers=upstream_headers,
                    timeout=settings.upstream_connect_timeout_seconds,
                    max_msg_size=settings.max_sse_event_bytes,
                )
                context = result.context
                websocket = result.websocket
                endpoint_id = result.route.endpoint_id
            else:
                context = await active_codex_client.ws_connect(
                    url,
                    route=route,
                    headers=upstream_headers,
                    timeout=settings.upstream_connect_timeout_seconds,
                    max_msg_size=settings.max_sse_event_bytes,
                )
                websocket = await context.__aenter__() if hasattr(context, "__aenter__") else context
                if not hasattr(context, "__aenter__"):
                    context = None
        except asyncio.CancelledError:
            if owns_codex_client:
                await active_codex_client.close()
            raise
        except CodexTransportError as exc:
            if owns_codex_client:
                await active_codex_client.close()
            error = ProxyResponseError(
                502,
                openai_error("upstream_unavailable", str(exc), error_type="server_error"),
                failure_phase="upstream_handshake",
                failure_exception_type=type(exc).__name__,
                upstream_status_code=exc.status_code,
                upstream_error_code="upstream_unavailable",
            )
            _log_realtime_voice_connect_failure(error, route_mode=route_mode)
            raise error from exc
        except Exception as exc:
            if owns_codex_client:
                await active_codex_client.close()
            logger.warning(
                "Realtime Voice upstream connect failed route_mode=%s failure_phase=upstream_handshake"
                " upstream_status=None upstream_error_code=None exception_type=%s",
                route_mode,
                type(exc).__name__,
            )
            raise
        logger.info(
            "Realtime Voice upstream connect succeeded route_mode=%s upstream_status=101",
            route_mode,
        )
        return CodexResponsesWebSocket(
            websocket,
            context=context if hasattr(context, "__aenter__") else None,
            codex_client=active_codex_client,
            owns_codex_client=owns_codex_client,
            endpoint_id=endpoint_id,
            response_headers=_codex_websocket_response_headers(websocket, context),
        )

    origin = cast(Origin | None, _pop_header_case_insensitive(upstream_headers, "origin"))
    user_agent = _pop_header_case_insensitive(upstream_headers, "user-agent")
    proxy_env = (
        settings.upstream_websocket_proxy_env() if hasattr(settings, "upstream_websocket_proxy_env") else os.environ
    )
    proxy_url = resolve_websocket_proxy_from_env(url, proxy_env) if settings.upstream_websocket_trust_env else None
    connect_kwargs: dict[str, Any] = {
        "origin": origin,
        "additional_headers": upstream_headers or None,
        "user_agent_header": user_agent,
        "open_timeout": settings.upstream_connect_timeout_seconds,
        "ping_timeout": None,
        "max_size": settings.max_sse_event_bytes,
        # Match the released Codex realtime client. tokio-tungstenite doesn't
        # advertise permessage-deflate on this sideband handshake, while the
        # Python websockets client does unless compression is explicitly off.
        "compression": None,
        "proxy": proxy_url,
    }
    try:
        response = await websocket_connect(url, **connect_kwargs)
    except asyncio.TimeoutError as exc:
        error = ProxyResponseError(
            502,
            openai_error("upstream_unavailable", "Request to upstream timed out"),
            failure_phase="upstream_connect",
            failure_exception_type=type(exc).__name__,
            upstream_error_code="upstream_unavailable",
        )
        _log_realtime_voice_connect_failure(error, route_mode=route_mode)
        raise error from exc
    except InvalidStatus as exc:
        handshake_response = exc.response
        message = handshake_response.reason_phrase or (
            f"Upstream websocket error: HTTP {handshake_response.status_code}"
        )
        payload = _handshake_error_payload(
            handshake_response.status_code,
            message,
            handshake_response.headers,
            handshake_response.body,
        )
        error = ProxyResponseError(
            handshake_response.status_code,
            payload,
            failure_phase="upstream_handshake_status",
            failure_exception_type=type(exc).__name__,
            upstream_status_code=handshake_response.status_code,
            upstream_error_code=realtime_voice_safe_error_code(payload),
        )
        normalized_response_headers = _normalize_response_headers(handshake_response.headers)
        parsed_error = _try_parse_handshake_error_payload(
            handshake_response.headers,
            handshake_response.body,
        )
        logger.warning(
            "Realtime Voice upstream connect failed route_mode=%s failure_phase=%s"
            " upstream_status=%s upstream_error_code=%s response_json_content_type=%s"
            " response_openai_error_parsed=%s cloudflare_marker_present=%s"
            " server_header_present=%s exception_type=%s",
            route_mode,
            error.failure_phase,
            error.upstream_status_code,
            error.upstream_error_code,
            "json" in normalized_response_headers.get("content-type", "").lower(),
            parsed_error is not None,
            any(name in normalized_response_headers for name in ("cf-cache-status", "cf-mitigated", "cf-ray")),
            "server" in normalized_response_headers,
            error.failure_exception_type,
        )
        raise error from exc
    except InvalidHandshake as exc:
        message = str(exc) or "Invalid upstream websocket handshake"
        error = ProxyResponseError(
            502,
            openai_error("upstream_unavailable", message, error_type="server_error"),
            failure_phase="upstream_handshake",
            failure_exception_type=type(exc).__name__,
            upstream_error_code="upstream_unavailable",
        )
        _log_realtime_voice_connect_failure(error, route_mode=route_mode)
        raise error from exc
    except InvalidProxy as exc:
        message = str(exc) or "Invalid upstream websocket proxy configuration"
        error = ProxyResponseError(
            502,
            openai_error("upstream_unavailable", message, error_type="server_error"),
            failure_phase="upstream_proxy_connect",
            failure_exception_type=type(exc).__name__,
            upstream_error_code="upstream_unavailable",
        )
        _log_realtime_voice_connect_failure(error, route_mode=route_mode)
        raise error from exc
    except OSError as exc:
        error = ProxyResponseError(
            502,
            openai_error("upstream_unavailable", str(exc)),
            failure_phase="upstream_connect",
            failure_exception_type=type(exc).__name__,
            upstream_error_code="upstream_unavailable",
        )
        _log_realtime_voice_connect_failure(error, route_mode=route_mode)
        raise error from exc

    logger.info(
        "Realtime Voice upstream connect succeeded route_mode=%s upstream_status=101",
        route_mode,
    )
    return WebsocketsResponsesWebSocket(response)


def _log_realtime_voice_connect_failure(error: ProxyResponseError, *, route_mode: str) -> None:
    logger.warning(
        "Realtime Voice upstream connect failed route_mode=%s failure_phase=%s"
        " upstream_status=%s upstream_error_code=%s exception_type=%s",
        route_mode,
        error.failure_phase,
        error.upstream_status_code,
        error.upstream_error_code,
        error.failure_exception_type,
    )


def _close_code_from_exception(exc: ConnectionClosedOK | ConnectionClosedError) -> int | None:
    if exc.rcvd is not None:
        return int(exc.rcvd.code)
    if exc.sent is not None:
        return int(exc.sent.code)
    return None


def _close_reason_from_exception(exc: ConnectionClosedOK | ConnectionClosedError) -> str | None:
    if exc.rcvd is not None and exc.rcvd.reason:
        return str(exc.rcvd.reason)
    if exc.sent is not None and exc.sent.reason:
        return str(exc.sent.reason)
    return None


def _codex_websocket_response_headers(websocket: object, context: object | None) -> Mapping[str, str]:
    for source in (websocket, context):
        headers = _response_headers_from_source(source)
        if headers:
            return headers
    return {}


def _response_headers_from_source(source: object | None) -> Mapping[str, str]:
    if source is None:
        return {}
    for attr in ("response", "handshake_response"):
        response = getattr(source, attr, None)
        headers = getattr(response, "headers", None)
        if headers:
            return _normalize_response_headers(headers)
    for attr in ("headers", "response_headers"):
        headers = getattr(source, attr, None)
        if headers:
            return _normalize_response_headers(headers)
    return {}


def _normalize_response_headers(headers: Mapping[str, object] | None) -> dict[str, str]:
    if headers is None:
        return {}
    # ``websockets.Headers.items()`` performs a singular lookup for every
    # header name and raises ``MultipleValuesError`` for common repeated
    # response headers such as Set-Cookie. Iterate raw pairs when the mapping
    # supports them; the normalized single-value view intentionally keeps the
    # final occurrence, matching an ordinary dict comprehension.
    return {str(key).lower(): str(value) for key, value in _response_header_items(headers)}


def _response_header_items(headers: Mapping[str, object]) -> Iterable[tuple[object, object]]:
    raw_items = getattr(headers, "raw_items", None)
    if callable(raw_items):
        return cast(Iterable[tuple[object, object]], raw_items())
    return headers.items()


def _handshake_error_payload(
    status_code: int,
    message: str,
    headers: Headers | None = None,
    body: bytes | bytearray | None = None,
) -> OpenAIErrorEnvelope:
    parsed = _try_parse_handshake_error_payload(headers, body)
    if parsed is not None:
        return parsed
    if status_code == 401:
        return openai_error("invalid_api_key", message, error_type="authentication_error")
    if status_code == 429:
        return openai_error("rate_limit_exceeded", message, error_type="rate_limit_error")
    if status_code == 403:
        return openai_error("forbidden", message, error_type="permission_error")
    if status_code >= 500:
        return openai_error("upstream_error", message, error_type="server_error")
    return openai_error("invalid_request_error", message, error_type="invalid_request_error")


def _try_parse_handshake_error_payload(
    headers: Headers | None,
    body: bytes | bytearray | None,
) -> OpenAIErrorEnvelope | None:
    if not body:
        return None

    content_type = ""
    if headers is not None:
        # Repeated Content-Type is malformed, but it must remain an upstream
        # classification problem rather than crashing the proxy's error path.
        content_type = ", ".join(
            str(value) for key, value in _response_header_items(headers) if str(key).lower() == "content-type"
        )

    if "json" not in content_type.lower() and not body.strip().startswith((b"{", b"[")):
        return None

    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None

    error = parse_error_payload(payload)
    if error is None:
        return None
    return {"error": _openai_error_detail(error)}


def _openai_error_detail(error: OpenAIError) -> OpenAIErrorDetail:
    detail: OpenAIErrorDetail = {}
    if error.message is not None:
        detail["message"] = error.message
    if error.type is not None:
        detail["type"] = error.type
    if error.code is not None:
        detail["code"] = error.code
    if error.param is not None:
        detail["param"] = error.param
    if error.plan_type is not None:
        detail["plan_type"] = error.plan_type
    if error.resets_at is not None:
        detail["resets_at"] = error.resets_at
    if error.resets_in_seconds is not None:
        detail["resets_in_seconds"] = error.resets_in_seconds
    return detail
