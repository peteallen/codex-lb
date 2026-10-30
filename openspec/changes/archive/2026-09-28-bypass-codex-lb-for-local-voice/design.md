## Context

The official client exposes separate WebRTC call and sideband base URL overrides but derives authentication from the selected provider. The configured codex-lb bearer cannot authenticate directly with OpenAI. Audio already travels over WebRTC between the app and OpenAI. Current evidence includes WebRTC connection failures, not proof that codex-lb causes stutter or hangs.

## Goals / Non-Goals

**Goals:** Isolate voice setup and control from the running load balancer, use an explicitly selected existing ChatGPT login, preserve model routing, and provide safe disconnect diagnostics.

**Non-Goals:** Change media transport, implement the public Realtime API, patch the official app, create Platform API keys, automatically renew shared refresh credentials, or guarantee a fix for a WebRTC/network/device fault.

## Decisions

- Use a standalone aiohttp script, copied into a private application-support directory and managed by a separate LaunchAgent. Import no app modules or database code. Existing installed Python dependencies suffice; the base service remains unchanged.
- Validate the local key against the current provider bearer in user config. Pin both email and ChatGPT account id at installation. Reread the official access-token file at each new operation, validate locally managed claims, and leave token verification to OpenAI. Do not independently rotate the shared refresh token.
- Accept only the two paths used by the installed client. Use fixed OpenAI destinations, no redirects or environment proxies, explicit metadata forwarding, no cookies, and verified TLS. Reject browser Origin headers.
- Store only hashed call/key identities and the pinned account in a bounded in-memory registry. Bind before exposing successful call creation; refuse unknown, expired, duplicate-active, or mismatched attachment. Service restart intentionally requires a new call.
- Relay opaque text/binary messages with no session duration/idle deadline. Own both relay tasks and close both sockets on every exit. Log only fixed categories, direction, close codes, and elapsed time. Disable library access/exception logs that could contain private paths or contents.

## Risks / Trade-offs

- Private Codex endpoints can change. Limit compatibility claims to the verified client shape; fail closed on unexpected Locations or routes.
- Codex may not refresh its stored login while using an explicit provider bearer. Reject expired credentials clearly and document refreshing the official login. Do not conceal this with independent OAuth refresh races.
- The helper depends on the existing Python environment. Use an installed source copy to avoid branch edits changing the live helper; document the environment dependency.
- Bypassing setup/control cannot fix a failing WebRTC media path. Automated local HTTP/WebSocket tests and real account health can verify configuration, but audible quality needs a fresh user voice call.

## Migration Plan

Test using local upstream fixtures, then install the helper, pinned identity, and LaunchAgent with owner-only files. Verify listener, identity readiness, and primary-account upstream authorization. Back up user config without displaying secrets and atomically modify only the two voice overrides. Verify the model provider is byte-for-byte unchanged and codex-lb remains healthy. Do not interrupt the running official app; report any restart boundary. Roll back by restoring only the original override entries, then unloading the helper.
