## 1. Recoverable overload scheduling

- [x] 1.1 Implement pre-acceptance raw HTTP overload classification and routed failover regression coverage.
- [x] 1.2 Implement bounded, success-resistant account overload cooldown with selection and expiry tests.
- [x] 1.3 Keep recoverable raw HTTP overloads pending beyond account-attempt exhaustion, preserving safe affinity escape and owner-bound waiting.
- [x] 1.4 Align bridged HTTP and direct WebSocket overload waiting/failover and verify accepted/visible-output refusal.

## 2. Verification and delivery

- [x] 2.1 Verify cancellation, reservation settlement, leases, deadline expiry, and available/busy account routing at external routes.
- [x] 2.2 Run targeted and broader proxy regressions, lint, typing, architecture budgets, and strict OpenSpec validation.
- [x] 2.3 Synchronize owning specifications/context, independently review, and archive only after verification.
- [x] 2.4 Preserve rollback source, deploy each verified candidate with one controlled restart, and verify live readiness and PID stability.
