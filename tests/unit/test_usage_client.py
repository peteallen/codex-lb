from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import pytest

from app.core.clients.usage import UsageFetchError, consume_rate_limit_reset_credit, fetch_usage
from app.core.upstream_proxy import ResolvedProxyEndpoint, ResolvedUpstreamRoute

pytestmark = pytest.mark.unit


class StubResponse:
    def __init__(self, status: int, payload: dict | None, text: str) -> None:
        self.status = status
        self._payload = payload
        self._text = text
        self.headers: dict[str, str] = {}
        self.method = "GET"
        self.closed = False

    def close(self) -> None:
        self.closed = True

    async def json(self, content_type: str | None = None) -> dict:
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    async def text(self) -> str:
        return self._text


@dataclass
class UsageClientState:
    calls: int = 0
    method: str | None = None
    url: str | None = None
    auth: str | None = None
    account: str | None = None
    payload: dict[str, str] | None = None


class StubRequestContext:
    def __init__(
        self,
        responses: list[StubResponse],
        state: UsageClientState,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, str] | None,
        retry_options: object | None,
    ) -> None:
        self._responses = responses
        self._state = state
        self._method = method
        self._url = url
        self._headers = headers
        self._payload = payload
        self._retry_options = retry_options

    async def __aenter__(self) -> StubResponse:
        attempts = getattr(self._retry_options, "attempts", 1)
        statuses = set(getattr(self._retry_options, "statuses", set()))
        response: StubResponse | None = None
        for attempt in range(attempts):
            index = min(self._state.calls, len(self._responses) - 1)
            response = self._responses[index]
            self._state.calls += 1
            self._state.method = self._method
            self._state.url = self._url
            self._state.auth = self._headers.get("Authorization")
            self._state.account = self._headers.get("chatgpt-account-id")
            self._state.payload = self._payload
            if response.status in statuses and attempt < attempts - 1:
                continue
            return response
        if response is None:
            response = StubResponse(500, None, "no response")
        return response

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class StubRetryClient:
    def __init__(self, responses: list[StubResponse], state: UsageClientState) -> None:
        self._responses = responses
        self._state = state

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json: dict[str, str] | None = None,
        timeout: object | None = None,
        retry_options: object | None = None,
    ) -> StubRequestContext:
        return StubRequestContext(self._responses, self._state, method, url, headers or {}, json, retry_options)


class StubCodexResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers: dict[str, str] = {}

    def json(self) -> dict:
        return self._payload or {
            "plan_type": "plus",
            "rate_limit": {
                "primary_window": {
                    "used_percent": 12.5,
                    "reset_at": 1735689600,
                    "limit_window_seconds": 60,
                    "reset_after_seconds": 30,
                }
            },
        }


class StubCodexClient:
    def __init__(self, responses: list[StubCodexResponse] | None = None) -> None:
        self._responses = responses or [StubCodexResponse()]
        self.calls: list[dict[str, object]] = []

    async def request(self, method: str, url: str, *, route: ResolvedUpstreamRoute, **kwargs: object) -> object:
        self.calls.append({"method": method, "url": url, "route": route, **kwargs})
        index = min(len(self.calls) - 1, len(self._responses) - 1)
        return self._responses[index]


@pytest.fixture
def usage_server() -> tuple[str, StubRetryClient, UsageClientState]:
    state = UsageClientState()
    responses = [
        StubResponse(503, None, "busy"),
        StubResponse(
            200,
            {
                "plan_type": "plus",
                "rate_limit": {
                    "primary_window": {
                        "used_percent": 12.5,
                        "reset_at": 1735689600,
                        "limit_window_seconds": 60,
                        "reset_after_seconds": 30,
                    }
                },
            },
            "",
        ),
    ]
    client = StubRetryClient(responses, state)
    return "http://usage.test/backend-api", client, state


