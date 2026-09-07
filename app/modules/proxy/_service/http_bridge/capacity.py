"""Proof and progress guards for request-local capacity escape."""

from __future__ import annotations

import asyncio
from typing import cast

from app.core.clients.proxy import ProxyResponseError
from app.core.openai.requests import ResponsesRequest
from app.core.types import JsonValue
from app.modules.proxy._service.http_bridge.service_stubs import _input_prefix_matches_stored_context
from app.modules.proxy._service.support import _WebSocketRequestState
from app.modules.proxy.replay_safety import (
    responses_input_suffix_retains_prior_output,
    responses_payload_is_account_neutral_fresh_replay,
)


def capacity_release_event_for_error(
    events: tuple[asyncio.Event, asyncio.Event],
    exc: ProxyResponseError,
) -> asyncio.Event | None:
    error = exc.payload.get("error")
    if isinstance(error, dict) and error.get("code") in {
        "account_response_create_cap",
        "account_stream_cap",
        "response_create_gate_timeout",
    }:
        return events[1] if error.get("code") == "account_stream_cap" else events[0]
    return None


def request_is_unsent(state: _WebSocketRequestState) -> bool:
    return not (
        state.recovery_attempt_dispatched
        or state.response_create_sent_at is not None
        or state.response_id is not None
        or state.response_event_count
        or state.latency_response_created_ms is not None
        or state.downstream_visible
        or state.last_downstream_sequence_number is not None
        or state.replay_count
    )


def original_request_can_escape_capacity(
    payload: ResponsesRequest,
    state: _WebSocketRequestState,
    *,
    client_turn_state: str | None,
    forwarded: bool,
    file_owner_required: bool,
    stored_input_count: int = 0,
    stored_input_fingerprint: str | None = None,
) -> bool:
    if (
        forwarded
        or client_turn_state is not None
        or file_owner_required
        or state.require_security_work_authorized
        or not request_is_unsent(state)
    ):
        return False
    if state.previous_response_id is not None and not (
        state.proxy_injected_previous_response_id and state.fresh_upstream_request_is_retry_safe
    ):
        return False
    if stored_input_count > 0 and not (
        isinstance(payload.input, list)
        and _input_prefix_matches_stored_context(
            payload.input,
            stored_count=stored_input_count,
            stored_fingerprint=stored_input_fingerprint,
        )
        and responses_input_suffix_retains_prior_output(
            cast(list[JsonValue], payload.input),
            stored_count=stored_input_count,
        )
    ):
        return False
    # Validates tool-call pairing and rejects opaque response/file/prompt state.
    # The injected-anchor case additionally requires the existing prefix proof.
    return responses_payload_is_account_neutral_fresh_replay(payload.to_replay_safety_payload())
