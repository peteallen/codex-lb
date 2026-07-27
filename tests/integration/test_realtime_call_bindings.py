from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocket
from sqlalchemy import delete, update

import app.modules.proxy._service.realtime_voice as realtime_voice_module
from app.core.clients.proxy import ProxyResponseError
from app.core.clients.proxy_websocket import UpstreamWebSocketMessage, build_realtime_voice_websocket_headers
from app.core.errors import openai_error
from app.core.utils.time import utcnow
from app.db.models import Account, AccountStatus, ApiKey, RealtimeCallBinding
from app.db.session import get_background_session
from app.dependencies import _proxy_repo_context
from app.modules.api_keys.service import ApiKeyData
from app.modules.proxy.realtime_call_repository import (
    RealtimeCallBindingConflictError,
    RealtimeCallBindingsRepository,
)
from app.modules.proxy.service import ProxyService

pytestmark = pytest.mark.integration


async def _insert_account_and_key(
    *,
    account_id: str = "voice-account",
    api_key_id: str = "voice-key",
    chatgpt_account_id: str = "chatgpt-workspace",
    codex_installation_id: str | None = None,
) -> None:
    async with get_background_session() as session:
        session.add(
            Account(
                id=account_id,
                chatgpt_account_id=chatgpt_account_id,
                email=f"{account_id}@example.com",
                plan_type="plus",
                access_token_encrypted=b"access",
                refresh_token_encrypted=b"refresh",
                id_token_encrypted=b"id",
                last_refresh=utcnow(),
                status=AccountStatus.ACTIVE,
                codex_installation_id=codex_installation_id,
            )
        )
        session.add(
            ApiKey(
                id=api_key_id,
                name="Voice key",
                key_hash=f"hash-{api_key_id}",
                key_prefix="sk-voice",
                is_active=True,
            )
        )
        await session.commit()


def _api_key(
    key_id: str = "voice-key",
    *,
    scoped: bool = False,
    assigned_account_ids: list[str] | None = None,
) -> ApiKeyData:
    return ApiKeyData(
        id=key_id,
        name="Voice key",
        key_prefix="sk-voice",
        allowed_models=None,
        enforced_model=None,
        enforced_reasoning_effort=None,
        enforced_service_tier=None,
        expires_at=None,
        is_active=True,
        created_at=datetime(2026, 7, 23),
        last_used_at=None,
        account_assignment_scope_enabled=scoped,
        assigned_account_ids=assigned_account_ids or [],
    )


@pytest.mark.asyncio
async def test_realtime_call_binding_claim_is_atomic_and_releasable(db_setup) -> None:
    del db_setup
    await _insert_account_and_key()
    async with get_background_session() as session:
        await RealtimeCallBindingsRepository(session).create(
            call_id="rtc_atomic",
            account_id="voice-account",
            api_key_id="voice-key",
            ttl_seconds=600,
        )

    async def claim(holder: str):
        async with get_background_session() as session:
            return await RealtimeCallBindingsRepository(session).claim(
                call_id="rtc_atomic",
                api_key_id="voice-key",
                holder=holder,
                ttl_seconds=30,
            )

    first, second = await asyncio.gather(claim("replica-a"), claim("replica-b"))
    assert sum(result is not None for result in (first, second)) == 1
    winner = "replica-a" if first is not None else "replica-b"
    loser = "replica-b" if winner == "replica-a" else "replica-a"

    async with get_background_session() as session:
        repository = RealtimeCallBindingsRepository(session)
        assert await repository.renew(call_id="rtc_atomic", holder=loser, ttl_seconds=30) is False
        await repository.release(call_id="rtc_atomic", holder=loser)
        still_claimed = await repository.get("rtc_atomic")
        assert still_claimed is not None
        assert still_claimed.claim_holder == winner
        await repository.release(call_id="rtc_atomic", holder=winner)

    reclaimed = await claim(loser)
    assert reclaimed is not None
    assert reclaimed.account_id == "voice-account"


