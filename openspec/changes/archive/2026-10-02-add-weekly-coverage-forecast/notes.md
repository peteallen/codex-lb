# Historical validation

The final read-only run on 2026-10-02 is recorded in [historical-validation.json](historical-validation.json). It used one consistent SQLite read transaction, a seven-day calibration window, seven-day holdout, twelve-hour cutoff cadence and five-minute freshness rule. The report contains only aggregate results and no account identities or credentials.

The current eligible cohort contained 5 Pro-family accounts. Retained history supplied 422,746 weekly observations and 16,946 hourly work buckets across 204 historical cutoffs. Historical account status and plan changes are unavailable, so this is a current-cohort audit rather than a reconstruction of historic eligibility.

There were 1 ready, 451 learning and 568 limited account-cutoffs. No complete pool met the readiness safeguards (0 ready pool cutoffs). Only ready estimates are eligible for scoring; saturation and reset-crossing intervals are excluded. The one candidate held-out interval had no attributable work, leaving 0 scorable intervals.

**Accuracy validation is unavailable.** This dataset does not establish capacity-error or interruption-timing accuracy. It does establish that the current safeguards withhold a reassuring whole-pool forecast when retained evidence is incomplete. Synthetic tests verify transfer of demand, staggered reset recovery, exhaustion at a reset boundary, and incomplete-evidence presentation separately.

Reproduce with:

```sh
.venv/bin/python -m scripts.weekly_coverage_backtest \
  --db /path/to/store.db --output /tmp/weekly-coverage-validation.json
```

The command opens SQLite with `mode=ro`, `query_only=ON` and one read transaction, including current WAL data. It never loads credential columns. Future observations are used only for scoring, and calibration receives only complete work buckets before each cutoff. No live routing, credentials or database contents were changed.
