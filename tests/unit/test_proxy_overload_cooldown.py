from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from app.core.balancer import (
    UPSTREAM_OVERLOAD_COOLDOWN_ERROR_CODE,
    AccountState,
    select_account,
)
from app.db.models import Account, AccountStatus
from app.modules.proxy import load_balancer as load_balancer_module
from app.modules.proxy._load_balancer.types import RuntimeState
from app.modules.proxy._service.support import _account_selection_recovery_sleep_seconds_from_message
from app.modules.proxy.load_balancer import LoadBalancer

pytestmark = pytest.mark.unit


def _account(account_id: str) -> Account:
    return Account(
        id=account_id,
        chatgpt_account_id=f"workspace-{account_id}",
        email=f"{account_id}@example.com",
        plan_type="plus",
        access_token_encrypted=b"access",
        refresh_token_encrypted=b"refresh",
        id_token_encrypted=b"id",
        last_refresh=datetime.now(UTC),
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )


def test_selector_skips_overload_cooldown_before_backoff_fallback() -> None:
    now = time.time()
    cooling = AccountState(
        "cooling",
        AccountStatus.ACTIVE,
        used_percent=0.0,
        overload_cooldown_until=now + 30.0,
    )
    healthy = AccountState("healthy", AccountStatus.ACTIVE, used_percent=50.0)

    result = select_account([cooling, healthy], now=now, routing_strategy="usage_weighted")

    assert result.account is healthy


def test_selector_does_not_use_an_overload_account_as_fallback() -> None:
    now = time.time()
    cooling = AccountState(
        "cooling",
        AccountStatus.ACTIVE,
        overload_cooldown_until=now + 30.0,
    )

    result = select_account([cooling], now=now, routing_strategy="single_account")

    assert result.account is None
    assert result.error_code == UPSTREAM_OVERLOAD_COOLDOWN_ERROR_CODE
    assert result.error_message == "Upstream accounts are overloaded. Try again in 30s"


def test_selector_reports_all_accounts_in_overload_cooldown_as_recoverable() -> None:
    now = time.time()
    cooling = AccountState(
        "cooling",
        AccountStatus.ACTIVE,
        overload_cooldown_until=now + 30.0,
    )

    result = select_account([cooling], now=now, routing_strategy="single_account")

    assert result.account is None
    assert result.error_code == UPSTREAM_OVERLOAD_COOLDOWN_ERROR_CODE
    assert result.error_message == "Upstream accounts are overloaded. Try again in 30s"


def test_selector_does_not_mask_generic_backoff_with_overload_cooldown() -> None:
    now = time.time()
    cooling = AccountState(
        "cooling",
        AccountStatus.ACTIVE,
        overload_cooldown_until=now + 30.0,
    )
    blocked = AccountState(
        "blocked",
        AccountStatus.ACTIVE,
        error_count=3,
        last_error_at=now,
    )

    result = select_account(
        [cooling, blocked],
        now=now,
        routing_strategy="single_account",
        allow_backoff_fallback=False,
    )

    assert result.account is None
    assert result.error_code is None
    assert result.error_message == "No available accounts"


def test_selector_preserves_generic_backoff_fallback_with_overload_cooldown() -> None:
    now = time.time()
    cooling = AccountState(
        "cooling",
        AccountStatus.ACTIVE,
        overload_cooldown_until=now + 30.0,
    )
    backoff_a = AccountState("backoff-a", AccountStatus.ACTIVE, error_count=3, last_error_at=now)
    backoff_b = AccountState("backoff-b", AccountStatus.ACTIVE, error_count=3, last_error_at=now)

    result = select_account(
        [cooling, backoff_a, backoff_b],
        now=now,
        routing_strategy="single_account",
    )

    assert result.account is backoff_a or result.account is backoff_b
    assert result.error_code is None