@pytest.mark.asyncio
async def test_realtime_call_binding_collision_is_first_writer_wins(db_setup) -> None:
    del db_setup
    await _insert_account_and_key()
    await _insert_account_and_key(account_id="voice-account-2", api_key_id="voice-key-2")
    async with get_background_session() as session:
        repository = RealtimeCallBindingsRepository(session)
        first = await repository.create(
            call_id="rtc_collision",
            account_id="voice-account",
            api_key_id="voice-key",
            ttl_seconds=600,
        )
        with pytest.raises(RealtimeCallBindingConflictError):
            await repository.create(
                call_id="rtc_collision",
                account_id="voice-account-2",
                api_key_id="voice-key-2",
                ttl_seconds=1200,
            )
        retained = await repository.get("rtc_collision")

    assert retained is not None
    assert retained.account_id == "voice-account"
    assert retained.api_key_id == "voice-key"
    assert retained.created_at == first.created_at
    assert retained.expires_at == first.expires_at


@pytest.mark.asyncio
async def test_realtime_call_binding_rejects_expired_or_wrong_key_claim(db_setup) -> None:
    del db_setup
    await _insert_account_and_key()
    async with get_background_session() as session:
        repository = RealtimeCallBindingsRepository(session)
        await repository.create(
            call_id="rtc_expired",
            account_id="voice-account",
            api_key_id="voice-key",
            ttl_seconds=600,
        )
        assert (
            await repository.claim(
                call_id="rtc_expired",
                api_key_id="other-key",
                holder="wrong-key",
                ttl_seconds=30,
            )
            is None
        )
        await session.execute(
            update(RealtimeCallBinding)
            .where(RealtimeCallBinding.call_id == "rtc_expired")
            .values(expires_at=utcnow() - timedelta(seconds=1))
        )
        await session.commit()
        assert (
            await repository.claim(
                call_id="rtc_expired",
                api_key_id="voice-key",
                holder="late",
                ttl_seconds=30,
            )
            is None
        )


@pytest.mark.asyncio
async def test_realtime_call_binding_is_deleted_when_owning_api_key_is_deleted(db_setup) -> None:
    del db_setup
    await _insert_account_and_key()
    await _create_binding(call_id="rtc_key_cascade")

    async with get_background_session() as session:
        api_key = await session.get(ApiKey, "voice-key")
        assert api_key is not None
        await session.delete(api_key)
        await session.commit()
    async with get_background_session() as session:
        assert await RealtimeCallBindingsRepository(session).get("rtc_key_cascade") is None


class _FakeDownstream:
    def __init__(self) -> None:
        self.accepted = False
        self.sent_text: list[str] = []
        self.sent_bytes: list[bytes] = []
        self.closed: list[tuple[int, str]] = []
        self._never = asyncio.Event()

    async def accept(self) -> None:
        self.accepted = True

    async def receive(self):
        await self._never.wait()
        raise AssertionError("unreachable")

    async def send_text(self, value: str) -> None:
        self.sent_text.append(value)

    async def send_bytes(self, value: bytes) -> None:
        self.sent_bytes.append(value)

    async def close(self, *, code: int = 1000, reason: str = "") -> None:
        self.closed.append((code, reason))


class _FakeUpstream:
    def __init__(self, messages: list[UpstreamWebSocketMessage]) -> None:
        self.messages = list(messages)
        self.sent_text: list[str] = []
        self.sent_bytes: list[bytes] = []
        self.closed: list[tuple[int, str]] = []

    async def send_text(self, value: str) -> None:
        self.sent_text.append(value)

    async def send_bytes(self, value: bytes) -> None:
        self.sent_bytes.append(value)

    async def receive(self) -> UpstreamWebSocketMessage:
        return self.messages.pop(0)

    async def close(self, *, code: int = 1000, reason: str = "") -> None:
        self.closed.append((code, reason))

    def response_header(self, _name: str) -> str | None:
        return None


