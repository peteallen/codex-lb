"""Prepare explicit rejected WebSocket work for deadline-bound reselection."""

from __future__ import annotations

import asyncio

from app.core.balancer.types import UpstreamError
from app.db.models import Account
from app.modules.proxy._service.support import (
    _clear_websocket_request_error_overrides,
    _WebSocketRequestState,
    overload_replay_is_account_neutral,
)
from app.modules.proxy._service.websocket.helpers import (
    _prepare_websocket_request_state_for_account_switch,
    _release_websocket_response_create_gate,
)
from app.modules.proxy._service.websocket.protocol import _WebSocketServiceProtocol
from app.modules.proxy.affinity import _AffinityPolicy


async def prepare_overload_recovery(
    proxy: _WebSocketServiceProtocol,
    account: Account,
    request_state: _WebSocketRequestState,
    response_create_gate: asyncio.Semaphore,
    *,
    error: UpstreamError | None = None,
    error_code: str = "server_is_overloaded",
) -> None:
    """Caller must first prove this terminal error preceded upstream acceptance."""
    if error is None:
        await proxy._load_balancer.record_overload(account)
    else:
        # Keep the normal failure hook in the recovery path. It owns the
        # account-runtime classification (including the independent overload
        # cooldown) and keeps request logs/health accounting consistent with
        # other first-event failures.
        await proxy._handle_stream_error(account, error, error_code)
    await _release_websocket_response_create_gate(request_state, response_create_gate)
    if overload_replay_is_account_neutral(request_state):
        replay_text = _prepare_websocket_request_state_for_account_switch(request_state)
        request_state.request_text = replay_text
        request_state.preferred_account_id = None
        request_state.affinity_policy = _AffinityPolicy()
    else:
        request_state.preferred_account_id = account.id
    request_state.overload_recovery_count += 1
    request_state.overload_recovery_pending = True
    request_state.awaiting_response_created = True
    request_state.response_id = None
    request_state.response_event_count = 0
    _clear_websocket_request_error_overrides(request_state)
