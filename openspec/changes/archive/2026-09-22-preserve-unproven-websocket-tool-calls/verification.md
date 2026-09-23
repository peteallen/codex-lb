## Verification

- Reproduced before the fix: the visualization function-call cases on both WebSocket routes failed with `No tool call found for function call output` from the validating upstream stub.
- After the fix: all 30 route cases passed, covering function/custom/apply-patch calls with matching, absent, different-response, different-type, and client-created-call evidence.
- Surrounding WebSocket integration suite plus new helper cases: 118 passed. The real keepalive socket test initially failed because sandbox binding was denied; its permitted rerun passed.
- Selected existing request-preparation, continuity, and trimming unit coverage: 20 passed.
- Ruff lint/format and targeted `ty check` passed. The scoped diff preserves pre-existing local edits.
- Strict validation of this change and `responses-api-compat` passed. Full spec validation: 48 passed, one unrelated existing `api-keys` spec failed because requirements 23 and 24 lack SHALL/MUST. That file is unchanged from HEAD.

## Requirement and design coverage

The request-preparation path passes recorded call types only for the exact completed response ID. The helper preserves calls unless their ID and type match this evidence. Route cases cover the three call types and continuity boundaries; mixed-prefix and malformed-identity helper cases verify retained order and conservative handling. Existing assistant/reasoning trimming remains covered by the adjusted integration test and utility tests.

The requirement and rationale are synced into the owning spec/context. No settings, schemas, routing, retry, or settlement paths changed. No unresolved issue in this change blocks archive. The historical request body remains unavailable, so the local reproduction proves the defect without claiming conclusive attribution of that incident.

## Local deployment

Restarted `com.peteallen.codex-lb` after verification. Listener PID changed from 4038 to 29087. `/health/ready` returned HTTP 200 with status/database `ok` and the local instance present in its bridge ring. The code remains uncommitted in the existing checkout; no PR or upstream release was created. Recovery of the remote client's failed task has not been observed.
