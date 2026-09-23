## Context

The bridge session key is hard for session-header isolation even when the route uses prompt-cache affinity. The durable reconnect gate conflated that isolation strength with Codex conversational continuity. The session-level anchor gate already checks Codex continuity.

## Decision

Require `CODEX_SESSION` affinity or a verified durable input prefix in the durable reconnect gate. Keep the existing explicit-anchor and full-resend guards. This prevents an independent short OpenAI request from acquiring a stale response ID while retaining proved context reuse and intentional Codex delta requests.

## Risks and validation

Test both streaming and collected HTTP responses, live reuse and reconnect, explicit anchors and client turn state. Existing prefix-proof, tool-output, ownership, and recovery tests must remain green. Preserve pre-existing dirty work and restart the existing local service only after validation.
