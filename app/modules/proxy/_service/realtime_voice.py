from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import uuid
from collections.abc import Callable, Mapping
from typing import Any, Awaitable, Protocol, TypeVar, cast
from urllib.parse import unquote, urlsplit

from fastapi import WebSocket

from app.core.clients.proxy import CodexControlResponse, ProxyResponseError
from app.core.clients.proxy_websocket import (
    UpstreamResponsesWebSocket,
    UpstreamWebSocketMessage,
    connect_realtime_voice_websocket,
)
from app.core.config.settings import get_settings
from app.core.errors import openai_error
from app.db.models import Account, AccountStatus
from app.db.session import detach_session_objects
from app.modules.api_keys.service import ApiKeyData
from app.modules.proxy.realtime_call_repository import (
    RealtimeCallBindingConflictError,
    RealtimeCallBindingsRepository,
)
from app.modules.proxy.repo_bundle import ProxyRepoFactory, ProxyRepositories

logger = logging.getLogger("app.modules.proxy.service")

REALTIME_CALL_BINDING_TTL_SECONDS = 10 * 60.0
REALTIME_CALL_CLAIM_TTL_SECONDS = 30.0
REALTIME_CALL_CLAIM_RENEW_INTERVAL_SECONDS = 10.0

_RTC_CALL_ID_RE = re.compile(r"rtc_[A-Za-z0-9_-]{1,124}\Z")
_UUID_CALL_ID_RE = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\Z")
_UNAVAILABLE_ACCOUNT_STATUSES = frozenset(
    {
        AccountStatus.PAUSED,
        AccountStatus.REAUTH_REQUIRED,
        AccountStatus.DEACTIVATED,
    }
)
_INVALID_CLOSE_CODES = frozenset({1004, 1005, 1006, 1015})
_T = TypeVar("_T")


class _RealtimeVoiceServiceProtocol(Protocol):
    _encryptor: Any
    _load_balancer: Any
    _repo_factory: ProxyRepoFactory

    async def _ensure_fresh_with_budget_or_auth_error(
        self,
        account: Account,
        *,
        force: bool = False,
        timeout_seconds: float | None = None,
        error_type: str = "invalid_request_error",
    ) -> Account: ...

    async def _resolve_upstream_route_for_account(self, account: Account, *, operation: str) -> Any: ...

    def _get_work_admission(self) -> Any: ...


