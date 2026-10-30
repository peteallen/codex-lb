# Codex Live Voice

codex-lb keeps Codex Live Voice call creation and its control sideband on the same ChatGPT account. This matters in an account pool: the account that successfully creates a call is the only account that can safely join its sideband.

!!! note "Private Codex compatibility"
    This capability supports the private routes used by the installed Codex app. It does not implement OpenAI's public Realtime API, `POST /v1/realtime/calls`, or `POST /v1/realtime/client_secrets`, and it does not proxy WebRTC media.

## Requirement: a registered proxy key

Live Voice routes always require an existing registered [proxy API key](api-keys.md), even when ordinary proxy API-key authentication is disabled. Missing or unregistered keys are rejected before codex-lb selects or contacts an upstream account.

No new `CODEX_LB_*` setting, migration, dependency, or setup step is required. Operators who do not use Live Voice can continue running the base proxy and dashboard unchanged.

## Supported private routes

A compatible Codex client uses these routes as one account-bound workflow:

- `POST /backend-api/codex/realtime/calls` creates the call.
- `WS /backend-api/codex/{call_id}` joins through the current installed-app form for bounded `rtc_...` or canonical UUID call ids; unrelated Codex WebSocket paths keep their ordinary behavior.
- `WS /v1/live/{call_id}` joins through the v3 form.
- `WS /v1/realtime?call_id={call_id}` joins through the legacy form.

codex-lb validates the call id returned in the successful call-creation `Location`, ignoring private query or fragment context after the first `?`, binds it to the final successful account under the caller's proxy key, and routes every supported sideband form back to that exact account. Attachment fails closed if the key, assignment, account state, or ownership binding is no longer valid; codex-lb does not refresh credentials or substitute another account after a call is created.

## Privacy and request history

The ownership record contains only an API-key-scoped digest and the owning account reference. Raw call ids, proxy keys, OAuth tokens, SDP, attestation values, and realtime frame bodies are not stored in that record. Call-creation SDP is excluded from payload traces, and sideband frames are not added to Responses archives.

The dashboard's Recent Requests data accepts the sideband as a typed `realtime_live` WebSocket request. Private call-creation and sideband rows omit account identity, model content, upstream error text, failure metadata, live query text, and credentials. The internal ownership record stays hidden from ordinary sticky-session lists and delete operations.

## Failure behavior

- `401 invalid_api_key` means the request did not carry a registered proxy key.
- `400 invalid_realtime_call_id` means the sideband supplied a malformed or ambiguous call id.
- `503 realtime_call_binding_failed` means a successful upstream call could not be bound safely; codex-lb does not replay that call through another account.

## Optional local voice bypass

The source checkout includes `scripts/codex_voice_direct.py`, a separate loopback adapter for the official Codex client's private voice transport. Use it when you want model requests to remain on codex-lb while voice call creation and control go directly to OpenAI under one existing ChatGPT login. Voice usage belongs to that selected account and no longer appears in codex-lb's request history. WebRTC audio already travels directly between the client and OpenAI; this change does not alter the microphone or media connection, and does not establish that a voice quality problem was caused by the proxy.

The helper supports the current `POST /backend-api/codex/realtime/calls` and `WS /backend-api/codex/{call_id}` shape, verified against Codex CLI `0.158.0-alpha.2.1`. It is optional source tooling, not part of the base service startup. It uses the checkout's existing Python dependencies, with no new proxy setting or database state.

1. Keep the official client signed into the desired ChatGPT account. Its `auth.json` must contain a ChatGPT access token whose email and account id match the identity you select. The selected model provider must have an `experimental_bearer_token` in user-level `config.toml`.
2. Run a separate instance using the checkout's Python environment:

    ```bash
    .venv/bin/python scripts/codex_voice_direct.py \
      --expected-email voice@example.test \
      --expected-account-id '<account id from your existing Codex login>'
    ```

    The helper binds only to `127.0.0.1:2456`. For unattended macOS use, copy the reviewed script to a private application-support directory and register a separate LaunchAgent with these arguments. Use absolute paths to the existing Python environment and copied script, owner-only configuration/log files, and a bounded restart throttle. There are no tokens in the process arguments or LaunchAgent: the helper reads the current provider key and official login locally.
3. Check `http://127.0.0.1:2456/health/ready` for HTTP 200 and `status: ready`. Readiness validates local identity and token expiry; it does not create a call or prove OpenAI connectivity.
4. Save a private backup and change only the two voice overrides:

    ```bash
    .venv/bin/python scripts/codex_voice_config.py enable \
      --backup "$HOME/.codex/config.before-direct-voice.toml"
    ```

    This sets `experimental_realtime_ws_base_url` and `experimental_realtime_webrtc_call_base_url` to `http://127.0.0.1:2456/backend-api/codex`. It preserves the selected model provider, provider bearer, model base URL, and all other settings. The helper refuses to overwrite an existing backup. Restart the official client to ensure it loads both changes, then start a new voice call.

### Credentials and diagnostics

The adapter rereads Codex-managed credentials for each new call and sideband attachment. A renewed access token for the same account is accepted automatically. It does **not** refresh or rotate the shared OAuth refresh token: if the official client has not renewed an expired login, sign into that same account again. An account switch fails closed until the original account is restored or the adapter is deliberately reconfigured. Existing sockets are not terminated merely because the auth file changes.

The helper records fixed failure categories, close direction/code, and duration. It excludes SDP, audio, transcripts, tokens, account identifiers, call ids, queries, and raw exception text. A process restart discards in-memory call bindings, so start a new call after restarting it. Calls are never replayed automatically.

### Rollback

Restore just the original voice override values from the backup:

```bash
.venv/bin/python scripts/codex_voice_config.py restore \
  --backup "$HOME/.codex/config.before-direct-voice.toml"
```

Then restart the official client and stop or unload the separate voice adapter. Selective restoration keeps unrelated settings added since installation; copying the whole old config over the current file is unnecessary. The running codex-lb service does not need a restart.

*Local adapter spec: [local-voice-direct](https://github.com/peteallen/codex-lb/tree/main/openspec/specs/local-voice-direct)*

---

*Spec: [realtime-api-compat](https://github.com/Soju06/codex-lb/tree/main/openspec/specs/realtime-api-compat)*
