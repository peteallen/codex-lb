from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.clients.proxy import ProxyResponseError
from app.core.config.settings import Settings
from app.core.errors import openai_error
from app.core.openai.requests import ResponsesRequest
from app.modules.proxy import service as proxy
from app.modules.proxy._service.http_bridge.capacity import (
    capacity_release_event_for_error,
    original_request_can_escape_capacity,
)
from app.modules.proxy._service.http_bridge.streaming import _iter_account_capacity_wait_sse
from app.modules.proxy._service.support import _record_response_event

pytestmark = pytest.mark.unit


def state(**kwargs):
    return proxy._WebSocketRequestState(
        request_id="capacity-test",
        model="gpt-5.1",
        service_tier=None,
        reasoning_effort=None,
        api_key_reservation=None,
        started_at=0.0,
        **kwargs,
    )


@pytest.fixture
def service(monkeypatch):
    settings = Settings(proxy_response_create_limit=1, proxy_admission_wait_timeout_seconds=5.0)
    monkeypatch.setattr(proxy, "get_settings", lambda: settings)
    monkeypatch.setattr(proxy, "get_settings_cache", lambda: SimpleNamespace(get=AsyncMock(return_value=settings)))
    return proxy.ProxyService(AsyncMock())


@pytest.mark.asyncio
async def test_three_gate_waiters_leave_account_startup_capacity_available(service):
    gate = asyncio.Semaphore(0)
    states = [state() for _ in range(3)]
    tasks = [
        asyncio.create_task(
            service._acquire_request_state_response_create_admission(
                item,
                response_create_gate=gate,
                account_id="warm",
                surface="http_bridge",
            )
        )
        for item in states
    ]
    try:
        for _ in range(20):
            await asyncio.sleep(0)
            if all(item.response_create_gate_wait_started_at is not None for item in states):
                break
        assert all(item.response_create_gate_wait_started_at is not None for item in states)
        assert await service._load_balancer.account_pressure_snapshot("warm") == (0, 0, 0.0)
        unrelated = state()
        other_gate = asyncio.Semaphore(1)
        await service._acquire_request_state_response_create_admission(
            unrelated,
            response_create_gate=other_gate,
            account_id="warm",
            surface="http_bridge",
        )
        assert await service._load_balancer.account_pressure_snapshot("warm") == (1, 0, 0.0)
        await proxy._release_websocket_response_create_gate(unrelated, other_gate)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert gate.locked()
    assert all(item.account_response_create_lease is None for item in states)
    assert await service._load_balancer.account_pressure_snapshot("warm") == (0, 0, 0.0)


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["account_lookup", "global_admission"])
async def test_cancel_after_gate_acquisition_releases_owned_resources(service, monkeypatch, phase):
    gate = asyncio.Semaphore(1)
    request = state()
    reached = asyncio.Event()

    async def blocked(*args, **kwargs):
        reached.set()
        await asyncio.Event().wait()

    if phase == "account_lookup":
        monkeypatch.setattr(service, "_acquire_account_response_create_lease_or_overload", blocked)
    else:
        monkeypatch.setattr(service._get_work_admission(), "acquire_response_create", blocked)
    task = asyncio.create_task(
        service._acquire_request_state_response_create_admission(
            request,
            response_create_gate=gate,
            account_id="warm",
        )
    )
    await asyncio.wait_for(reached.wait(), 1)
    assert gate.locked()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not gate.locked()
    assert request.account_response_create_lease is None
    assert request.response_create_admission is None
    assert await service._load_balancer.account_pressure_snapshot("warm") == (0, 0, 0.0)


@pytest.mark.asyncio
async def test_account_cap_after_gate_acquisition_releases_gate(service, monkeypatch):
    gate = asyncio.Semaphore(1)
    request = state()
    monkeypatch.setattr(
        service,
        "_acquire_account_response_create_lease_or_overload",
        AsyncMock(
            side_effect=ProxyResponseError(429, openai_error("account_response_create_cap", "At capacity")),
        ),
    )
    with pytest.raises(ProxyResponseError):
        await service._acquire_request_state_response_create_admission(
            request, response_create_gate=gate, account_id="warm"
        )
    assert not gate.locked()
    assert request.account_response_create_lease is None


