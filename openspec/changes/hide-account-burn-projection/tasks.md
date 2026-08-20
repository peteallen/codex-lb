## 1. Dashboard presentation

- [x] 1.1 Remove the account burn projection stat and its frontend-only calculation path.
- [x] 1.2 Remove the card visibility preference and Appearance settings toggle.
- [x] 1.3 Remove obsolete translations while preserving other projection-backed dashboard surfaces.

## 2. Specification and tests

- [x] 2.1 Synchronize the frontend architecture specification with the hidden-card behavior.
- [x] 2.2 Update unit and integration coverage to assert the card and toggle stay absent.

## 3. Validation

- [x] 3.1 Run focused frontend tests, the full frontend test suite, lint, typecheck, and production build.
- [x] 3.2 Verify the final diff is clean.
- [ ] 3.3 Run OpenSpec validation when the CLI is available (currently blocked because `openspec` is not installed).