class _ScriptedDownstream(_FakeDownstream):
    def __init__(self, messages: list[dict[str, object]]) -> None:
        super().__init__()
        self.messages = list(messages)

    async def receive(self) -> dict[str, object]:
        return self.messages.pop(0)


class _BlockingUpstream(_FakeUpstream):
    def __init__(self) -> None:
        super().__init__([])
        self._block = asyncio.Event()

    async def receive(self) -> UpstreamWebSocketMessage:
        await self._block.wait()
        raise AssertionError("unreachable")


class _FailAcceptDownstream(_FakeDownstream):
    async def accept(self) -> None:
        raise RuntimeError("downstream accept failed")


class _ObservedDownstream(_FakeDownstream):
    def __init__(self) -> None:
        super().__init__()
        self.accepted_event = asyncio.Event()

    async def accept(self) -> None:
        await super().accept()
        self.accepted_event.set()


class _AdmissionLease:
    def __init__(self) -> None:
        self.released = False

    def release(self) -> None:
        self.released = True


class _AdmissionController:
    def __init__(self, *, error: ProxyResponseError | None = None) -> None:
        self.error = error
        self.calls = 0
        self.lease = _AdmissionLease()

    async def acquire_websocket_connect(self) -> _AdmissionLease:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.lease


async def _create_binding(call_id: str = "rtc_service") -> None:
    async with get_background_session() as session:
        await RealtimeCallBindingsRepository(session).create(
            call_id=call_id,
            account_id="voice-account",
            api_key_id="voice-key",
            ttl_seconds=600,
        )


def _service(monkeypatch) -> ProxyService:
    service = ProxyService(repo_factory=_proxy_repo_context)
    service._encryptor = SimpleNamespace(decrypt=lambda _value: "upstream-token")

    async def fresh(account, **_kwargs):
        return account

    monkeypatch.setattr(service, "_ensure_fresh_with_budget_or_auth_error", fresh)
    monkeypatch.setattr(service, "_resolve_upstream_route_for_account", AsyncMock(return_value=None))
    return service


@pytest.mark.asyncio
async def test_realtime_voice_sideband_relays_and_consumes_binding(db_setup, monkeypatch) -> None:
    del db_setup
    await _insert_account_and_key(codex_installation_id="stored-installation-must-not-be-injected")
    await _create_binding()
    service = _service(monkeypatch)
    admission = _AdmissionController()
    monkeypatch.setattr(service, "_get_work_admission", lambda: admission)
    downstream = _FakeDownstream()
    upstream = _FakeUpstream(
        [
            UpstreamWebSocketMessage(kind="text", text="delegation-event"),
            UpstreamWebSocketMessage(kind="binary", data=b"audio-control"),
            UpstreamWebSocketMessage(kind="close", close_code=1001, close_reason="voice complete"),
        ]
    )
    captured: dict[str, object] = {}

    async def connect(headers, access_token, account_id, **kwargs):
        captured.update(
            headers=build_realtime_voice_websocket_headers(headers, access_token, account_id),
            access_token=access_token,
            account_id=account_id,
            **kwargs,
        )
        return upstream

    monkeypatch.setattr(realtime_voice_module, "connect_realtime_voice_websocket", connect)

    await service.proxy_realtime_voice_websocket(
        cast(WebSocket, downstream),
        call_id="rtc_service",
        headers={
            "openai-alpha": "quicksilver=v2",
            "x-session-id": "session-1",
            "x-oai-attestation": "same-call-attestation",
            "x-codex-installation-id": "client-installation-must-not-be-forwarded",
        },
        query="intent=quicksilver&architecture=avas",
        api_key=_api_key(),
    )

    assert downstream.accepted is True
    assert downstream.sent_text == ["delegation-event"]
    assert downstream.sent_bytes == [b"audio-control"]
    assert downstream.closed == [(1001, "voice complete")]
    assert captured["access_token"] == "upstream-token"
    assert captured["account_id"] == "chatgpt-workspace"
    assert captured["call_id"] == "rtc_service"
    assert captured["query"] == "intent=quicksilver&architecture=avas"
    assert captured["allow_direct_egress"] is True
    captured_headers = {key.lower(): value for key, value in cast(dict[str, str], captured["headers"]).items()}
    assert captured_headers["x-oai-attestation"] == "same-call-attestation"
    assert "x-codex-installation-id" not in captured_headers
    assert admission.calls == 1
    assert admission.lease.released is True
    async with get_background_session() as session:
        assert await RealtimeCallBindingsRepository(session).get("rtc_service") is None


