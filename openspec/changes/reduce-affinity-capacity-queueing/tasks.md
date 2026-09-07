## 1. Admission accounting

- [x] 1.1 Acquire the session gate before account startup capacity and release both on all later failure/cancellation paths.
- [x] 1.2 Add contention and cancellation regressions proving gate waiters leave unrelated account startup capacity available.

## 2. Capacity-aware affinity

- [x] 2.1 Preserve a proof-gated original full resend for locally rejected unsent bridge requests.
- [x] 2.2 Use an independent same-account connection, then eligible alternate-account selection, without waiting on a busy canonical bridge or mutating its ownership.
- [x] 2.3 Cover full-context/anchor restoration, prompt-cache preservation, late admission races, and negative controls for files, client anchors, delta-only context, and accepted/output-bearing work through the bridge path.

## 3. Wakeups and diagnostics

- [x] 3.1 Add bounded capacity-release wakeups for local bridge retries and test competing waiters/cancellation without changing upstream backoff.
- [x] 3.2 Emit bounded missing-created progress diagnostics and verify they contain no payload content.

## 4. Verification and rollout

- [x] 4.1 Run focused proxy/integration regressions, lint/type checks, strict OpenSpec validation, and available broader CI.
- [ ] 4.2 Synchronize normative/context documentation and archive the verified change.
- [ ] 4.3 Commit and push main, arm an independent rollback watchdog, perform one bounded restart, and verify readiness and post-restart request behavior.
