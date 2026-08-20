## 1. Contract and regression coverage

- [x] 1.1 Add focused tests for capability-aware HTTP fallback selection and
  response-ID lineage persistence.
- [x] 1.2 Add focused tests for graceful drain with only an active fallback.
- [x] 1.3 Add focused cancellation coverage while response-create admission is
  blocked.

## 2. Implementation

- [x] 2.1 Thread the capability requirement into the HTTP streamer and persist
  the generated response alias before downstream delivery.
- [x] 2.2 Include detached fallback tasks in drain activity checks.
- [x] 2.3 Make pre-relay cancellation release reservation and admission once.

## 3. Verification

- [x] 3.1 Run focused proxy unit/integration tests, formatter, linter, and
  `git diff --check`.
- [x] 3.2 Run strict OpenSpec validation and inspect the final diff.