class _RealtimeVoiceMixin:
    async def bind_realtime_call_response(
        self,
        account: Account,
        response: CodexControlResponse,
        api_key: ApiKeyData | None,
    ) -> None:
        """Persist the final post-failover account before returning call SDP."""

        if response.status_code != 201:
            return
        call_id = realtime_call_id_from_location(response.headers)
        if call_id is None:
            raise ProxyResponseError(
                502,
                openai_error(
                    "invalid_upstream_response",
                    "Realtime call response did not contain a valid call id",
                    error_type="server_error",
                ),
                failure_phase="upstream_response_validation",
                upstream_status_code=201,
                upstream_error_code="invalid_upstream_response",
            )
        proxy = cast(_RealtimeVoiceServiceProtocol, self)
        try:
            async with proxy._repo_factory() as repos:
                repository = _required_realtime_repository(repos)
                await repository.create(
                    call_id=call_id,
                    account_id=account.id,
                    api_key_id=api_key.id if api_key is not None else None,
                    ttl_seconds=REALTIME_CALL_BINDING_TTL_SECONDS,
                )
        except RealtimeCallBindingConflictError as exc:
            raise ProxyResponseError(
                502,
                openai_error(
                    "realtime_call_id_conflict",
                    "Upstream reused an active realtime call id",
                    error_type="server_error",
                ),
                failure_phase="binding_persist",
            ) from exc
        except ProxyResponseError:
            raise
        except Exception as exc:
            logger.error("Failed to persist realtime call binding exception_type=%s", type(exc).__name__)
            raise ProxyResponseError(
                503,
                openai_error(
                    "realtime_call_binding_unavailable",
                    "Realtime call routing could not be persisted",
                    error_type="server_error",
                ),
                failure_phase="binding_persist",
            ) from exc

    async def proxy_realtime_voice_websocket(
        self,
        websocket: WebSocket,
        *,
        call_id: str,
        headers: Mapping[str, str],
        query: str,
        api_key: ApiKeyData | None,
    ) -> None:
        proxy = cast(_RealtimeVoiceServiceProtocol, self)
        normalized_call_id = normalize_realtime_call_id(call_id)
        if normalized_call_id is None:
            raise _join_denial(
                400,
                "invalid_realtime_call_id",
                "Invalid realtime call id",
                failure_phase="local_validation",
            )

        api_key_id = api_key.id if api_key is not None else None
        holder = uuid.uuid4().hex
        account: Account
        try:
            async with proxy._repo_factory() as repos:
                repository = _required_realtime_repository(repos)
                binding = await repository.get(normalized_call_id)
                binding_expired = binding is not None and binding.is_expired()
                api_key_match = binding is not None and binding.api_key_id == api_key_id
                logger.info(
                    "Realtime Voice binding lookup completed binding_found=%s binding_expired=%s api_key_match=%s",
                    binding is not None,
                    binding_expired,
                    api_key_match,
                )
                if binding is None or binding.is_expired():
                    raise _join_denial(
                        404,
                        "realtime_call_not_found",
                        "Realtime call was not found or has expired",
                        failure_phase="binding_lookup",
                    )
                if binding.api_key_id != api_key_id:
                    raise _join_denial(
                        403,
                        "realtime_call_forbidden",
                        "Realtime call belongs to another API key",
                        failure_phase="binding_authorization",
                    )
                claimed = await repository.claim(
                    call_id=normalized_call_id,
                    api_key_id=api_key_id,
                    holder=holder,
                    ttl_seconds=REALTIME_CALL_CLAIM_TTL_SECONDS,
                )
                logger.info("Realtime Voice binding claim completed claim_acquired=%s", claimed is not None)
                if claimed is None:
                    raise _join_denial(
                        409,
                        "realtime_call_already_joined",
                        "Realtime call is already being joined",
                        failure_phase="binding_claim",
                    )
                claim_handed_off = False
                try:
                    # The binding may have expired and been replaced between
                    # the initial read and the atomic claim.  The claimed row,
                    # not the pre-claim snapshot, owns the credential route.
                    loaded_account = await repos.accounts.get_by_id_fresh(claimed.account_id)
                    if (
                        api_key is not None
                        and api_key.account_assignment_scope_enabled
                        and claimed.account_id not in api_key.assigned_account_ids
                    ):
                        raise _join_denial(
                            403,
                            "realtime_call_account_scope_changed",
                            "Realtime call account is no longer assigned to this API key",
                            failure_phase="bound_account_authorization",
                        )
                    if loaded_account is None or loaded_account.status in _UNAVAILABLE_ACCOUNT_STATUSES:
                        raise _join_denial(
                            403,
                            "realtime_call_account_unavailable",
                            "Realtime call account is unavailable",
                            failure_phase="bound_account_authorization",
                        )
                    account = loaded_account
                    claim_handed_off = True
                    logger.info(
                        "Realtime Voice bound account authorized account_scope_allowed=True account_available=True"
                    )
                finally:
                    if not claim_handed_off:
                        with contextlib.suppress(Exception):
                            await repository.release(call_id=normalized_call_id, holder=holder)
                detach_session_objects(repos.accounts.session)
        except ProxyResponseError:
            raise
        except Exception as exc:
            logger.error("Failed to claim realtime call binding exception_type=%s", type(exc).__name__)
            raise ProxyResponseError(
                503,
                openai_error(
                    "realtime_call_binding_unavailable",
                    "Realtime call routing is temporarily unavailable",
                    error_type="server_error",
                ),
                failure_phase="binding_repository",
            ) from exc

        upstream: UpstreamResponsesWebSocket | None = None
        account_lease: Any | None = None
        claim_renewal = asyncio.create_task(
            _renew_claim(proxy, call_id=normalized_call_id, holder=holder),
            name=f"realtime-voice-claim-{holder}",
        )
        upstream_opened = False
        downstream_accepted = False
        setup_phase = "bound_account_admission"
        try:
            account_lease = await _await_while_claim_owned(
                proxy._load_balancer.acquire_account_lease(account.id, kind="stream"),
                claim_renewal,
                on_abandoned=proxy._load_balancer.release_account_lease,
            )
            if account_lease is None:
                raise _join_denial(
                    429,
                    "account_stream_concurrency_exceeded",
                    "The realtime call account has reached its stream concurrency limit",
                    failure_phase="bound_account_admission",
                )
            settings = get_settings()
            setup_phase = "bound_account_refresh"
            logger.info("Realtime Voice bound account refresh started")
            try:
                account = await _await_while_claim_owned(
                    proxy._ensure_fresh_with_budget_or_auth_error(
                        account,
                        timeout_seconds=settings.proxy_request_budget_seconds,
                    ),
                    claim_renewal,
                )
            except ProxyResponseError as exc:
                if exc.failure_phase is None:
                    exc.failure_phase = setup_phase
                raise
            logger.info("Realtime Voice bound account refresh succeeded")
            access_token = proxy._encryptor.decrypt(account.access_token_encrypted)
            upstream_account_id = account.chatgpt_account_id.strip() if account.chatgpt_account_id else None
            setup_phase = "upstream_connect_admission"
            connect_admission = await _await_while_claim_owned(
                proxy._get_work_admission().acquire_websocket_connect(),
                claim_renewal,
                on_abandoned=_release_admission_lease,
            )
            try:
                setup_phase = "bound_account_route"
                route = await _await_while_claim_owned(
                    proxy._resolve_upstream_route_for_account(
                        account,
                        operation="realtime_voice_sideband",
                    ),
                    claim_renewal,
                )
                logger.info(
                    "Realtime Voice bound account route resolved route_mode=%s",
                    "direct" if route is None else "configured_proxy",
                )
                setup_phase = "upstream_handshake"
                upstream = await _await_while_claim_owned(
                    connect_realtime_voice_websocket(
                        headers,
                        access_token,
                        upstream_account_id,
                        call_id=normalized_call_id,
                        query=query,
                        route=route,
                        allow_direct_egress=route is None,
                    ),
                    claim_renewal,
                    on_abandoned=_close_upstream,
                )
            finally:
                connect_admission.release()
            upstream_opened = True
            await _await_while_claim_owned(
                websocket.accept(),
                claim_renewal,
                on_abandoned=lambda _result: _close_downstream(
                    websocket,
                    code=1001,
                    reason="Realtime Voice setup cancelled",
                ),
            )
            downstream_accepted = True
            await _relay_realtime_voice(
                websocket,
                upstream,
                claim_renewal=claim_renewal,
            )
        except asyncio.CancelledError:
            raise
        except ProxyResponseError as exc:
            if exc.failure_phase is None:
                exc.failure_phase = setup_phase
            if downstream_accepted:
                await _close_downstream(websocket, code=1011, reason="Realtime Voice upstream connection failed")
                return
            raise
        except Exception as exc:
            logger.warning(
                "Realtime Voice sideband setup or relay failed failure_phase=%s exception_type=%s",
                setup_phase if not downstream_accepted else "relay",
                type(exc).__name__,
            )
            if downstream_accepted:
                await _close_downstream(websocket, code=1011, reason="Realtime Voice relay failed")
                return
            raise
        finally:
            if not claim_renewal.done():
                claim_renewal.cancel()
            await asyncio.gather(claim_renewal, return_exceptions=True)
            if upstream is not None:
                with contextlib.suppress(Exception):
                    await upstream.close()
            try:
                if account_lease is not None:
                    await proxy._load_balancer.release_account_lease(account_lease)
            finally:
                await _finish_binding(
                    proxy,
                    call_id=normalized_call_id,
                    holder=holder,
                    consumed=upstream_opened,
                )


