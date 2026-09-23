# Verification

- Added native WebSocket, raw HTTP streaming, and HTTP bridge regressions for consecutive GPT-6 Sol/Luna account-model rejections, pool exhaustion, unchanged model/API-key scope, no account revisit, generic replay-budget preservation, and safe continuation/file guards.
- Focused integration/unit validation passed: 60 tests in the combined model-recovery/bridge suite, 23 native WebSocket pool tests, 45 raw-stream tests, and 30 targeted legacy retry tests.
- Ruff lint/format, targeted Ty, `git diff --check`, strict change validation, and all 49 main OpenSpec validations passed.
- Restarted `com.peteallen.codex-lb` at 2026-09-22 22:45 UTC. `/health/ready` returned `status: ok`, database `ok`, and a healthy single-member bridge ring.
- Minimal live native WebSocket probes completed `gpt-6-sol` and `gpt-6-luna` after restart. The smoke key uses the local configured pool; the LAN key's multi-account path is covered by deterministic pool regressions and the live logs previously showed openai10 serving Sol.
- No commit or PR was created; pre-existing working-tree changes were preserved.
