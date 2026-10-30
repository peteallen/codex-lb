from __future__ import annotations

from datetime import datetime

from cryptography.fernet import Fernet

from app.core.crypto import TokenEncryptor
from app.db.models import Account, AccountStatus, UsageHistory
from app.modules.accounts import mappers
from app.modules.accounts.mappers import (
    _effective_status_from_usage,
    _latest_usage_recorded_at,
    _normalize_account_routing_policy,
)


def _usage(
    *,
    recorded_at: datetime,
    credits_has: bool,
    credits_balance: float,
) -> UsageHistory:
    return UsageHistory(
        account_id="acc",
        recorded_at=recorded_at,
        window="secondary",
        used_percent=100.0,
        credits_has=credits_has,
        credits_unlimited=False,
        credits_balance=credits_balance,
    )


def test_extract_credit_status_uses_freshest_sample() -> None:
    stale = _usage(
        recorded_at=datetime(2026, 1, 1, 12, 0, 0),
        credits_has=True,
        credits_balance=10.0,
    )
    fresh = _usage(
        recorded_at=datetime(2026, 1, 1, 12, 1, 0),
        credits_has=False,
        credits_balance=0.0,
    )

    assert mappers._extract_credit_status(stale, fresh) == (False, False, 0.0)


def test_latest_usage_recorded_at_uses_newest_loaded_sample() -> None:
    primary = _primary_usage(recorded_at=datetime(2026, 1, 1, 12, 0, 0))
    secondary = _secondary_usage(recorded_at=datetime(2026, 1, 1, 12, 2, 0))
    monthly = UsageHistory(
        account_id="account-1",
        window="monthly",
        used_percent=20.0,
        recorded_at=datetime(2026, 1, 1, 12, 1, 0),
    )

    assert _latest_usage_recorded_at(primary, secondary, monthly) == secondary.recorded_at
    assert _latest_usage_recorded_at(None, None, None) is None