@pytest.fixture
def failing_usage_server() -> tuple[str, StubRetryClient]:
    state = UsageClientState()
    responses = [StubResponse(503, None, "busy")]
    client = StubRetryClient(responses, state)
    return "http://usage.test/backend-api", client


@pytest.mark.asyncio
async def test_fetch_usage_retries_and_returns_payload(usage_server):
    base_url, client, state = usage_server
    data = await fetch_usage(
        access_token="access-token",
        account_id="acc_test",
        base_url=base_url,
        max_retries=1,
        timeout_seconds=2.0,
        client=cast(Any, client),
        allow_direct_egress=True,
    )
    assert data.plan_type == "plus"
    assert state.calls == 2
    assert state.auth == "Bearer access-token"
    assert state.account == "acc_test"


@pytest.mark.asyncio
async def test_fetch_usage_uses_resolved_codex_route() -> None:
    route = ResolvedUpstreamRoute(
        mode="account_bound",
        pool_id="pool_1",
        endpoint=ResolvedProxyEndpoint("ep_1", "http", "proxy.test", 8080),
    )
    client = StubCodexClient()

    data = await fetch_usage(
        access_token="access-token",
        account_id="acc_test",
        base_url="http://usage.test/backend-api",
        timeout_seconds=2.0,
        route=route,
        codex_client=cast(Any, client),
        allow_direct_egress=True,
    )

    assert data.plan_type == "plus"
    assert client.calls[0]["route"] is route
    assert client.calls[0]["method"] == "GET"
    assert client.calls[0]["url"] == "http://usage.test/backend-api/wham/usage"


@pytest.mark.asyncio
async def test_consume_rate_limit_reset_credit_posts_payload_direct() -> None:
    state = UsageClientState()
    client = StubRetryClient(
        [StubResponse(200, {"code": "reset", "windows_reset": 2}, "")],
        state,
    )

    data = await consume_rate_limit_reset_credit(
        access_token="access-token",
        account_id="acc_test",
        redeem_request_id="redeem-123",
        base_url="http://usage.test",
        max_retries=0,
        timeout_seconds=1.0,
        client=cast(Any, client),
        allow_direct_egress=True,
    )

    assert data.code == "reset"
    assert data.windows_reset == 2
    assert state.calls == 1
    assert state.method == "POST"
    assert state.url == "http://usage.test/backend-api/wham/rate-limit-reset-credits/consume"
    assert state.auth == "Bearer access-token"
    assert state.account == "acc_test"
    assert state.payload == {"redeem_request_id": "redeem-123"}


@pytest.mark.asyncio
async def test_consume_rate_limit_reset_credit_uses_resolved_codex_route() -> None:
    route = ResolvedUpstreamRoute(
        mode="account_bound",
        pool_id="pool_1",
        endpoint=ResolvedProxyEndpoint("ep_1", "http", "proxy.test", 8080),
    )
    client = StubCodexClient(
        [
            StubCodexResponse(
                200,
                {"code": "already_redeemed", "windows_reset": 0},
            )
        ]
    )

    data = await consume_rate_limit_reset_credit(
        access_token="access-token",
        account_id="acc_test",
        redeem_request_id="redeem-123",
        base_url="http://usage.test/backend-api",
        max_retries=0,
        timeout_seconds=1.0,
        route=route,
        codex_client=cast(Any, client),
    )

    assert data.code == "already_redeemed"
    assert client.calls[0]["route"] is route
    assert client.calls[0]["method"] == "POST"
    assert client.calls[0]["url"] == "http://usage.test/backend-api/wham/rate-limit-reset-credits/consume"
    assert client.calls[0]["json"] == {"redeem_request_id": "redeem-123"}