@pytest.mark.asyncio
async def test_realtime_voice_uses_account_from_authoritative_claim(db_setup, monkeypatch) -> None:
    del db_setup
    await _insert_account_and_key()
    await _insert_account_and_key(
        account_id="voice-account-replacement",
        api_key_id="unused-voice-key",
        chatgpt_account_id="replacement-workspace",
    )
    await _create_binding(call_id="rtc_replaced_binding")
    original_claim = RealtimeCallBindingsRepository.claim

    async def replace_then_claim(repository, **kwargs):
        await repository._session.execute(  # noqa: SLF001 - controlled TOCTOU regression setup
            update(RealtimeCallBinding)
            .where(RealtimeCallBinding.call_id == "rtc_replaced_binding")
            .values(account_id="voice-account-replacement")
        )
        await repository._session.commit()  # noqa: SLF001 - controlled TOCTOU regression setup
        return await original_claim(repository, **kwargs)

    monkeypatch.setattr(RealtimeCallBindingsRepository, "claim", replace_then_claim)
    service = _service(monkeypatch)
    captured_account_ids: list[str | None] = []

    async def connect(_headers, _access_token, account_id, **_kwargs):
        captured_account_ids.append(account_id)
        return _FakeUpstream([UpstreamWebSocketMessage(kind="close", close_code=1000)])

    monkeypatch.setattr(realtime_voice_module, "connect_realtime_voice_websocket", connect)

    await service.proxy_realtime_voice_websocket(
        cast(WebSocket, _FakeDownstream()),
        call_id="rtc_replaced_binding",
        headers={},
        query="",
        api_key=_api_key(),
    )

    assert captured_account_ids == ["replacement-workspace"]


@pytest.mark.asyncio
async def test_realtime_voice_sideband_relays_downstream_frames_and_close(db_setup, monkeypatch) -> None:
    del db_setup
    await _insert_account_and_key()
    await _create_binding(call_id="rtc_downstream")
    service = _service(monkeypatch)
    downstream = _ScriptedDownstream(
        [
            {"type": "websocket.receive", "text": "client-control"},
            {"type": "websocket.receive", "bytes": b"client-binary"},
            {"type": "websocket.disconnect", "code": 1001, "reason": "client done"},
        ]
    )
    upstream = _BlockingUpstream()

    async def connect(*_args, **_kwargs):
        return upstream

    monkeypatch.setattr(realtime_voice_module, "connect_realtime_voice_websocket", connect)

    await service.proxy_realtime_voice_websocket(
        cast(WebSocket, downstream),
        call_id="rtc_downstream",
        headers={},
        query="",
        api_key=_api_key(),
    )

    assert upstream.sent_text == ["client-control"]
    assert upstream.sent_bytes == [b"client-binary"]
    assert upstream.closed[0] == (1001, "client done")
    async with get_background_session() as session:
        assert await RealtimeCallBindingsRepository(session).get("rtc_downstream") is None


