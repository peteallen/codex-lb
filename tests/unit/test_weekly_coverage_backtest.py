from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest

from app.modules.dashboard.coverage_types import CoverageWorkBucket, WeeklyQuotaSample
from scripts import weekly_coverage_backtest as backtest

BASE = datetime(2026, 1, 5)


def _bucket(at: datetime) -> CoverageWorkBucket:
    return CoverageWorkBucket(
        account_id="private-account",
        started_at=at,
        model="gpt-6-sol",
        service_tier=None,
        context_long=False,
        input_tokens=1000,
        output_tokens=100,
        cached_input_tokens=0,
        cache_write_tokens=0,
        request_count=1,
    )


def test_backtest_calibration_receives_only_past_complete_buckets(monkeypatch):
    cutoff = BASE + timedelta(hours=8)
    samples = [WeeklyQuotaSample(BASE + timedelta(hours=i), i * 3, BASE + timedelta(days=7), 10080) for i in range(11)]
    buckets = [_bucket(BASE + timedelta(hours=i)) for i in range(11)]
    original = backtest.build_weekly_coverage
    captured = []

    def capture(accounts, **kwargs):
        captured.extend(accounts)
        return original(accounts, **kwargs)

    monkeypatch.setattr(backtest, "build_weekly_coverage", capture)
    backtest._evaluate_cutoffs(
        [backtest._AccountRow("private-account", "pro", "active", "normal")],
        {"private-account": samples},
        {"private-account": buckets},
        cutoff,
        cutoff,
        backtest.BacktestConfig(),
    )
    assert len(captured) == 1
    assert max(row.recorded_at for row in captured[0].quota_history) == cutoff
    assert max(row.started_at for row in captured[0].work_buckets) == cutoff - timedelta(hours=1)


def test_backtest_does_not_score_saturation_or_cross_a_reset():
    reset = BASE + timedelta(days=7)
    samples = [
        WeeklyQuotaSample(BASE + timedelta(hours=i), used, reset, 10080) for i, used in [(0, 10), (2, 14), (4, 100)]
    ]
    samples.extend(
        [
            WeeklyQuotaSample(BASE + timedelta(hours=6), 0, reset + timedelta(days=7), 10080),
            WeeklyQuotaSample(BASE + timedelta(hours=8), 10, reset + timedelta(days=7), 10080),
        ]
    )
    totals = backtest._ValidationTotals()
    backtest._score_held_out_intervals(
        totals,
        capacity=1,
        samples=samples,
        work_buckets=[_bucket(BASE + timedelta(hours=i)) for i in range(8)],
        cutoff=BASE,
        holdout_end=BASE + timedelta(hours=8),
    )
    assert totals.scored_intervals == 1


def test_read_only_connection_reads_wal_and_rejects_writes(tmp_path):
    path = tmp_path / "history.db"
    with sqlite3.connect(path) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE evidence (value INTEGER)")
        writer.execute("INSERT INTO evidence VALUES (1)")
        writer.commit()
        reader = backtest._open_read_only(path)
        try:
            assert reader.execute("SELECT value FROM evidence").fetchone()[0] == 1
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                reader.execute("DELETE FROM evidence")
        finally:
            reader.close()
        assert writer.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 1


def test_backtest_groups_work_by_actual_speed_instead_of_requested_speed():
    with sqlite3.connect(":memory:") as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("""
            CREATE TABLE request_logs (
                account_id TEXT, requested_at TEXT, model TEXT,
                actual_service_tier TEXT, service_tier TEXT, input_tokens INTEGER,
                output_tokens INTEGER, cached_input_tokens INTEGER, reasoning_tokens INTEGER,
                status TEXT, cost_usd REAL
            )
        """)
        connection.executemany(
            """
            INSERT INTO request_logs VALUES (
                'private-account', '2026-01-05 00:30:00.000000', 'gpt-6-sol', ?, 'default',
                1000, 100, 0, NULL, 'success', 0.01
            )
        """,
            [("priority",), ("default",)],
        )
        buckets = backtest._load_work_buckets(
            connection,
            ["private-account"],
            BASE,
            BASE + timedelta(hours=1),
        )["private-account"]
    assert {row.service_tier for row in buckets} == {"priority", "default"}
    assert [row.request_count for row in buckets] == [1, 1]
