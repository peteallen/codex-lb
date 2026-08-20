## Why

The upstream Codex Responses WebSocket rejects a `response.create` frame above
its byte budget. Historical context can be slimmed to get under it, but a turn
whose *current* tool output is itself oversized has nothing left to slim: the
body is already a minimal delta consisting of the tool outputs for the calls the
model just made, anchored by a client-supplied `previous_response_id`.

Such a turn is rejected with `payload_too_large`, which is a dead end for the
client -- reducing images or compacting the thread cannot shrink the current
command result. Upstream HTTP has no equivalent frame budget and accepts exactly
the same body.

Two adjacent defects surface on the same path:

- The HTTP streamer re-derives previous-response ownership and the owner-lookup
  session id from HTTP headers. A websocket-originated turn has already resolved
  both, so re-deriving loses them: the continuation can be attempted as a
  cross-account request and its request log detaches from its conversation.
- When a hard owner-bound continuation gets a pre-visible error from its owner,
  the retry loop penalizes and excludes the owner and then reports the next
  selection miss as `previous_response_owner_unavailable`. The client sees a
  misleading routing error instead of the owner's real one -- for example
  `Unsupported parameter: previous_response_id`.

## What Changes

- Relay one oversized anchored turn over upstream HTTP when, and only when, it
  carries a client-supplied `previous_response_id`, its input is entirely
  current tool outputs, and the projected wire frame really exceeds the
  websocket budget. Every other oversized anchored turn keeps the existing
  `payload_too_large` rejection.
- A proxy-injected reattach anchor is never eligible: that body was rewritten
  against a durable anchor the client never sent, so it is not a delta the client
  could reproduce.
- Keep the turn a websocket turn downstream -- same socket, same event shapes,
  Codex keepalives while pre-created -- while recording `upstream_transport=http`.
  Keep it out of the shared socket's pending set, since none of its correlation
  state belongs there.
- Hand the websocket-resolved previous-response owner and owner-lookup session id
  to the HTTP streamer instead of re-deriving them from headers, and attach that
  session id to owner-unavailable request logs.
- Surface the owner's original pre-visible error for a hard owner-bound
  continuation that has no verified fresh replay body, instead of rewriting it as
  `previous_response_owner_unavailable`.
- Hold the terminal frame until the upstream stream is drained, and settle the
  gate, reservation and relay task on every exit including client disconnect and
  `response.cancel`.

## Impact

- Affected capability: `responses-api-compat`.
- A turn whose current tool output exceeds the websocket frame budget now
  completes instead of failing with an unactionable error.
- No ambiguously dispatched request becomes replayable: the fallback decision is
  made before any upstream dispatch, and the terminal no-replay rules are
  unchanged.
- Hard owner-bound continuations report their real upstream error.