@pytest.mark.asyncio
async def test_realtime_voice_renews_claim_during_slow_upstream_open(db_setup, monkeypatch) -> None:
    del db_setup
    await _insert_account_and_key()
    await _create_binding(call_id="rtc_slow_open")
    service = _service(monkeypatch)
    connect_started = asyncio.Event()
    allow_connect = asyncio.Event()
    # Repository TTLs are clamped to one second. Wait beyond that floor so
    # this would become claimable without the renewal loop.
    monkeypatch.setattr(realtime_voice_module, "REALTIME_CALL_CLAIM_TTL_SECONDS", 1.0)
    monkeypatch.setattr(realtime_voice_module, "REALTIME_CALL_CLAIM_RENEW_INTERVAL_SECONDS", 0.2)

    async def connect(*_args, **_kwargs):
        connect_started.set()
        await allow_connect.wait()
        return _FakeUpstream([UpstreamWebSocketMessage(kind="close", close_code=1000)])

    monkeypatch.setattr(realtime_voice_module, "connect_realtime_voice_websocket", connect)
    join = asyncio.create_task(
        service.proxy_realtime_voice_websocket(
            cast(WebSocket, _FakeDownstream()),
            call_id="rtc_slow_open",
            headers={},
            query="",
            api_key=_api_key(),
        )
    )
    await asyncio.wait_for(connect_started.wait(), timeout=1)
    await asyncio.sleep(1.25)
    async with get_background_session() as session:
        competing = await RealtimeCallBindingsRepository(session).claim(
            call_id="rtc_slow_open",
            api_key_id="voice-key",
            holder="replica-b",
            ttl_seconds=30,
        )
    assert competing is None

    allow_connect.set()
    await asyncio.wait_for(join, timeout=1)


@pytest.mark.asyncio
async def test_realtime_voice_terminates_relay_when_claim_is_lost(db_setup, monkeypatch) -> None:
    del db_setup
    await _insert_account_and_key()
    await _create_binding(call_id="rtc_claim_lost")
    service = _service(monkeypatch)
    downstream = _ObservedDownstream()
    upstream = _BlockingUpstream()
    monkeypatch.setattr(realtime_voice_module, "REALTIME_CALL_CLAIM_TTL_SECONDS", 0.12)
    monkeypatch.setattr(realtime_voice_module, "REALTIME_CALL_CLAIM_RENEW_INTERVAL_SECONDS", 0.03)

    async def connect(*_args, **_kwargs):
        return upstream

    monkeypatch.setattr(realtime_voice_module, "connect_realtime_voice_websocket", connect)
    join = asyncio.create_task(
        service.proxy_realtime_voice_websocket(
            cast(WebSocket, downstream),
            call_id="rtc_claim_lost",
            headers={},
            query="",
            api_key=_api_key(),
        )
    )
    await asyncio.wait_for(downstream.accepted_event.wait(), timeout=1)
    async with get_background_session() as session:
        await session.execute(delete(RealtimeCallBinding).where(RealtimeCallBinding.call_id == "rtc_claim_lost"))
        await session.commit()

    await asyncio.wait_for(join, timeout=1)

    assert downstream.closed == [(1011, "Realtime Voice relay failed")]
    assert upstream.closed


@pytest.mark.asyncio
async def test_realtime_voice_consumes_binding_when_downstream_accept_fails_after_upstream_open(
    db_setup,
    monkeypatch,
) -> None:
    del db_setup
    await _insert_account_and_key()
    await _create_binding(call_id="rtc_accept_failure")
    service = _service(monkeypatch)
    upstream = _FakeUpstream([UpstreamWebSocketMessage(kind="close", close_code=1000)])

    async def connect(*_args, **_kwargs):
        return upstream

    monkeypatch.setattr(realtime_voice_module, "connect_realtime_voice_websocket", connect)
    with pytest.raises(RuntimeError, match="downstream accept failed"):
        await service.proxy_realtime_voice_websocket(
            cast(WebSocket, _FailAcceptDownstream()),
            call_id="rtc_accept_failure",
            headers={},
            query="",
            api_key=_api_key(),
        )

    assert upstream.closed
    async with get_background_session() as session:
        assert await RealtimeCallBindingsRepository(session).get("rtc_accept_failure") is None


