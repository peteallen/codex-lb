"""Recovery behavior layered on the eventless response.created watchdog.

The watchdog itself (bounded wait, parser-visible keepalives, retirement and
startup cleanup) is upstream behavior. These tests cover the three recovery
properties that upstream does not yet provide:

* a proxy-injected durable reattach anchor that upstream accepted and then
  ignored is invalidated on an exact match, so the lane self-heals instead of
  handing the same dead anchor to every later request;
* a client-supplied ``previous_response_id`` is never invalidated;
* a sibling request that is already streaming downstream keeps its stream --
  the bridge is quarantined rather than closed under it;
* reader-driven failures keep API-key attribution in the request log.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any, Callable, cast
from unittest.mock import AsyncMock, Mock

import anyio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.clients.proxy_websocket import UpstreamResponsesWebSocket, UpstreamWebSocketMessage
from app.core.utils.time import utcnow
from app.db.models import AccountStatus, Base
from app.modules.proxy import service as proxy_service
from app.modules.proxy._service.http_bridge import request_submit as http_bridge_request_submit_module
from app.modules.proxy.durable_bridge_coordinator import DurableBridgeSessionCoordinator

pytestmark = pytest.mark.unit

_INSTANCE_ID = "test-missing-response-created-instance"
_STUCK_GATE_RETIRE_AFTER_SECONDS = 0.02


class _SilentUpstream:
    """Accepts the send, then never emits a frame -- the observed failure mode."""

    def __init__(self) -> None:
        self.first_receive_started = asyncio.Event()
        self.receive_calls = 0
        self.closed = False
        self.sent_texts: list[str] = []

    async def receive(self) -> UpstreamWebSocketMessage:
        self.receive_calls += 1
        self.first_receive_started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async def send_text(self, text: str) -> None:
        self.sent_texts.append(text)

    async def close(self) -> None:
        self.closed = True


class _SilentAfterSiblingOutputUpstream(_SilentUpstream):
    """Delivers one sibling delta, then goes silent for the anchored owner."""

    def __init__(self, sibling_response_id: str) -> None:
        super().__init__()
        self._sibling_response_id = sibling_response_id

    async def receive(self) -> UpstreamWebSocketMessage:
        self.receive_calls += 1
        self.first_receive_started.set()
        if self.receive_calls == 1:
            return UpstreamWebSocketMessage(
                kind="text",
                text=json.dumps(
                    {
                        "type": "response.output_text.delta",
                        "response_id": self._sibling_response_id,
                        "delta": "hi",
                    },
                    separators=(",", ":"),
                ),
            )
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


def _make_settings() -> SimpleNamespace:
    return SimpleNamespace(
        sse_keepalive_interval_seconds=0.0,
        stream_idle_timeout_seconds=60.0,
        http_responses_session_bridge_request_budget_seconds=60.0,
        http_responses_session_bridge_stuck_gate_retire_after_seconds=_STUCK_GATE_RETIRE_AFTER_SECONDS,
        http_responses_session_bridge_instance_id=_INSTANCE_ID,
    )


def _make_session(key_value: str) -> proxy_service._HTTPBridgeSession:
    return proxy_service._HTTPBridgeSession(
        key=proxy_service._HTTPBridgeSessionKey("session_header", key_value, None),
        headers={"session_id": key_value},
        affinity=proxy_service._AffinityPolicy(
            key=key_value,
            kind=proxy_service.StickySessionKind.CODEX_SESSION,
        ),
        request_model="gpt-5.6-luna",
        account=cast(Any, SimpleNamespace(id="acc-bridge", status=AccountStatus.ACTIVE, plan_type="plus")),
        upstream=cast(UpstreamResponsesWebSocket, SimpleNamespace(close=AsyncMock())),
        upstream_control=proxy_service._WebSocketUpstreamControl(),
        pending_requests=deque(),
        pending_lock=anyio.Lock(),
        response_create_gate=asyncio.Semaphore(1),
        queued_request_count=0,
        last_used_at=1.0,
        idle_ttl_seconds=120.0,
    )


def _make_anchored_owner(
    *,
    request_id: str,
    previous_response_id: str,
    proxy_injected: bool,
) -> proxy_service._WebSocketRequestState:
    return proxy_service._WebSocketRequestState(
        request_id=request_id,
        model="gpt-5.6-luna",
        service_tier=None,
        reasoning_effort="high",
        api_key_reservation=None,
        started_at=time.monotonic() - 30.0,
        transport="http",
        awaiting_response_created=True,
        response_create_sent_at=None,
        event_queue=asyncio.Queue(),
        previous_response_id=previous_response_id,
        proxy_injected_previous_response_id=proxy_injected,
    )


def _make_streaming_sibling(response_id: str) -> proxy_service._WebSocketRequestState:
    return proxy_service._WebSocketRequestState(
        request_id=f"req-sibling-{response_id}",
        model="gpt-5.6-luna",
        service_tier=None,
        reasoning_effort="high",
        api_key_reservation=None,
        started_at=time.monotonic(),
        transport="http",
        response_id=response_id,
        event_queue=asyncio.Queue(),
    )


async def _make_durable_coordinator() -> tuple[DurableBridgeSessionCoordinator, Any]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    coordinator = DurableBridgeSessionCoordinator(cast(Callable[[], AsyncSession], session_factory))
    return coordinator, engine


async def _claim_durable_session(
    coordinator: DurableBridgeSessionCoordinator,
    *,
    key_value: str,
    latest_response_id: str,
) -> str:
    lookup = await coordinator.claim_live_session(
        session_key_kind="session_header",
        session_key_value=key_value,
        api_key_id=None,
        instance_id=_INSTANCE_ID,
        lease_ttl_seconds=60.0,
        account_id="acc-bridge",
        model="gpt-5.6-luna",
        service_tier=None,
        latest_turn_state=None,
        latest_response_id=latest_response_id,
        allow_takeover=True,
    )
    return lookup.session_id


async def _durable_latest_response_id(
    coordinator: DurableBridgeSessionCoordinator,
    key_value: str,
) -> str | None:
    lookup = await coordinator.lookup_request_targets(
        session_key_kind="session_header",
        session_key_value=key_value,
        api_key_id=None,
        turn_state=None,
        session_header=key_value,
        previous_response_id=None,
    )
    assert lookup is not None
    return lookup.latest_response_id


async def _drain_event_queue(event_queue: asyncio.Queue[str | None]) -> list[str]:
    blocks: list[str] = []
    while (block := await asyncio.wait_for(event_queue.get(), timeout=0.2)) is not None:
        blocks.append(block)
    return blocks


async def _run_watchdog_against_silent_upstream(
    monkeypatch: pytest.MonkeyPatch,
    *,
    key_value: str,
    owner: proxy_service._WebSocketRequestState,
    latest_response_id: str,
    upstream: _SilentUpstream | None = None,
    sibling: proxy_service._WebSocketRequestState | None = None,
) -> tuple[proxy_service.ProxyService, proxy_service._HTTPBridgeSession, _SilentUpstream, Any]:
    service = proxy_service.ProxyService(cast(Any, nullcontext()))
    coordinator, engine = await _make_durable_coordinator()
    service._durable_bridge = coordinator

    session = _make_session(key_value)
    session.durable_session_id = await _claim_durable_session(
        coordinator,
        key_value=key_value,
        latest_response_id=latest_response_id,
    )
    active_upstream = upstream if upstream is not None else _SilentUpstream()
    session.upstream = cast(UpstreamResponsesWebSocket, active_upstream)
    service._http_bridge_sessions[session.key] = session

    monkeypatch.setattr(proxy_service, "get_settings", lambda: _make_settings())
    monkeypatch.setattr(service, "_retry_http_bridge_precreated_request", AsyncMock(return_value=False))
    monkeypatch.setattr(service, "_handle_stream_error", AsyncMock())
    monkeypatch.setattr(service, "_write_request_log", AsyncMock())
    monkeypatch.setattr(proxy_service, "_record_http_bridge_stuck_retire", Mock())

    reader_task = asyncio.create_task(service._relay_http_bridge_upstream_messages(session))
    await asyncio.wait_for(active_upstream.first_receive_started.wait(), timeout=0.5)

    gate = session.response_create_gate
    await gate.acquire()
    owner.response_create_gate = gate
    owner.response_create_gate_acquired = True
    owner.request_text = '{"type":"response.create","model":"gpt-5.6-luna","input":"hello"}'
    async with session.pending_lock:
        if sibling is not None:
            session.pending_requests.append(sibling)
        session.pending_requests.append(owner)
        session.queued_request_count = len(session.pending_requests)

    await http_bridge_request_submit_module._send_http_bridge_request_text_with_archive_id(
        session,
        owner,
        owner.request_text,
    )
    if sibling is None:
        await asyncio.wait_for(reader_task, timeout=1.0)
    return service, session, active_upstream, engine


@pytest.mark.asyncio
async def test_eventless_timeout_invalidates_proxy_injected_reattach_anchor(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    owner = _make_anchored_owner(
        request_id="req-proxy-anchored",
        previous_response_id="resp_injected",
        proxy_injected=True,
    )

    with caplog.at_level(logging.WARNING):
        service, session, _upstream, engine = await _run_watchdog_against_silent_upstream(
            monkeypatch,
            key_value="sid-proxy-anchored",
            owner=owner,
            latest_response_id="resp_injected",
        )
    try:
        assert await _durable_latest_response_id(service._durable_bridge, "sid-proxy-anchored") is None
        assert "http_bridge_event event=missing_response_created_anchor_invalidated" in caplog.text

        assert owner.event_queue is not None
        terminal_blocks = [
            block
            for block in await _drain_event_queue(owner.event_queue)
            if '"code":"upstream_request_timeout"' in block
        ]
        assert len(terminal_blocks) == 1
        assert "continuation anchor was dropped" in terminal_blocks[0]
        assert session.closed is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_eventless_timeout_preserves_client_supplied_previous_response_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _make_anchored_owner(
        request_id="req-client-anchored",
        previous_response_id="resp_client",
        proxy_injected=False,
    )

    service, _session, _upstream, engine = await _run_watchdog_against_silent_upstream(
        monkeypatch,
        key_value="sid-client-anchored",
        owner=owner,
        latest_response_id="resp_client",
    )
    try:
        assert await _durable_latest_response_id(service._durable_bridge, "sid-client-anchored") == "resp_client"
        assert owner.event_queue is not None
        terminal_blocks = [
            block
            for block in await _drain_event_queue(owner.event_queue)
            if '"code":"upstream_request_timeout"' in block
        ]
        assert len(terminal_blocks) == 1
        assert "continuation anchor was dropped" not in terminal_blocks[0]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_eventless_timeout_quarantines_bridge_instead_of_killing_streaming_sibling(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sibling = _make_streaming_sibling("resp-streaming-sibling")
    owner = _make_anchored_owner(
        request_id="req-quarantine-owner",
        previous_response_id="resp_injected_quarantine",
        proxy_injected=True,
    )

    with caplog.at_level(logging.WARNING):
        service, session, upstream, engine = await _run_watchdog_against_silent_upstream(
            monkeypatch,
            key_value="sid-quarantine",
            owner=owner,
            latest_response_id="resp_injected_quarantine",
            upstream=_SilentAfterSiblingOutputUpstream("resp-streaming-sibling"),
            sibling=sibling,
        )
    try:
        assert owner.event_queue is not None
        owner_terminal_blocks = [
            block
            for block in await _drain_event_queue(owner.event_queue)
            if '"code":"upstream_request_timeout"' in block
        ]
        assert len(owner_terminal_blocks) == 1

        # The streaming sibling keeps its stream: not failed, still pending, and
        # the socket is neither closed nor deregistered.
        assert sibling.failure_detail_override is None
        assert [state.request_id for state in session.pending_requests] == [sibling.request_id]
        assert session.closed is False
        assert upstream.closed is False
        assert service._http_bridge_sessions.get(session.key) is session

        # ...but nothing new may land on the poisoned websocket.
        assert session.upstream_control.reconnect_requested is True
        assert session.upstream_control.retire_after_drain is True
        assert session.queued_request_count == 1
        assert "http_bridge_event event=missing_response_created_timeout_quarantined" in caplog.text
        assert await _durable_latest_response_id(service._durable_bridge, "sid-quarantine") is None
    finally:
        for task in tuple(service._background_cleanup_tasks):
            task.cancel()
        await asyncio.gather(*service._background_cleanup_tasks, return_exceptions=True)
        await engine.dispose()


@pytest.mark.asyncio
async def test_invalidate_latest_response_id_is_guarded_by_exact_match() -> None:
    coordinator, engine = await _make_durable_coordinator()
    try:
        session_id = await _claim_durable_session(
            coordinator,
            key_value="sid-guard",
            latest_response_id="resp_current",
        )

        assert not await coordinator.invalidate_latest_response_id(
            session_id=session_id,
            response_id="resp_stale_other",
        )
        assert await _durable_latest_response_id(coordinator, "sid-guard") == "resp_current"

        assert await coordinator.invalidate_latest_response_id(
            session_id=session_id,
            response_id="resp_current",
        )
        assert await _durable_latest_response_id(coordinator, "sid-guard") is None

        assert not await coordinator.invalidate_latest_response_id(
            session_id=session_id,
            response_id="resp_current",
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reader_failure_request_log_keeps_request_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reader-driven failures pass api_key=None.

    The log row must fall back to the request's own key instead of losing
    attribution for every reader-path failure.
    """
    service = proxy_service.ProxyService(cast(Any, nullcontext()))
    write_request_log = AsyncMock()
    monkeypatch.setattr(service, "_write_request_log", write_request_log)

    api_key = proxy_service.ApiKeyData(
        id="key-attribution",
        name="attribution",
        key_prefix="sk-test",
        allowed_models=None,
        enforced_model=None,
        enforced_reasoning_effort=None,
        enforced_service_tier=None,
        expires_at=None,
        is_active=True,
        created_at=utcnow(),
        last_used_at=None,
    )
    request_state = _make_anchored_owner(
        request_id="req-attribution",
        previous_response_id="resp_any",
        proxy_injected=False,
    )
    request_state.api_key = api_key

    await service._fail_pending_websocket_requests(
        account=None,
        account_id_value="acc-attribution",
        pending_requests=deque([request_state]),
        pending_lock=anyio.Lock(),
        error_code="stream_idle_timeout",
        error_message="Upstream stream idle timeout",
        api_key=None,
        response_create_gate=None,
    )

    write_request_log.assert_awaited_once()
    assert write_request_log.await_args is not None
    assert write_request_log.await_args.kwargs["api_key"] is api_key
