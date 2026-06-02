from __future__ import annotations

import base64
import hashlib
import urllib.parse
from contextlib import asynccontextmanager
from typing import Any, cast

import aiohttp
import pytest

import app.core.clients.oauth as oauth_client_module
from app.core.clients.oauth import OAuthTokens, build_authorization_url, exchange_device_token, pkce_challenge
from app.core.config.settings import get_settings

pytestmark = pytest.mark.unit


def test_pkce_challenge_matches_sha256():
    verifier = "test_verifier"
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    assert pkce_challenge(verifier) == expected


def test_build_authorization_url_contains_required_params():
    url = build_authorization_url(
        state="state_123",
        code_challenge="challenge_456",
        base_url="https://auth.openai.com",
        client_id="client_id",
        redirect_uri="http://localhost:1455/auth/callback",
        scope="openid profile email offline_access",
    )

    parsed = urllib.parse.urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "auth.openai.com"
    assert parsed.path == "/oauth/authorize"

    query = urllib.parse.parse_qs(parsed.query)
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["client_id"]
    assert query["redirect_uri"] == ["http://localhost:1455/auth/callback"]
    assert query["scope"] == ["openid profile email offline_access"]
    assert query["code_challenge"] == ["challenge_456"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"] == ["state_123"]
    assert query["id_token_add_organizations"] == ["true"]
    assert query["codex_cli_simplified_flow"] == ["true"]
    assert query["originator"] == ["codex_chatgpt_desktop"]


def test_build_authorization_url_uses_configured_originator(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CODEX_LB_OAUTH_ORIGINATOR", "codex_chatgpt_desktop")
    get_settings.cache_clear()

    try:
        url = build_authorization_url(
            state="state_123",
            code_challenge="challenge_456",
            base_url="https://auth.openai.com",
            client_id="client_id",
            redirect_uri="http://localhost:1455/auth/callback",
            scope="openid profile email offline_access",
        )
    finally:
        get_settings.cache_clear()

    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    assert query["originator"] == ["codex_chatgpt_desktop"]


def test_build_authorization_url_allows_cli_override(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CODEX_LB_OAUTH_ORIGINATOR", "codex_cli_rs")
    get_settings.cache_clear()

    try:
        url = build_authorization_url(
            state="state_123",
            code_challenge="challenge_456",
            base_url="https://auth.openai.com",
            client_id="client_id",
            redirect_uri="http://localhost:1455/auth/callback",
            scope="openid profile email offline_access",
        )
    finally:
        get_settings.cache_clear()

    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    assert query["originator"] == ["codex_cli_rs"]


@pytest.mark.asyncio
async def test_exchange_device_token_reuses_supplied_session_for_authorization_code(monkeypatch: pytest.MonkeyPatch):
    supplied_session = cast(aiohttp.ClientSession, object())
    seen: dict[str, Any] = {}

    class FakeResponse:
        status = 200

        async def json(self, *_, **__):
            return {
                "authorization_code": "device-authorization-code",
                "code_verifier": "device-code-verifier",
            }

    class FakePostContext:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeSession:
        def post(self, url: str, **kwargs):
            seen["device_url"] = url
            seen["device_kwargs"] = kwargs
            return FakePostContext()

    @asynccontextmanager
    async def fake_lease_http_session(session=None):
        seen["leased_session"] = session
        yield FakeSession()

    async def fake_exchange_authorization_code(**kwargs):
        seen["authorization_kwargs"] = kwargs
        return OAuthTokens("access-token", "refresh-token", "id-token")

    monkeypatch.setattr(oauth_client_module, "lease_http_session", fake_lease_http_session)
    monkeypatch.setattr(oauth_client_module, "exchange_authorization_code", fake_exchange_authorization_code)

    tokens = await exchange_device_token(
        device_auth_id="device-auth-id",
        user_code="USER-CODE",
        base_url="https://auth.example.test",
        timeout_seconds=12.0,
        session=supplied_session,
        allow_direct_egress=True,
    )

    assert tokens is not None
    assert tokens.access_token == "access-token"
    assert seen["leased_session"] is supplied_session
    authorization_kwargs = seen["authorization_kwargs"]
    assert authorization_kwargs["session"] is supplied_session
    assert authorization_kwargs["code"] == "device-authorization-code"
    assert authorization_kwargs["code_verifier"] == "device-code-verifier"
    assert authorization_kwargs["redirect_uri"] == "https://auth.example.test/deviceauth/callback"
