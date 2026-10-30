## Why

Operators with staggered Pro weekly resets need to know whether continued work will exhaust every eligible account before capacity returns. The removed credit charts depended on unknown plan allowances and did not answer that question.

## What Changes

- Add an observational weekly coverage forecast with an explicit learning state, empirical per-account capacity estimates, current-window average demand, and a fourteen-day reset simulation.
- Show a seven-day coverage timeline with a fourteen-day option, first gap and recovery, minimum reserve, account explanations and excluded-account reasons.
- Validate the estimator against retained history before presenting calibrated results. Missing, stale or incompatible evidence prevents a reassuring whole-pool forecast.
- Keep subscription estimates separate from purchased credits, reset credits, five-hour limits and routing decisions.

## Capabilities

### New Capabilities
- `weekly-coverage`: Evidence-based weekly quota coverage forecasts and dashboard presentation.

### Modified Capabilities
- `frontend-architecture`: Allow a coverage timeline without restoring the removed credit/percentage quota charts.

## Impact

Dashboard projections API, bounded quota/request-history reads, pure calibration and simulation logic, dashboard component and tests. Reuse retained history without a new database migration or environment setting. No change to live routing, billing or account credentials.