@pytest.mark.asyncio
async def test_fetch_usage_retries_resolved_codex_route_retryable_status(monkeypatch) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("app.core.clients.usage.asyncio.sleep", no_sleep)
    route = ResolvedUpstreamRoute(
        mode="account_bound",
        pool_id="pool_1",
        endpoint=ResolvedProxyEndpoint("ep_1", "http", "proxy.test", 8080),
    )
    client = StubCodexClient(
        [
            StubCodexResponse(503, {"error": {"message": "busy"}}),
            StubCodexResponse(),
        ]
    )

    data = await fetch_usage(
        access_token="access-token",
        account_id="acc_test",
        base_url="http://usage.test/backend-api",
        max_retries=1,
        timeout_seconds=2.0,
        route=route,
        codex_client=cast(Any, client),
        allow_direct_egress=True,
    )

    assert data.plan_type == "plus"
    assert len(client.calls) == 2
    assert client.calls[0]["route"] is route
    assert client.calls[1]["route"] is route


@pytest.mark.asyncio
async def test_fetch_usage_raises_after_retries(failing_usage_server):
    base_url, client = failing_usage_server
    with pytest.raises(UsageFetchError) as excinfo:
        await fetch_usage(
            access_token="access-token",
            account_id=None,
            base_url=base_url,
            max_retries=0,
            timeout_seconds=1.0,
            client=cast(Any, client),
            allow_direct_egress=True,
        )
    exc = excinfo.value
    assert isinstance(exc, UsageFetchError)
    assert exc.status_code == 503


@pytest.mark.asyncio
async def test_fetch_usage_preserves_error_code():
    state = UsageClientState()
    responses = [
        StubResponse(
            401,
            {
                "error": {
                    "code": "account_deactivated",
                    "message": "Your OpenAI account has been deactivated.",
                }
            },
            "",
        )
    ]
    client = StubRetryClient(responses, state)

    with pytest.raises(UsageFetchError) as excinfo:
        await fetch_usage(
            access_token="access-token",
            account_id=None,
            base_url="http://usage.test/backend-api",
            max_retries=0,
            timeout_seconds=1.0,
            client=cast(Any, client),
            allow_direct_egress=True,
        )

    exc = excinfo.value
    assert exc.status_code == 401
    assert exc.code == "account_deactivated"
    assert "deactivated" in exc.message.lower()


@pytest.mark.parametrize("routed", [False, True])
@pytest.mark.parametrize("consume", [False, True])
@pytest.mark.parametrize("retry_after", ["60", "future_date", "nonsense", "-1", "nan", None])
@pytest.mark.asyncio
async def test_usage_requests_honor_retry_after(monkeypatch, routed, consume, retry_after):
    import time
    from email.utils import formatdate

    from aiohttp_retry import RetryClient

    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("app.core.clients.usage.asyncio.sleep", record_sleep)
    header = formatdate(time.time() + 60, usegmt=True) if retry_after == "future_date" else retry_after
    success = {"code": "reset", "windows_reset": 1} if consume else {"plan_type": "plus"}
    route = ResolvedUpstreamRoute(
        mode="account_bound",
        pool_id="pool_1",
        endpoint=ResolvedProxyEndpoint("ep_1", "http", "proxy.test", 8080),
    )
    direct_responses = [StubResponse(429, {}, ""), StubResponse(200, success, "")]
    codex_responses = [StubCodexResponse(429, {}), StubCodexResponse(200, success)]
    for response in [*direct_responses[:1], *codex_responses[:1]]:
        if header is not None:
            response.headers["retry-after"] = header
    calls = 0

    class StubSession:
        closed = False

        async def request(self, method, url, **kwargs):
            nonlocal calls
            response = direct_responses[min(calls, 1)]
            response.method = method
            calls += 1
            return response

        async def close(self):
            self.closed = True

    # Exercise aiohttp-retry's real loop against an in-memory upstream session.
    client = RetryClient(client_session=cast(Any, StubSession()))
    codex_client = StubCodexClient(codex_responses)
    selected_route = route if routed else None
    selected_codex_client = cast(Any, codex_client)
    try:
        if consume:
            result = await consume_rate_limit_reset_credit(
                access_token="test-token",
                account_id="test-account",
                redeem_request_id="test-redeem",
                max_retries=1,
                base_url="http://usage.test",
                client=client,
                route=selected_route,
                codex_client=selected_codex_client,
                allow_direct_egress=True,
            )
            assert result.code == "reset"
        else:
            result = await fetch_usage(
                access_token="test-token",
                account_id="test-account",
                max_retries=1,
                base_url="http://usage.test",
                client=client,
                route=selected_route,
                codex_client=selected_codex_client,
                allow_direct_egress=True,
            )
            assert result.plan_type == "plus"
    finally:
        await client.close()

    assert (len(codex_client.calls) if routed else calls) == 2
    assert len(delays) == 1
    if retry_after == "60":
        assert delays[0] == 60
    elif retry_after == "future_date":
        assert 58 <= delays[0] <= 60
    else:
        assert delays[0] == (0.5 if routed else 1.0)