def normalize_realtime_call_id(value: str) -> str | None:
    if _RTC_CALL_ID_RE.fullmatch(value):
        return value
    if _UUID_CALL_ID_RE.fullmatch(value):
        return str(uuid.UUID(value))
    return None


def realtime_call_id_from_location(headers: Mapping[str, str]) -> str | None:
    location = next((value for key, value in headers.items() if key.lower() == "location"), None)
    if not location:
        return None
    try:
        parsed = urlsplit(location)
    except ValueError:
        return None
    if parsed.fragment:
        return None
    segments = parsed.path.split("/")
    if not segments or not segments[-1]:
        return None
    call_id = unquote(segments[-1])
    if "/" in call_id or "\\" in call_id:
        return None
    return normalize_realtime_call_id(call_id)


async def _relay_realtime_voice(
    downstream: WebSocket,
    upstream: UpstreamResponsesWebSocket,
    *,
    claim_renewal: asyncio.Task[None],
) -> None:
    tasks = {
        asyncio.create_task(_relay_downstream_to_upstream(downstream, upstream)),
        asyncio.create_task(_relay_upstream_to_downstream(upstream, downstream)),
        claim_renewal,
    }
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            await task
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _await_while_claim_owned(
    awaitable: Awaitable[_T],
    claim_renewal: asyncio.Task[None],
    *,
    on_abandoned: Callable[[_T], Awaitable[None]] | None = None,
) -> _T:
    operation = asyncio.ensure_future(awaitable)
    try:
        done, _ = await asyncio.wait({operation, claim_renewal}, return_when=asyncio.FIRST_COMPLETED)
    except asyncio.CancelledError:
        await _abandon_operation(operation, on_abandoned)
        raise
    if claim_renewal in done:
        await _abandon_operation(operation, on_abandoned)
        await claim_renewal
        raise RuntimeError("Realtime Voice claim renewal stopped unexpectedly")
    if operation in done:
        return await operation
    raise RuntimeError("Realtime Voice setup wait ended without a completed task")


