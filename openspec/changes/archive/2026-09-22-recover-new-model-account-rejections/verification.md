## Verification

- Completeness: shared classifier extension implemented; main Responses requirement and context synced; existing model slugs and routing configuration preserved.
- Correctness: 62 focused tests passed across classifier matching, existing recovery behavior, native WebSocket aliases, raw HTTP aliases, and HTTP bridge replacement/no-replacement behavior. Tests cover both GPT-6 Sol and Luna, unchanged request models, rejected-account exclusion, error preservation, accepted/output replay guards, and file pinning.
- Regression evidence: before the classifier extension, six targeted new unit/service cases failed; after the extension the focused suite passes.
- Coherence: independent code review confirmed exact message/model matching and reuse of existing bounded replay safeguards. No new settings or persistent entitlement state.
- Static validation: Ruff lint and formatting pass for six affected Python files; targeted Ty passes; `git diff --check` passes. All 49 main specifications and this change pass strict OpenSpec validation.

## Local runtime

Restarted `com.peteallen.codex-lb` on 2026-09-22. The replacement process started with the persisted nine-model catalog, completed startup, and refreshed it successfully. `/health/ready` returned status `ok`, database `ok`, and healthy single-member bridge membership.

Minimal native WebSocket requests with priority tier completed for both models after restart:

- Sol: `resp_0745b3960429f80f016ab2d82d662087d0b59e98099c292191`
- Luna: `resp_0eafe728da8ba42f016ab2d82fea5487d0a1610711163bee4a`

Both live probes selected the primary account. Recovery from the rejecting account is verified with deterministic route regressions; the original remote task has not been retried by this task. No commit, PR, or upstream release is claimed. Pre-existing local modifications were preserved, with a baseline patch under the ignored deployment-backup directory.
