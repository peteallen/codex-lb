## 1. OpenSpec and scope

- [x] 1.1 Keep this change focused on the four retained fork customizations.
- [x] 1.2 Preserve v1.23 i18n copy, localize new Dashboard controls in every
  supported locale, and omit the Reports date-picker, Responses wire-shape,
  and beta import-order patches.

## 2. Backend

- [x] 2.1 Port fork branding constants and working-day-aware weekly forecast.
- [x] 2.2 Add rollup-aware custom Dashboard overview date bounds.
- [x] 2.3 Preserve TTFT-based report throughput and add response-created
  fallback for tool-only turns.

## 3. Frontend

- [x] 3.1 Apply fork branding to title, header, auth, and status-bar link.
- [x] 3.2 Add the Dashboard custom range picker, draft-safe date editing, and
  local-calendar URL/query state.
- [x] 3.3 Add recent-request timing fields and localized approximate
  first-output display.

## 4. Regression coverage and validation

- [x] 4.1 Add backend regression tests for working-day forecast, local/DST
  custom ranges, bounded conversations, and TTFT/tool-only TPS.
- [x] 4.2 Add frontend tests for custom range state, query serialization,
  schema compatibility, branding, localized copy, and tool-only display.
- [x] 4.3 Run focused tests, lint/format/type checks, and a production build.
- [ ] 4.4 Run strict change and repo-wide OpenSpec validation. The OpenSpec CLI
  is unavailable in this worktree; validation must be rerun after integration.
