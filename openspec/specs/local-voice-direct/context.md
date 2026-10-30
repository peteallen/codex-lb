# Local Voice Direct Context

## Purpose and decision

This optional helper separates voice call setup and control from the account pool while ordinary model requests keep using codex-lb. It supports the installed official client's private route shape; WebRTC audio already travels directly to OpenAI. It is a diagnostic isolation option, not evidence that the load balancer caused choppy audio or disconnected calls.

Codex CLI `0.158.0-alpha.2.1` includes `experimental_realtime_ws_base_url` and `experimental_realtime_webrtc_call_base_url`. The upstream source reviewed at `openai/codex` commit `e07e58c8429019de78b138d7138deaaf7f3ef22c` applies those URL overrides after deriving authentication from the selected provider (`core/src/client.rs`, `core/src/realtime_conversation.rs`, and `model-provider/src/auth.rs`). Pointing the URLs straight at OpenAI would therefore send the provider's proxy key. The adapter replaces that credential with the explicitly selected existing ChatGPT identity.

## Boundaries and example

With model calls on `http://127.0.0.1:2455/backend-api/codex`, run a separate adapter on `127.0.0.1:2456` and set both voice URL overrides to `http://127.0.0.1:2456/backend-api/codex`. The adapter validates the existing local provider bearer, creates a call at `chatgpt.com`, and attaches its control WebSocket at `api.openai.com/v1/live/{call_id}` with the same selected account. It never selects or decrypts a pooled account, imports the base application, or writes its database.

The installed source copy and LaunchAgent are independent of codex-lb, although they use the existing Python environment. Removing that environment breaks the helper. Voice usage belongs to the selected ChatGPT account and does not enter the pooled dashboard's request history. No new Platform API key is needed.

## Credentials and failures

The selected email and account id are pinned at installation. Each call/attachment rereads the official login and local provider key. Fresh credentials for the same account are accepted; expired, mismatched, malformed, or missing credentials produce fixed errors. Local claim checks establish consistency with the selected login; OpenAI validates the token. The helper deliberately never rotates Codex's shared refresh token. If Codex has not renewed the login, sign into that same account again.

Bindings expire after an hour and are bounded to 32 outstanding calls, including in-flight creations. They are process-local digests. A restart requires a new call. Duplicate-active, cross-key, expired, or unknown attachments fail closed. Upstream redirects and automatic call replay are disabled. Payload/frame size and shutdown cleanup are bounded; an established WebSocket has no whole-session or receive-idle timeout.

Logs contain only fixed categories, close direction/code, and duration. Tokens, account identity, call ids, queries, SDP, audio, transcripts, close reasons, and exception text stay out of logs. Readiness checks local credentials only; a successful OpenAI account probe establishes authentication/connectivity but does not prove voice quality.

## Operation and rollback

Follow [the user guide](../../../docs/live-voice.md#optional-local-voice-bypass). Verify the helper is ready before applying URLs with `scripts/codex_voice_config.py`. Its private backup retains the old voice values; selective restoration preserves unrelated later configuration edits. Restart the official client to load the changed settings and start a fresh call. Do not restart codex-lb for this change.