@pytest.mark.asyncio
async def test_realtime_voice_global_connect_admission_denial_keeps_binding_retryable(db_setup, monkeypatch) -> None:
    del db_setup
    await _insert_account_and_key()
    await _create_binding(call_id="rtc_admission")
    service = _service(monkeypatch)
    admission = _AdmissionController(
        error=ProxyResponseError(429, openai_error("global_admission_timeout", "temporarily overloaded"))
    )
    monkeypatch.setattr(service, "_get_work_admission", lambda: admission)
    connect = AsyncMock(side_effect=AssertionError("upstream must not be called"))
    monkeypatch.setattr(realtime_voice_module, "connect_realtime_voice_websocket", connect)

    with pytest.raises(ProxyResponseError) as caught:
        await service.proxy_realtime_voice_websocket(
            cast(WebSocket, _FakeDownstream()),
            call_id="rtc_admission",
            headers={},
            query="",
            api_key=_api_key(),
        )

    assert caught.value.status_code == 429
    assert admission.calls == 1
    connect.assert_not_awaited()
    async with get_background_session() as session:
        retained = await RealtimeCallBindingsRepository(session).get("rtc_admission")
        assert retained is not None
        assert retained.claim_holder is None


@pytest.mark.asyncio
async def test_realtime_voice_preopen_failure_releases_claim_for_same_account_retry(db_setup, monkeypatch) -> None:
    del db_setup
    await _insert_account_and_key()
    await _create_binding(call_id="rtc_retry")
    service = _service(monkeypatch)
    account_ids: list[str | None] = []

    async def fail_connect(_headers, _access_token, account_id, **_kwargs):
        account_ids.append(account_id)
        raise ProxyResponseError(502, openai_error("upstream_unavailable", "connect failed"))

    monkeypatch.setattr(realtime_voice_module, "connect_realtime_voice_websocket", fail_connect)
    with pytest.raises(ProxyResponseError) as caught:
        await service.proxy_realtime_voice_websocket(
            cast(WebSocket, _FakeDownstream()),
            call_id="rtc_retry",
            headers={},
            query="",
            api_key=_api_key(),
        )
    assert caught.value.status_code == 502
    async with get_background_session() as session:
        retained = await RealtimeCallBindingsRepository(session).get("rtc_retry")
        assert retained is not None
        assert retained.account_id == "voice-account"
        assert retained.claim_holder is None

    async def succeed_connect(_headers, _access_token, account_id, **_kwargs):
        account_ids.append(account_id)
        return _FakeUpstream([UpstreamWebSocketMessage(kind="close", close_code=1000)])

    monkeypatch.setattr(realtime_voice_module, "connect_realtime_voice_websocket", succeed_connect)
    await service.proxy_realtime_voice_websocket(
        cast(WebSocket, _FakeDownstream()),
        call_id="rtc_retry",
        headers={},
        query="",
        api_key=_api_key(),
    )
    assert account_ids == ["chatgpt-workspace", "chatgpt-workspace"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("call_id", "api_key", "expected_status"),
    [
        ("rtc_unknown", _api_key(), 404),
        ("rtc_guarded", _api_key("wrong-key"), 403),
        ("rtc_guarded", _api_key(scoped=True, assigned_account_ids=["different-account"]), 403),
    ],
)
async def test_realtime_voice_denials_make_no_upstream_request(
    db_setup,
    monkeypatch,
    call_id: str,
    api_key: ApiKeyData,
    expected_status: int,
) -> None:
    del db_setup
    await _insert_account_and_key()
    await _create_binding(call_id="rtc_guarded")
    service = _service(monkeypatch)
    connect = AsyncMock(side_effect=AssertionError("upstream must not be called"))
    monkeypatch.setattr(realtime_voice_module, "connect_realtime_voice_websocket", connect)

    with pytest.raises(ProxyResponseError) as caught:
        await service.proxy_realtime_voice_websocket(
            cast(WebSocket, _FakeDownstream()),
            call_id=call_id,
            headers={},
            query="",
            api_key=api_key,
        )
    assert caught.value.status_code == expected_status
    connect.assert_not_awaited()