def test_overload_cooldown_selection_error_is_recoverable_without_a_message() -> None:
    assert (
        _account_selection_recovery_sleep_seconds_from_message(
            None,
            error_code=UPSTREAM_OVERLOAD_COOLDOWN_ERROR_CODE,
        )
        == 30.0
    )


def test_selector_probes_account_after_overload_cooldown_expires() -> None:
    now = time.time()
    cooling = AccountState(
        "recovering",
        AccountStatus.ACTIVE,
        overload_cooldown_until=now + 30.0,
    )

    result = select_account([cooling], now=now + 30.0, routing_strategy="single_account")

    assert result.account is cooling
    assert cooling.overload_cooldown_until is None


@pytest.mark.asyncio
async def test_record_overload_is_bounded_and_success_resistant(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 10_000.0
    monkeypatch.setattr(load_balancer_module.time, "time", lambda: now)
    balancer = LoadBalancer(lambda: pytest.fail("overload recording must not persist account state"))
    account = _account("overloaded")

    await balancer.record_overload(account)
    first_deadline = balancer._runtime[account.id].overload_cooldown_until
    assert first_deadline == now + 30.0

    await balancer.record_success(account)
    runtime = balancer._runtime[account.id]
    assert runtime.overload_cooldown_until == first_deadline
    assert runtime.overload_count == 1

    for count, delay in enumerate((60.0, 120.0, 240.0, 300.0, 300.0), start=2):
        now += 1.0
        await balancer.record_overload(account)
        runtime = balancer._runtime[account.id]
        assert runtime.overload_count == min(count, 5)
        assert runtime.overload_cooldown_until == now + delay

    assert account.status == AccountStatus.ACTIVE


@pytest.mark.asyncio
async def test_overload_retry_after_reports_expiry_without_clearing_hold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 20_000.0
    monkeypatch.setattr(load_balancer_module.time, "time", lambda: now)
    balancer = LoadBalancer(lambda: pytest.fail("retry lookup must not access repositories"))
    account = _account("retry-after")

    await balancer.record_overload(account)
    assert await balancer.overload_retry_after(account.id) == 30.0

    now += 31.0
    assert await balancer.overload_retry_after(account.id) == 0.0
    assert balancer._runtime[account.id].overload_cooldown_until == 20_030.0


def test_account_state_exposes_runtime_overload_cooldown() -> None:
    account = _account("state")
    balancer = LoadBalancer(lambda: pytest.fail("state construction must not access repositories"))
    deadline = time.time() + 30.0
    balancer._runtime[account.id] = RuntimeState(overload_cooldown_until=deadline)

    state = balancer._state_for(account)

    assert state.overload_cooldown_until == deadline


@pytest.mark.asyncio
async def test_recurrent_overload_escalates_after_expiry_and_success(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 30_000.0
    monkeypatch.setattr(load_balancer_module.time, "time", lambda: now)
    balancer = LoadBalancer(lambda: pytest.fail("overload history must not persist account state"))
    account = _account("recurrent")
    for delay in (30.0, 60.0, 120.0, 240.0, 300.0, 300.0):
        await balancer.record_overload(account)
        assert await balancer.overload_retry_after(account.id) == delay
        now += delay + 1
        # Selection can clear the expired eligibility deadline. Neither this
        # nor a success proves a recurring overload has recovered.
        state = balancer._state_for(account)
        assert select_account([state], now=now).account is state
        balancer._sync_runtime_state(account, state)
        await balancer.record_success(account)
    assert account.status == AccountStatus.ACTIVE


@pytest.mark.asyncio
async def test_overload_history_resets_after_quiet_window(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 40_000.0
    monkeypatch.setattr(load_balancer_module.time, "time", lambda: now)
    balancer = LoadBalancer(lambda: pytest.fail("overload history must not persist account state"))
    account = _account("quiet-recovery")
    await balancer.record_overload(account)
    now += 31
    await balancer.record_overload(account)
    assert await balancer.overload_retry_after(account.id) == 60
    now += 900
    await balancer.record_overload(account)
    assert await balancer.overload_retry_after(account.id) == 30