@pytest.mark.asyncio
async def test_capacity_release_wakes_competing_waiters_and_preserves_caps(service):
    lb = service._load_balancer
    caps = proxy.AccountConcurrencyCaps(response_create_limit=1, stream_limit=1)
    held = await lb.acquire_account_lease("warm", kind="response_create", concurrency_caps=caps)
    released = lb.capacity_release_events[0]
    waiting = asyncio.Event()

    async def wait_and_acquire():
        waiting.set()
        async for _ in _iter_account_capacity_wait_sse(
            request_id="wait",
            reason="capacity",
            sleep_seconds=30,
            emit_keepalives=False,
            capacity_release_event=released,
        ):
            pass
        return await lb.acquire_account_lease("warm", kind="response_create", concurrency_caps=caps)

    tasks = [asyncio.create_task(wait_and_acquire()) for _ in range(2)]
    await waiting.wait()
    await lb.release_account_lease(held)
    leases = await asyncio.wait_for(asyncio.gather(*tasks), 1)
    assert sum(lease is not None for lease in leases) == 1
    next_release = lb.capacity_release_events[0]
    await lb.release_account_lease(held)  # Duplicate releases cannot wake a new generation.
    assert not next_release.is_set()
    for lease in leases:
        await lb.release_account_lease(lease)
    assert next_release.is_set()
    quota_error = ProxyResponseError(429, openai_error("rate_limit_exceeded", "Try again in 30s"))
    assert capacity_release_event_for_error(lb.capacity_release_events, quota_error) is None


@pytest.mark.asyncio
async def test_capacity_wait_cancellation_does_not_consume_release(service):
    release = service._load_balancer.capacity_release_events[0]
    wait = _iter_account_capacity_wait_sse(
        request_id="cancel",
        reason="capacity",
        sleep_seconds=30,
        emit_keepalives=False,
        capacity_release_event=release,
    )
    task = asyncio.ensure_future(anext(wait))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not release.is_set()
    assert not release._waiters


@pytest.mark.parametrize(
    "guard",
    [
        "client_anchor",
        "conversation",
        "file",
        "item_reference",
        "turn_state",
        "file_owner",
        "forwarded",
        "delta",
        "missing_prior_output",
        "sent",
        "ambiguous_send",
        "events",
        "visible",
        "security",
    ],
)
def test_capacity_escape_rejects_owner_bound_incomplete_or_dispatched_requests(guard):
    payload = ResponsesRequest(
        model="gpt-5.1",
        instructions="Continue the conversation.",
        input=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "continue"},
        ],
    )
    request = state(
        previous_response_id="injected",
        proxy_injected_previous_response_id=True,
        fresh_upstream_request_is_retry_safe=True,
    )
    if guard == "client_anchor":
        payload.previous_response_id = "client-owned"
    elif guard == "conversation":
        payload.conversation = "conv-owned"
    elif guard == "file":
        payload.input = [{"role": "user", "content": [{"type": "input_file", "file_id": "file-owned"}]}]
    elif guard == "item_reference":
        payload.input = [{"type": "item_reference", "id": "msg-owned"}]
    elif guard == "delta":
        request.fresh_upstream_request_is_retry_safe = False
    elif guard == "missing_prior_output":
        payload.input = [{"role": "user", "content": "hello"}, {"role": "user", "content": "continue"}]
    elif guard == "sent":
        request.response_create_sent_at = 1.0
    elif guard == "ambiguous_send":
        request.recovery_attempt_dispatched = True
    elif guard == "events":
        _record_response_event(request, "response.output_text.delta")
    elif guard == "visible":
        request.downstream_visible = True
    elif guard == "security":
        request.require_security_work_authorized = True
    assert not original_request_can_escape_capacity(
        payload,
        request,
        client_turn_state="owner" if guard == "turn_state" else None,
        forwarded=guard == "forwarded",
        file_owner_required=guard == "file_owner",
        stored_input_count=1,
        stored_input_fingerprint=proxy._fingerprint_input_items([{"role": "user", "content": "hello"}]),
    )


def test_original_proven_full_context_retains_capacity_mobility():
    payload = ResponsesRequest(
        model="gpt-5.1",
        instructions="Continue",
        input=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "continue"},
        ],
    )
    assert original_request_can_escape_capacity(
        payload,
        state(
            previous_response_id="injected",
            proxy_injected_previous_response_id=True,
            fresh_upstream_request_is_retry_safe=True,
        ),
        client_turn_state=None,
        forwarded=False,
        file_owner_required=False,
        stored_input_count=1,
        stored_input_fingerprint=proxy._fingerprint_input_items([{"role": "user", "content": "hello"}]),
    )


def test_protocol_progress_records_only_known_bounded_event_types():
    request = state()
    _record_response_event(request, "response.output_text.delta")
    assert request.last_response_event_type == "response.output_text.delta"
    _record_response_event(request, "response." + "private-body-content" * 1000)
    assert request.last_response_event_type == "response.other"
    assert request.response_event_count == 2
