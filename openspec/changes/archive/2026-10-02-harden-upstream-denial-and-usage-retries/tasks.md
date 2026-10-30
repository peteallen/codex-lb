## 1. Implementation

- [x] 1.1 Honor numeric/date Retry-After across both usage transports and reset-credit consumption.
- [x] 1.2 Recognize explicit revocation and prevent terminal credentials from entering forced-refresh retry paths.
- [x] 1.3 Fail closed on unknown authorization denials while preserving recognized fallback and account ownership.
- [x] 1.4 Require explicit terminal evidence for usage deactivation, removing bare 402/404 handling.

## 2. Verification and specification sync

- [x] 2.1 Add client, updater, and public proxy regression coverage and run relevant existing suites.
- [x] 2.2 Run lint, typing, and strict OpenSpec validation; sync requirements and record verification before archive.