@pytest.mark.parametrize("routed", [False, True])
@pytest.mark.asyncio
async def test_usage_retry_after_wait_is_cancellable(monkeypatch, routed):
    import asyncio

    from aiohttp_retry import RetryClient

    calls = 0

    async def cancel_wait(delay):
        assert delay == 60
        raise asyncio.CancelledError

    monkeypatch.setattr("app.core.clients.usage.asyncio.sleep", cancel_wait)
    response = StubResponse(503, {}, "")
    response.headers["Retry-After"] = "60"

    class StubSession:
        closed = False

        async def request(self, method, url, **kwargs):
            nonlocal calls
            calls += 1
            return response

        async def close(self):
            self.closed = True

    codex_response = StubCodexResponse(503, {})
    codex_response.headers["Retry-After"] = "60"
    codex_client = StubCodexClient([codex_response])
    route = ResolvedUpstreamRoute(
        mode="account_bound",
        pool_id="pool_1",
        endpoint=ResolvedProxyEndpoint("ep_1", "http", "proxy.test", 8080),
    )
    client = RetryClient(client_session=cast(Any, StubSession()))
    try:
        with pytest.raises(asyncio.CancelledError):
            await fetch_usage(
                access_token="test",
                account_id="test",
                max_retries=1,
                client=client,
                route=route if routed else None,
                codex_client=cast(Any, codex_client),
                allow_direct_egress=True,
            )
    finally:
        await client.close()
    assert (len(codex_client.calls) if routed else calls) == 1


@pytest.mark.parametrize("routed", [False, True])
@pytest.mark.parametrize("consume", [False, True])
@pytest.mark.asyncio
async def test_usage_final_error_preserves_retry_after(routed, consume):
    response = StubResponse(503, {"error": {"message": "busy"}}, "")
    response.headers["retry-after"] = "60"
    codex_response = StubCodexResponse(503, {"error": {"message": "busy"}})
    codex_response.headers["retry-after"] = "60"
    route = ResolvedUpstreamRoute(
        mode="account_bound",
        pool_id="pool_1",
        endpoint=ResolvedProxyEndpoint("ep_1", "http", "proxy.test", 8080),
    )
    selected_route = route if routed else None
    client = cast(Any, StubRetryClient([response], UsageClientState()))
    codex_client = cast(Any, StubCodexClient([codex_response]))
    with pytest.raises(UsageFetchError) as caught:
        if consume:
            await consume_rate_limit_reset_credit(
                access_token="test",
                account_id="test",
                redeem_request_id="test",
                max_retries=0,
                client=client,
                route=selected_route,
                codex_client=codex_client,
                allow_direct_egress=True,
            )
        else:
            await fetch_usage(
                access_token="test",
                account_id="test",
                max_retries=0,
                client=client,
                route=selected_route,
                codex_client=codex_client,
                allow_direct_egress=True,
            )
    assert caught.value.status_code == 503
    assert caught.value.retry_after_seconds == 60
