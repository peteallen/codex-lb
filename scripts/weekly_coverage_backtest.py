"""Run a read-only historical validation of the weekly coverage estimator.

The command deliberately opens SQLite in read-only mode and emits
aggregate results only. It fits each prediction from the samples and hourly
work buckets available at a cutoff, then scores later quota drawdown intervals
that were not available at that cutoff.

Example::

    python -m scripts.weekly_coverage_backtest \
        --db .codex-lb/store.db \
        --output /tmp/weekly-coverage-backtest.json

The JSON report is safe to commit when it comes from a local database: it does
not contain account IDs, emails, request IDs, prompts, or raw request rows.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

from app.modules.dashboard.coverage_types import CoverageWorkBucket, WeeklyCoverageAccountInput, WeeklyQuotaSample
from app.modules.dashboard.weekly_coverage import (
    LIMIT_CENSOR_PERCENT,
    WEEKLY_WINDOW_MINUTES,
    _calibration_blocks,
    _is_reset_boundary,
    _work_between,
    build_weekly_coverage,
)

DEFAULT_LOOKBACK = timedelta(days=14)
DEFAULT_HOLDOUT = timedelta(days=7)
DEFAULT_STEP = timedelta(hours=12)
DEFAULT_FRESHNESS = timedelta(seconds=300)
MAX_RAW_WINDOW = timedelta(days=14)
MISSING_REASON = "validation_unavailable"


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    lookback: timedelta = DEFAULT_LOOKBACK
    holdout: timedelta = DEFAULT_HOLDOUT
    step: timedelta = DEFAULT_STEP
    freshness: timedelta = DEFAULT_FRESHNESS


@dataclass(frozen=True, slots=True)
class _AccountRow:
    account_id: str
    plan_type: str
    status: str
    routing_policy: str


@dataclass(slots=True)
class _ValidationTotals:
    cutoffs: int = 0
    eligible_account_cutoffs: int = 0
    calibrated_account_cutoffs: int = 0
    ready_account_cutoffs: int = 0
    learning_account_cutoffs: int = 0
    limited_account_cutoffs: int = 0
    ready_pool_cutoffs: int = 0
    zero_ready_pool_cutoffs: int = 0
    insufficient_evidence_cutoffs: int = 0
    simulated_pool_cutoffs: int = 0
    candidate_intervals: int = 0
    scored_intervals: int = 0
    incomplete_intervals: int = 0
    unexplained_intervals: int = 0
    absolute_errors: list[float] = field(default_factory=list)


def run_backtest(
    db_path: Path,
    *,
    config: BacktestConfig = BacktestConfig(),
) -> dict[str, object]:
    """Return an anonymized aggregate report from a consistent SQLite read snapshot."""

    with closing(_open_read_only(db_path)) as connection:
        accounts = _load_accounts(connection)
        report = _report_shell(config, accounts)
        if not accounts:
            report["validation"] = {"status": MISSING_REASON, "reason": "no_eligible_pro_accounts"}
            return report

        weekly_history, history_start, history_end = _load_weekly_history(connection, accounts)
        report_scope = cast(dict[str, object], report["scope"])
        report["scope"] = {
            **report_scope,
            "weeklySampleCount": sum(len(rows) for rows in weekly_history.values()),
            "historyStart": history_start.isoformat() if history_start else None,
            "historyEnd": history_end.isoformat() if history_end else None,
        }
        if history_start is None or history_end is None:
            report["validation"] = {"status": MISSING_REASON, "reason": "no_weekly_samples"}
            return report

        first_cutoff = _ceil_hour(history_start + config.lookback)
        last_cutoff = _floor_hour(history_end - config.holdout)
        if last_cutoff < first_cutoff or config.step.total_seconds() <= 0:
            report["validation"] = {"status": MISSING_REASON, "reason": "insufficient_time_span"}
            return report

        work_buckets = _load_work_buckets(
            connection,
            [account.account_id for account in accounts],
            history_start,
            history_end,
        )
        report["scope"] = {
            **report["scope"],
            "workBucketCount": sum(len(rows) for rows in work_buckets.values()),
        }
        totals = _evaluate_cutoffs(
            accounts,
            weekly_history,
            work_buckets,
            first_cutoff,
            last_cutoff,
            config,
        )
        report["cutoffs"] = {
            "first": first_cutoff.isoformat(),
            "last": last_cutoff.isoformat(),
            "stepHours": config.step.total_seconds() / 3600,
            "evaluated": totals.cutoffs,
            "eligibleAccountCutoffs": totals.eligible_account_cutoffs,
            "calibratedAccountCutoffs": totals.calibrated_account_cutoffs,
            "readyAccountCutoffs": totals.ready_account_cutoffs,
            "learningAccountCutoffs": totals.learning_account_cutoffs,
            "limitedAccountCutoffs": totals.limited_account_cutoffs,
            "readyPoolCutoffs": totals.ready_pool_cutoffs,
            "zeroReadyPoolCutoffs": totals.zero_ready_pool_cutoffs,
            "insufficientEvidenceCutoffs": totals.insufficient_evidence_cutoffs,
            "simulatedPoolCutoffs": totals.simulated_pool_cutoffs,
        }
        report["validation"] = _validation_report(totals)
        return report


def _evaluate_cutoffs(
    accounts: list[_AccountRow],
    weekly_history: dict[str, list[WeeklyQuotaSample]],
    work_buckets: dict[str, list[CoverageWorkBucket]],
    first_cutoff: datetime,
    last_cutoff: datetime,
    config: BacktestConfig,
) -> _ValidationTotals:
    totals = _ValidationTotals()
    cutoff = _floor_hour(first_cutoff)
    while cutoff <= last_cutoff:
        totals.cutoffs += 1
        calibration_start = cutoff - config.lookback
        inputs: list[WeeklyCoverageAccountInput] = []
        for account in accounts:
            samples = tuple(
                sample
                for sample in weekly_history.get(account.account_id, [])
                if calibration_start <= sample.recorded_at <= cutoff
            )
            buckets = tuple(
                bucket
                for bucket in work_buckets.get(account.account_id, [])
                if calibration_start <= bucket.started_at < cutoff
            )
            inputs.append(
                WeeklyCoverageAccountInput(
                    # The estimator needs a stable key for matching its own
                    # response, but the key never enters the report.
                    account_id=account.account_id,
                    label="eligible account",
                    plan_type=account.plan_type,
                    status=account.status,
                    quota_history=samples,
                    work_buckets=buckets,
                    routing_policy=account.routing_policy,
                )
            )

        response = build_weekly_coverage(
            inputs,
            now=cutoff,
            routing_strategy="capacity_weighted",
            freshness_seconds=config.freshness.total_seconds(),
        )
        included_forecasts = [account for account in response.accounts if account.status != "excluded"]
        totals.eligible_account_cutoffs += len(included_forecasts)
        totals.ready_account_cutoffs += sum(account.status == "ready" for account in included_forecasts)
        totals.learning_account_cutoffs += sum(account.status == "learning" for account in included_forecasts)
        totals.limited_account_cutoffs += sum(account.status == "limited" for account in included_forecasts)
        totals.ready_pool_cutoffs += response.status == "ready"
        totals.zero_ready_pool_cutoffs += bool(included_forecasts) and not any(
            account.status == "ready" for account in included_forecasts
        )
        totals.insufficient_evidence_cutoffs += response.status in {"learning", "limited"}
        totals.calibrated_account_cutoffs += sum(
            account.capacity_work_units is not None for account in included_forecasts
        )
        if response.status == "ready" and response.intervals:
            totals.simulated_pool_cutoffs += 1

        response_by_id = {account.account_id: account for account in response.accounts}
        for account in accounts:
            forecast = response_by_id[account.account_id]
            if forecast.status != "ready" or forecast.capacity_work_units is None:
                continue
            _score_held_out_intervals(
                totals,
                capacity=forecast.capacity_work_units,
                samples=weekly_history.get(account.account_id, []),
                work_buckets=work_buckets.get(account.account_id, []),
                cutoff=cutoff,
                holdout_end=min(cutoff + config.holdout, last_cutoff + config.holdout),
            )
        cutoff += config.step
    return totals


def _score_held_out_intervals(
    totals: _ValidationTotals,
    *,
    capacity: float,
    samples: list[WeeklyQuotaSample],
    work_buckets: list[CoverageWorkBucket],
    cutoff: datetime,
    holdout_end: datetime,
) -> None:
    if capacity <= 0:
        return
    before = [sample for sample in samples if sample.recorded_at <= cutoff]
    if not before:
        return
    baseline = before[-1]
    future_samples: list[WeeklyQuotaSample] = []
    for current in samples:
        if current.recorded_at <= cutoff or current.recorded_at > holdout_end:
            continue
        if _is_reset_boundary(baseline, current):
            # Capacity is regime-specific. A later reset belongs to a future
            # fit and must not be scored against the earlier estimate.
            break
        future_samples.append(current)
        baseline = current
    if not future_samples:
        return

    scoring_samples = [before[-1], *future_samples]
    for start_edge, end_edge, _start_percent, end_percent in _calibration_blocks(scoring_samples):
        if start_edge < cutoff or end_edge > holdout_end:
            continue
        if end_percent >= LIMIT_CENSOR_PERCENT:
            continue
        totals.candidate_intervals += 1
        delta_percent = end_percent - _start_percent
        total = _work_between(work_buckets, start_edge, end_edge)
        if total.incomplete:
            totals.incomplete_intervals += 1
            continue
        if total.work_units <= 0:
            totals.unexplained_intervals += 1
            continue
        predicted_drop = total.work_units * 100.0 / capacity
        totals.absolute_errors.append(abs(predicted_drop - delta_percent))
        totals.scored_intervals += 1


def _validation_report(totals: _ValidationTotals) -> dict[str, object]:
    errors = sorted(totals.absolute_errors or [])
    if not errors:
        return {
            "status": MISSING_REASON,
            "reason": "no_complete_held_out_drawdown_intervals",
            "candidateIntervals": totals.candidate_intervals,
            "scoredIntervals": 0,
            "incompleteIntervals": totals.incomplete_intervals,
            "unexplainedIntervals": totals.unexplained_intervals,
        }
    mean_error = sum(errors) / len(errors)
    midpoint = len(errors) // 2
    median_error = errors[midpoint] if len(errors) % 2 else (errors[midpoint - 1] + errors[midpoint]) / 2
    return {
        "status": "available",
        "metric": "absolute percentage-point error for held-out quota drawdown",
        "candidateIntervals": totals.candidate_intervals,
        "scoredIntervals": totals.scored_intervals,
        "incompleteIntervals": totals.incomplete_intervals,
        "unexplainedIntervals": totals.unexplained_intervals,
        "coveragePercent": round(100 * totals.scored_intervals / max(1, totals.candidate_intervals), 2),
        "meanAbsoluteErrorPercentagePoints": round(mean_error, 3),
        "medianAbsoluteErrorPercentagePoints": round(median_error, 3),
        "p95AbsoluteErrorPercentagePoints": round(errors[min(len(errors) - 1, int(len(errors) * 0.95))], 3),
    }


def _report_shell(config: BacktestConfig, accounts: list[_AccountRow]) -> dict[str, object]:
    plan_counts = Counter(account.plan_type.lower() for account in accounts)
    status_counts = Counter(account.status for account in accounts)
    return {
        "schemaVersion": 1,
        "mode": "read_only_sqlite_transaction",
        "config": {
            "lookbackDays": config.lookback.total_seconds() / 86400,
            "holdoutDays": config.holdout.total_seconds() / 86400,
            "freshnessHours": config.freshness.total_seconds() / 3600,
        },
        "scope": {
            "eligibleAccountCount": len(accounts),
            "planCounts": dict(sorted(plan_counts.items())),
            "statusCounts": dict(sorted(status_counts.items())),
        },
        "limitations": [
            (
                "Historical account status and plan changes are not retained; "
                "current eligible accounts are used as the validation cohort."
            ),
            (
                "Account attribution is required for work scoring; unmatched or "
                "incomplete work is reported as unavailable evidence."
            ),
            "The metric scores account capacity drawdown, not a guarantee of future routing or provider behavior.",
            "Only ready estimates are scored; saturation does not measure uncensored drawdown.",
            (
                "Held-out capacity error is evaluated separately from full-pool interruption timing; "
                "the historical request log cannot reproduce sticky-session allocation exactly."
            ),
            "Only seven-day quota observations are included; five-hour limits and purchased credits are excluded.",
        ],
        "cutoffs": {},
        "validation": {},
    }


def _open_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    uri = f"file:{path.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA temp_store=MEMORY")
    # Hold one consistent read snapshot while the live process may append to
    # the database or its WAL. No write-capable connection is ever opened.
    connection.execute("BEGIN")
    return connection


def _load_accounts(connection: sqlite3.Connection) -> list[_AccountRow]:
    rows = connection.execute(
        """
        SELECT id, plan_type, status, routing_policy
        FROM accounts
        WHERE lower(plan_type) IN ('pro', 'prolite', 'promax')
          AND status IN ('active', 'rate_limited', 'quota_exceeded')
        ORDER BY id
        """
    ).fetchall()
    return [
        _AccountRow(
            account_id=str(row["id"]),
            plan_type=str(row["plan_type"]),
            status=str(row["status"]),
            routing_policy=str(row["routing_policy"] or "normal"),
        )
        for row in rows
    ]


def _load_weekly_history(
    connection: sqlite3.Connection,
    accounts: list[_AccountRow],
) -> tuple[dict[str, list[WeeklyQuotaSample]], datetime | None, datetime | None]:
    if not accounts:
        return {}, None, None
    placeholders = ",".join("?" for _ in accounts)
    rows = connection.execute(
        f"""
        SELECT account_id, recorded_at, used_percent, reset_at, window_minutes
        FROM usage_history
        WHERE account_id IN ({placeholders})
          AND window_minutes = ?
        ORDER BY recorded_at ASC, id ASC
        """,
        [account.account_id for account in accounts] + [WEEKLY_WINDOW_MINUTES],
    ).fetchall()
    history: dict[str, list[WeeklyQuotaSample]] = {account.account_id: [] for account in accounts}
    for row in rows:
        recorded_at = _parse_datetime(row["recorded_at"])
        reset_at = _epoch_datetime(row["reset_at"]) if row["reset_at"] is not None else None
        history[str(row["account_id"])].append(
            WeeklyQuotaSample(
                recorded_at=recorded_at,
                used_percent=float(row["used_percent"]),
                reset_at=reset_at,
                window_minutes=int(row["window_minutes"]) if row["window_minutes"] is not None else None,
            )
        )
    recorded = [sample.recorded_at for rows_for_account in history.values() for sample in rows_for_account]
    return history, min(recorded) if recorded else None, max(recorded) if recorded else None


def _load_work_buckets(
    connection: sqlite3.Connection,
    account_ids: list[str],
    since: datetime,
    until: datetime,
) -> dict[str, list[CoverageWorkBucket]]:
    if not account_ids or until <= since:
        return {}

    result: dict[str, list[CoverageWorkBucket]] = {account_id: [] for account_id in account_ids}
    cursor = _floor_hour(since)
    end = _floor_hour(until)
    while cursor < end:
        chunk_end = min(cursor + MAX_RAW_WINDOW, end)
        chunk = _load_raw_work_window(connection, account_ids, cursor, chunk_end)
        for account_id, buckets in chunk.items():
            result.setdefault(account_id, []).extend(buckets)
        cursor = chunk_end
    for account_id in result:
        result[account_id].sort(key=lambda bucket: bucket.started_at)
    return result


def _load_raw_work_window(
    connection: sqlite3.Connection,
    account_ids: list[str],
    since: datetime,
    until: datetime,
) -> dict[str, list[CoverageWorkBucket]]:
    end = _floor_hour(until)
    start = max(_floor_hour(since), end - MAX_RAW_WINDOW)
    if end <= start:
        return {account_id: [] for account_id in account_ids}

    account_placeholders = ",".join("?" for _ in account_ids)
    output_expr = "COALESCE(output_tokens, reasoning_tokens)"
    cached_expr = (
        "CASE WHEN cached_input_tokens IS NULL THEN 0 "
        "WHEN input_tokens IS NULL THEN MAX(0, cached_input_tokens) "
        "ELSE MAX(0, MIN(cached_input_tokens, input_tokens)) END"
    )
    cache_write_expr = (
        "COALESCE(SUM(CASE WHEN cache_write_tokens IS NULL THEN 0 "
        "WHEN input_tokens IS NULL THEN MAX(0, cache_write_tokens) "
        f"ELSE MAX(0, MIN(cache_write_tokens, input_tokens - ({cached_expr}))) END), 0)"
        if _has_column(connection, "cache_write_tokens")
        else "0"
    )
    missing_expr = (
        f"input_tokens IS NULL OR ({output_expr}) IS NULL "
        f"OR input_tokens < 0 OR ({output_expr}) < 0 "
        "OR cached_input_tokens < 0 "
        f"OR (input_tokens = 0 AND ({output_expr}) = 0 AND status = 'success')"
    )
    if _has_column(connection, "cache_write_tokens"):
        missing_expr += " OR cache_write_tokens < 0"
    tier_expr = "COALESCE(actual_service_tier, service_tier)"
    rows = connection.execute(
        f"""
        SELECT account_id,
               CAST(strftime('%s', requested_at) AS INTEGER) / 3600 * 3600 AS bucket_epoch,
               model,
               {tier_expr} AS service_tier,
               CASE WHEN {missing_expr} THEN 1 ELSE 0 END AS missing_flag,
               COALESCE(SUM(input_tokens), 0) AS input_tokens,
               COALESCE(SUM({output_expr}), 0) AS output_tokens,
               COALESCE(SUM({cached_expr}), 0) AS cached_input_tokens,
               {cache_write_expr} AS cache_write_tokens,
               COUNT(*) AS request_count,
               SUM(CASE WHEN {missing_expr} THEN 1 ELSE 0 END) AS missing_count
        FROM request_logs
        WHERE account_id IN ({account_placeholders})
          AND requested_at >= ?
          AND requested_at < ?
        GROUP BY account_id, bucket_epoch, model, {tier_expr}, missing_flag
        """,
        account_ids + [_sqlite_datetime(start), _sqlite_datetime(end)],
    ).fetchall()

    result: dict[str, list[CoverageWorkBucket]] = {account_id: [] for account_id in account_ids}
    for row in rows:
        result.setdefault(str(row["account_id"]), []).append(
            CoverageWorkBucket(
                account_id=str(row["account_id"]),
                started_at=_epoch_datetime(int(row["bucket_epoch"])),
                model=str(row["model"]),
                service_tier=str(row["service_tier"]) if row["service_tier"] is not None else None,
                # Context classification is legacy metadata; empirical work
                # uses measured input/output totals directly.
                context_long=None,
                input_tokens=int(row["input_tokens"] or 0),
                output_tokens=int(row["output_tokens"] or 0),
                cached_input_tokens=int(row["cached_input_tokens"] or 0),
                cache_write_tokens=int(row["cache_write_tokens"] or 0),
                request_count=int(row["request_count"] or 0),
                missing_usage_count=int(row["missing_count"] or 0),
            )
        )
    return result


def _has_column(connection: sqlite3.Connection, column: str) -> bool:
    return any(str(row[1]) == column for row in connection.execute("PRAGMA table_info(request_logs)"))


def _parse_datetime(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _epoch_datetime(value: object) -> datetime:
    return datetime.fromtimestamp(float(cast(float | int | str, value)), timezone.utc).replace(tzinfo=None)


def _epoch_seconds(value: datetime) -> int:
    return int((value - datetime(1970, 1, 1)).total_seconds())


def _floor_hour(value: datetime) -> datetime:
    return datetime(1970, 1, 1) + timedelta(hours=_epoch_seconds(value) // 3600)


def _ceil_hour(value: datetime) -> datetime:
    floor = _floor_hour(value)
    return floor if floor == value else floor + timedelta(hours=1)


def _sqlite_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S.%f")


def _write_report(report: dict[str, object], output: Path | None) -> None:
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(serialized, end="")
        return
    output.write_text(serialized, encoding="utf-8")
    print(f"wrote anonymized report to {output}")


def _duration_days(value: str) -> timedelta:
    days = float(value)
    if days <= 0:
        raise argparse.ArgumentTypeError("duration must be positive")
    return timedelta(days=days)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="SQLite snapshot to open read-only")
    parser.add_argument("--output", type=Path, help="Write the anonymized JSON report to this path")
    parser.add_argument("--lookback-days", type=_duration_days, default=DEFAULT_LOOKBACK)
    parser.add_argument("--holdout-days", type=_duration_days, default=DEFAULT_HOLDOUT)
    parser.add_argument("--step-hours", type=float, default=DEFAULT_STEP.total_seconds() / 3600)
    parser.add_argument("--freshness-hours", type=float, default=DEFAULT_FRESHNESS.total_seconds() / 3600)
    args = parser.parse_args()
    if args.step_hours <= 0 or args.freshness_hours <= 0:
        parser.error("step and freshness durations must be positive")
    config = BacktestConfig(
        lookback=args.lookback_days,
        holdout=args.holdout_days,
        step=timedelta(hours=args.step_hours),
        freshness=timedelta(hours=args.freshness_hours),
    )
    _write_report(run_backtest(args.db, config=config), args.output)


if __name__ == "__main__":
    main()