def test_account_summary_preserves_promax_monthly_usage_with_unknown_credits() -> None:
    account = _account(AccountStatus.ACTIVE)
    account.plan_type = "promax"
    monthly = UsageHistory(
        account_id=account.id,
        window="monthly",
        used_percent=25.0,
        reset_at=1_900_000_000,
        window_minutes=43_200,
        recorded_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    summary = mappers._account_to_summary(
        account,
        None,
        None,
        monthly,
        None,
        None,
        None,
        TokenEncryptor(key=Fernet.generate_key()),
        include_auth=False,
    )

    assert summary.usage is not None
    assert summary.usage.monthly_remaining_percent == 75.0
    assert summary.reset_at_monthly is not None
    assert summary.window_minutes_monthly == 43_200
    assert summary.capacity_credits_monthly is None
    assert summary.remaining_credits_monthly is None


def test_account_summary_omits_primary_no_data_marker() -> None:
    account = _account(AccountStatus.ACTIVE)
    account.plan_type = "promax"
    marker = UsageHistory(
        account_id=account.id,
        window="primary",
        used_percent=0.0,
        reset_at=None,
        window_minutes=0,
        recorded_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    secondary = _secondary_usage(used_percent=25.0, reset_at=1_900_000_000)

    summary = mappers._account_to_summary(
        account,
        marker,
        secondary,
        None,
        None,
        None,
        None,
        TokenEncryptor(key=Fernet.generate_key()),
        include_auth=False,
    )

    assert summary.usage is not None
    assert summary.usage.primary_remaining_percent is None
    assert summary.usage.secondary_remaining_percent == 75.0
    assert summary.window_minutes_primary is None


def test_account_summary_preserves_incomplete_measured_primary_usage() -> None:
    account = _account(AccountStatus.ACTIVE)
    primary = _primary_usage(used_percent=100.0, reset_at=None, window_minutes=None)

    summary = mappers._account_to_summary(
        account,
        primary,
        None,
        None,
        None,
        None,
        None,
        TokenEncryptor(key=Fernet.generate_key()),
        include_auth=False,
    )

    assert summary.usage is not None
    assert summary.usage.primary_remaining_percent == 0.0
    assert summary.capacity_credits_primary == 225.0
    assert summary.remaining_credits_primary == 0.0


def _account(status: AccountStatus = AccountStatus.QUOTA_EXCEEDED) -> Account:
    return Account(
        id="account-1",
        email="account@example.com",
        plan_type="plus",
        access_token_encrypted=b"",
        refresh_token_encrypted=b"",
        id_token_encrypted=b"",
        status=status,
        reset_at=1_700_003_600,
    )


def _primary_usage(**overrides) -> UsageHistory:
    values = {
        "account_id": "account-1",
        "window": "primary",
        "used_percent": 40.0,
        "reset_at": None,
        "window_minutes": 300,
    }
    values.update(overrides)
    return UsageHistory(**values)


def _secondary_usage(**overrides) -> UsageHistory:
    values = {
        "account_id": "account-1",
        "window": "secondary",
        "used_percent": 100.0,
        "reset_at": 1_700_003_600,
        "window_minutes": 10080,
    }
    values.update(overrides)
    return UsageHistory(**values)


def test_effective_status_uses_secondary_credits_to_reactivate_quota_exceeded_account() -> None:
    account = _account()
    primary = _primary_usage()
    secondary = _secondary_usage(
        credits_has=False,
        credits_unlimited=False,
        credits_balance=25.0,
    )

    assert (
        _effective_status_from_usage(
            account,
            status_seed=account.status,
            primary_usage=primary,
            primary_used_percent=primary.used_percent,
            secondary_usage=secondary,
            secondary_used_percent=secondary.used_percent,
            monthly_usage=None,
            monthly_used_percent=None,
            runtime_reset=float(account.reset_at) if account.reset_at else None,
        )
        == AccountStatus.ACTIVE
    )


def test_effective_status_uses_primary_credits_when_secondary_has_no_credit_fields() -> None:
    account = _account()
    primary = _primary_usage(credits_balance=25.0)
    secondary = _secondary_usage()

    assert (
        _effective_status_from_usage(
            account,
            status_seed=account.status,
            primary_usage=primary,
            primary_used_percent=primary.used_percent,
            secondary_usage=secondary,
            secondary_used_percent=secondary.used_percent,
            monthly_usage=None,
            monthly_used_percent=None,
            runtime_reset=float(account.reset_at) if account.reset_at else None,
        )
        == AccountStatus.ACTIVE
    )


def test_effective_status_keeps_primary_exhaustion_rate_limited_with_credits() -> None:
    account = _account(AccountStatus.ACTIVE)
    primary = _primary_usage(used_percent=100.0, reset_at=1_700_000_300, credits_balance=25.0)
    secondary = _secondary_usage(used_percent=100.0, credits_balance=25.0)

    assert (
        _effective_status_from_usage(
            account,
            status_seed=account.status,
            primary_usage=primary,
            primary_used_percent=primary.used_percent,
            secondary_usage=secondary,
            secondary_used_percent=secondary.used_percent,
            monthly_usage=None,
            monthly_used_percent=None,
            runtime_reset=float(account.reset_at) if account.reset_at else None,
        )
        == AccountStatus.RATE_LIMITED
    )


def test_effective_status_keeps_paused_account_paused_with_usable_credits() -> None:
    account = _account(AccountStatus.PAUSED)
    primary = _primary_usage(credits_balance=25.0)
    secondary = _secondary_usage(credits_balance=25.0)

    assert (
        _effective_status_from_usage(
            account,
            status_seed=account.status,
            primary_usage=primary,
            primary_used_percent=primary.used_percent,
            secondary_usage=secondary,
            secondary_used_percent=secondary.used_percent,
            monthly_usage=None,
            monthly_used_percent=None,
            runtime_reset=float(account.reset_at) if account.reset_at else None,
        )
        == AccountStatus.PAUSED
    )


def test_normalize_account_routing_policy() -> None:
    assert _normalize_account_routing_policy("normal") == "normal"
    assert _normalize_account_routing_policy("burn_first") == "burn_first"
    assert _normalize_account_routing_policy("preserve") == "preserve"
    assert _normalize_account_routing_policy("legacy") == "normal"
    assert _normalize_account_routing_policy(None) == "normal"
