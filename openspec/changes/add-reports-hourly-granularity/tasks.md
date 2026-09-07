## 1. Backend contract and aggregation

- [x] 1.1 Add typed hourly report rows plus explicit chart granularity to the
  Reports API response.
- [x] 1.2 Share report bucket aggregation logic and add complete timezone-aware
  hourly ranges with zero-filled gaps.
- [x] 1.3 Populate hourly rows only for one-day and two-day inclusive ranges
  while preserving daily rows and every existing report aggregate.

## 2. Frontend rendering

- [x] 2.1 Parse the new response fields and map all five charts to the
  server-selected hourly or daily series.
- [x] 2.2 Format hourly axis/tooltip labels and switch cost/token titles and
  chart-filter labels without changing persisted visibility IDs.
- [x] 2.3 Keep Daily Breakdown and CSV wired exclusively to daily rows.

## 3. Regression coverage and verification

- [x] 3.1 Add backend coverage for hourly metric/filter parity, zero gaps, DST,
  and the two-day/three-day boundary.
- [x] 3.2 Add frontend schema and chart/page coverage for hourly and daily
  rendering behavior.
- [x] 3.3 Run focused backend/frontend tests, type/lint checks, diff checks, and
  available OpenSpec validation.
