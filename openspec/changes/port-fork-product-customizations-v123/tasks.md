## 1. OpenSpec and scope

- [x] 1.1 Keep this change focused on the four retained fork customizations.
- [x] 1.2 Preserve v1.23 i18n copy and omit the Reports date-picker, Responses
  wire-shape, and beta import-order patches.

## 2. Backend

- [x] 2.1 Port fork branding constants and working-day-aware weekly forecast.
- [x] 2.2 Add rollup-aware custom Dashboard overview date bounds.
- [x] 2.3 Add upstream-anchor tool-only throughput to report medians.

## 3. Frontend

- [x] 3.1 Apply fork branding to title, header, auth, and status-bar link.
- [x] 3.2 Add the Dashboard custom range picker and URL/query state.
- [x] 3.3 Add recent-request timing fields and approximate first-output display.

## 4. Regression coverage and validation

- [x] 4.1 Add backend regression tests for working-day forecast, custom range,
  bounded conversations, and tool-only TPS.
- [x] 4.2 Add frontend tests for custom range state, query serialization,
  schema compatibility, branding, and tool-only display.
- [x] 4.3 Run focused tests, lint/format/type checks, production build, and
  strict OpenSpec validation.
