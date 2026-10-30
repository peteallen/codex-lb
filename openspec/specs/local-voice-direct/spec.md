# local-voice-direct Specification

## Purpose

Define opt-in, account-pinned local routing for private Codex voice while preserving pooled model traffic.

## Requirements

### Requirement: Voice routing is isolated and opt-in

The optional standalone adapter MUST bind only to IPv4 loopback and accept only a health route, private call creation at `POST /backend-api/codex/realtime/calls`, and sideband upgrades at `GET /backend-api/codex/{call_id}` for bounded ASCII `rtc_...` or canonical UUID identifiers. It MUST authenticate voice requests with the selected Codex provider's configured bearer, reject browser-origin requests, and never forward model routes. Its command-line interface MUST use fixed OpenAI upstream destinations. It MUST introduce no base-service dependency, database write, or `CODEX_LB_*` setting.

#### Scenario: Normal model calls remain pooled

- **WHEN** the adapter is installed and the two user-level voice URL overrides point to it
- **THEN** the selected provider and every non-voice setting remain unchanged
- **AND** `/responses`, unrelated paths, and trailing-slash variants on the adapter do not reach OpenAI

#### Scenario: Local request is not authorized

- **WHEN** a voice request has a missing, incorrect, or ambiguous bearer, or a browser Origin
- **THEN** the adapter rejects it before any upstream request

### Requirement: Voice uses the selected Codex-managed identity

The adapter MUST reread Codex's auth file for each call creation and attachment, validate the access token's email, account identity, and expiration against the installed identity, and replace downstream credentials with that token and account header. It MUST fail closed on missing, invalid, expired, or switched credentials. It MUST NOT write the auth file, use the shared refresh token, or select a pooled account. It MUST strip downstream credentials and connection-specific headers while preserving supported Codex protocol metadata and opaque request bodies.

#### Scenario: Codex rotates the access token

- **WHEN** Codex replaces the access token for the same selected account between call creation and attachment
- **THEN** the attachment uses the new token and the original account

#### Scenario: Login becomes unavailable or changes

- **WHEN** the auth file has an expired token or a different email or account
- **THEN** new voice operations fail with a content-free actionable error
- **AND** no token refresh or account substitution occurs

### Requirement: Calls retain bounded ownership and upstream destinations

Call creation MUST send the original bounded body to `https://chatgpt.com/backend-api/codex/realtime/calls` exactly once. Successful responses MUST have a supported root-relative or OpenAI-hosted HTTPS Location with the exact `/v1/realtime/calls/{call_id}` path before being returned. The adapter MUST retain a bounded, expiring, memory-only binding scoped to the local key and primary account and permit only one active attachment per call. Attachments MUST connect to `wss://api.openai.com/v1/live/{call_id}`, preserving the remaining raw query string and rejecting query `call_id`. HTTP and WebSocket redirects MUST NOT be followed.

#### Scenario: Successful call attaches

- **WHEN** OpenAI returns a valid successful call response
- **THEN** the status, body, Location, and allowed headers are returned without reinterpretation
- **AND** the sideband for that bound call authenticates as the same account

#### Scenario: Unsafe or unknown call

- **WHEN** a successful response has no valid Location, or attachment is unknown, expired, cross-key, or already active
- **THEN** the operation fails without exposing or replaying the created call or attaching another identity

### Requirement: Streaming cleanup and diagnostics are bounded

The adapter MUST relay text and binary messages unchanged with bounded message size, negotiate only client-offered upstream-selected subprotocols, preserve valid close codes and bounded reasons, and avoid a whole-session or receive-idle timeout. On either-peer close, failure, cancellation, or shutdown it MUST cancel and await paired relay tasks and close owned sockets within a bounded cleanup interval. It MUST log lifecycle duration, direction, close code, and fixed failure categories without tokens, raw call ids, queries, email, account ids, SDP, transcripts, audio, frame bodies, or exception details.

#### Scenario: Peer closes or transport fails

- **WHEN** either peer closes normally, abruptly disconnects, or the service shuts down
- **THEN** the opposite socket and all owned relay tasks are cleaned up
- **AND** content-free diagnostics identify the stage and close category

### Requirement: Installation is recoverable

Installation instructions MUST pin the existing selected ChatGPT identity, start the adapter separately from codex-lb, verify health before changing voice URLs, preserve a private configuration backup, and modify only the two voice overrides. Documentation MUST explain that renewed credentials are supplied by Codex, a client restart may be needed, voice usage accrues to the primary account, and WebRTC audio remains direct to OpenAI. Rollback MUST restore only the voice overrides without reverting unrelated newer settings.

#### Scenario: Restore pooled voice

- **WHEN** the operator rolls back the adapter configuration
- **THEN** the original voice override values are restored and the standalone service can be stopped
- **AND** unrelated settings and the running codex-lb service remain intact
