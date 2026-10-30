## Why

The official Codex client can override voice endpoints but continues using the selected model provider's bearer token. A local, separately authenticated voice path lets an operator use their primary ChatGPT account for voice while retaining codex-lb for model requests, and isolates the proxy from voice disconnect diagnosis.

## What Changes

- Add an opt-in standalone loopback adapter for private Codex WebRTC call creation and the current client control WebSocket.
- Authenticate local requests with the existing provider key and forward only voice traffic with the explicitly selected Codex-managed ChatGPT identity.
- Preserve call ownership, frames, and bounded cleanup; record content-free lifecycle diagnostics.
- Document installation, credential renewal boundaries, client restart, and rollback without modifying the base proxy's runtime or settings.

## Capabilities

### New Capabilities

- `local-voice-direct`: Optional local voice routing with a pinned primary identity, independent of pooled model traffic.

### Modified Capabilities

None. The existing pooled realtime compatibility contract remains unchanged.

## Impact

Standalone scripts, local HTTP/WebSocket regression tests, and OpenSpec/user documentation. Installation changes only the user's two experimental voice URL overrides and adds a separate macOS LaunchAgent. Existing aiohttp, certifi, and Pydantic dependencies are sufficient. No changes to codex-lb routes, database, provider configuration, or release defaults.
