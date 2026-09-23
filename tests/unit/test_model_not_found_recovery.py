from __future__ import annotations

import pytest

from app.core.types import JsonValue
from app.modules.proxy import service as proxy_service
from app.modules.proxy.helpers import _is_account_model_unsupported_error

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("model", ["gpt-6-sol", "gpt-6-luna"])
def test_canonical_model_not_found_is_account_rejection(model):
    assert _is_account_model_unsupported_error(
        code="model_not_found",
        message=f"  The model `{model}` does not exist or you do not\n have access to it. ",
        model=model,
    )


@pytest.mark.parametrize(
    ("code", "message", "model"),
    [
        ("model_not_found", "Unknown model", "gpt-6-sol"),
        ("model_not_found", "The model `gpt-6-luna` does not exist or you do not have access to it.", "gpt-6-sol"),
        ("invalid_request_error", "The model `gpt-6-sol` does not exist or you do not have access to it.", "gpt-6-sol"),
        ("model_not_found", None, "gpt-6-sol"),
        ("model_not_found", "The model `None` does not exist or you do not have access to it.", None),
    ],
)
def test_unrelated_rejections_do_not_trigger_account_recovery(code, message, model):
    assert not _is_account_model_unsupported_error(code=code, message=message, model=model)


@pytest.mark.parametrize("model", ["gpt-6-sol", "gpt-6-luna"])
def test_model_rejection_recovery_is_independent_of_generic_replay_budget(model):
    state = proxy_service._WebSocketRequestState(
        request_id="model-rejection-after-generic-replay",
        model=model,
        service_tier=None,
        reasoning_effort=None,
        api_key_reservation=None,
        started_at=0.0,
        awaiting_response_created=True,
        request_text='{"type":"response.create","input":"hello"}',
        replay_count=1,
    )
    for error, expected in [
        (
            {
                "code": "model_not_found",
                "message": f"The model `{model}` does not exist or you do not have access to it.",
            },
            "account_model_unsupported",
        ),
        ({"code": "stream_incomplete", "message": "Upstream stream closed prematurely"}, None),
    ]:
        assert (
            proxy_service._websocket_precreated_retry_error_code(
                state,
                event_type="error",
                payload={"type": "error", "error": error},
                has_other_pending_requests=False,
            )
            == expected
        )


@pytest.mark.parametrize("model", ["gpt-6-sol", "gpt-6-luna"])
@pytest.mark.parametrize("guard", ["accepted", "output", "response_id", "concurrent"])
def test_model_not_found_respects_existing_websocket_replay_guards(model, guard):
    state = proxy_service._WebSocketRequestState(
        request_id="model-not-found-guard",
        model=model,
        service_tier=None,
        reasoning_effort=None,
        api_key_reservation=None,
        started_at=0.0,
        awaiting_response_created=True,
        request_text='{"type":"response.create","input":"hello"}',
    )
    event: dict[str, JsonValue] = {
        "type": "error",
        "error": {
            "code": "model_not_found",
            "message": f"The model `{model}` does not exist or you do not have access to it.",
        },
    }
    if guard == "accepted":
        state.response_id = "resp_accepted"
        state.awaiting_response_created = False
    elif guard == "output":
        state.response_event_count = 1
    elif guard == "response_id":
        event["response_id"] = "resp_accepted"
    assert (
        proxy_service._websocket_precreated_retry_error_code(
            state,
            event_type="error",
            payload=event,
            has_other_pending_requests=guard == "concurrent",
        )
        is None
    )
