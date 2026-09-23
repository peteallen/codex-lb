from __future__ import annotations

import pytest

from app.core.types import JsonValue
from app.modules.proxy._service.websocket.helpers import _trim_websocket_previous_response_input_items

pytestmark = pytest.mark.unit


def test_mixed_replay_prefix_preserves_unconfirmed_calls_and_output_order() -> None:
    items: list[JsonValue] = [
        {"type": "reasoning", "summary": []},
        {"type": "function_call", "call_id": "upstream", "name": "shell", "arguments": "{}"},
        {"type": "function_call", "call_id": "visualization_state_local", "name": "state", "arguments": "{}"},
        {"type": "function_call_output", "call_id": "upstream", "output": "done"},
        {"type": "function_call_output", "call_id": "visualization_state_local", "output": "state"},
        {"role": "user", "content": "continue"},
    ]

    trimmed = _trim_websocket_previous_response_input_items(
        items, confirmed_tool_call_types={"upstream": "function_call"}
    )

    assert trimmed == items[2:]
    assert len(items) == 6


@pytest.mark.parametrize("call_id", [None, 42, "unknown"])
def test_call_without_matching_identity_is_preserved(call_id: JsonValue) -> None:
    items: list[JsonValue] = [
        {"type": "function_call", "call_id": call_id, "name": "state", "arguments": "{}"},
        {"type": "function_call_output", "call_id": "unknown", "output": "state"},
    ]

    assert (
        _trim_websocket_previous_response_input_items(items, confirmed_tool_call_types={"upstream": "function_call"})
        == items
    )