async def _abandon_operation(
    operation: asyncio.Future[_T],
    on_abandoned: Callable[[_T], Awaitable[None]] | None,
) -> None:
    if not operation.done():
        operation.cancel()
    await asyncio.gather(operation, return_exceptions=True)
    if on_abandoned is None or operation.cancelled() or operation.exception() is not None:
        return
    try:
        await on_abandoned(operation.result())
    except Exception:
        logger.warning("Failed to clean up abandoned Realtime Voice setup resource", exc_info=True)


async def _release_admission_lease(lease: Any) -> None:
    lease.release()


async def _close_upstream(upstream: UpstreamResponsesWebSocket) -> None:
    await upstream.close()


async def _relay_downstream_to_upstream(
    downstream: WebSocket,
    upstream: UpstreamResponsesWebSocket,
) -> None:
    while True:
        message = await downstream.receive()
        message_type = message.get("type")
        if message_type == "websocket.disconnect":
            code = _safe_close_code(message.get("code"), default=1000)
            reason = _safe_close_reason(message.get("reason"))
            await upstream.close(code=code, reason=reason)
            return
        if message_type != "websocket.receive":
            continue
        text = message.get("text")
        if isinstance(text, str):
            await upstream.send_text(text)
            continue
        data = message.get("bytes")
        if isinstance(data, bytes):
            await upstream.send_bytes(data)


async def _relay_upstream_to_downstream(
    upstream: UpstreamResponsesWebSocket,
    downstream: WebSocket,
) -> None:
    while True:
        message = await upstream.receive()
        if message.kind == "text" and message.text is not None:
            await downstream.send_text(message.text)
            continue
        if message.kind == "binary" and message.data is not None:
            await downstream.send_bytes(message.data)
            continue
        await _close_downstream(
            downstream,
            code=_safe_close_code(message.close_code, default=1000 if message.kind == "close" else 1011),
            reason=_upstream_close_reason(message),
        )
        return


async def _renew_claim(
    proxy: _RealtimeVoiceServiceProtocol,
    *,
    call_id: str,
    holder: str,
) -> None:
    while True:
        await asyncio.sleep(REALTIME_CALL_CLAIM_RENEW_INTERVAL_SECONDS)
        async with proxy._repo_factory() as repos:
            renewed = await _required_realtime_repository(repos).renew(
                call_id=call_id,
                holder=holder,
                ttl_seconds=REALTIME_CALL_CLAIM_TTL_SECONDS,
            )
        if not renewed:
            raise RuntimeError("Realtime Voice call claim was lost")


async def _finish_binding(
    proxy: _RealtimeVoiceServiceProtocol,
    *,
    call_id: str,
    holder: str,
    consumed: bool,
) -> None:
    try:
        async with proxy._repo_factory() as repos:
            repository = _required_realtime_repository(repos)
            if consumed:
                await repository.delete_claimed(call_id=call_id, holder=holder)
            else:
                await repository.release(call_id=call_id, holder=holder)
    except Exception:
        logger.warning("Failed to finalize realtime call binding", exc_info=True)


async def _close_downstream(websocket: WebSocket, *, code: int, reason: str) -> None:
    with contextlib.suppress(Exception):
        await websocket.close(code=code, reason=_safe_close_reason(reason))


def _upstream_close_reason(message: UpstreamWebSocketMessage) -> str:
    if message.close_reason:
        return _safe_close_reason(message.close_reason)
    if message.kind == "error":
        return "Realtime Voice upstream websocket closed unexpectedly"
    return ""


def _safe_close_code(value: object, *, default: int) -> int:
    if (
        not isinstance(value, int)
        or value < 1000
        or value > 4999
        or value in _INVALID_CLOSE_CODES
        or 1016 <= value < 3000
    ):
        return default
    return value


def _safe_close_reason(value: object) -> str:
    if not isinstance(value, str):
        return ""
    encoded = value.encode("utf-8")
    if len(encoded) <= 123:
        return value
    return encoded[:123].decode("utf-8", errors="ignore")


def _join_denial(
    status_code: int,
    code: str,
    message: str,
    *,
    failure_phase: str,
) -> ProxyResponseError:
    error_type = "permission_error" if status_code == 403 else "invalid_request_error"
    if status_code >= 500:
        error_type = "server_error"
    return ProxyResponseError(
        status_code,
        openai_error(code, message, error_type=error_type),
        failure_phase=failure_phase,
    )


def _required_realtime_repository(repos: ProxyRepositories) -> RealtimeCallBindingsRepository:
    repository = repos.realtime_calls
    if repository is None:
        raise RuntimeError("Realtime call bindings repository is not configured")
    return repository
