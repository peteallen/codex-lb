## Why

The eventless `response.created` watchdog bounds how long a silent upstream can
hold an HTTP bridge request, but it does not make the affected lane recover.

Three gaps remain after a bounded failure:

1. When the proxy injected the durable session's `latest_response_id` as a
   reattach anchor and upstream accepted the `response.create` and then emitted
   nothing, the durable row keeps that dead anchor. Every later request for the
   lane re-injects it and hangs again, so one upstream behavior change turns into
   an indefinitely repeating failure. Observed 2026-07-23: 30+ consecutive
   anchored fresh creates hung across four accounts and every model, while
   unanchored creates on the same accounts succeeded.
2. The watchdog fails and retires the whole websocket. A sibling request that is
   already streaming downstream on that socket -- which is the only proof the
   socket is still delivering frames -- is destroyed with it.
3. Reader-driven failures have no single caller API key and pass
   `api_key=None`, so every reader-path failure row loses its `api_key_id` and
   the failure cannot be attributed to a key.

## What Changes

- Invalidate a timed-out **proxy-injected** reattach anchor in the durable
  session row, guarded by an exact `latest_response_id` match so a newer anchor
  recorded by a concurrent turn is never clobbered. The next request for the lane
  reattaches unanchored -- the path that kept working throughout the incident.
- Never invalidate a client-supplied `previous_response_id`.
- Tell the affected client that its continuation anchor was dropped, so a retry
  is known to start a fresh turn rather than silently losing server-side state.
- Fail only the unacknowledged requests when a sibling has downstream-visible
  progress, and quarantine the bridge (reconnect requested, retire after drain)
  instead of closing the socket under that stream.
- Fall back to the request's own API key when a reader-driven failure writes its
  request log.
- Keep the upstream watchdog's bounded wait, its existing stuck-gate threshold,
  its fail-closed no-replay boundaries, and its retirement path unchanged. No new
  setting is introduced.

## Impact

- Affected capability: `proxy-admission-control`.
- A lane poisoned by an unresumable reattach anchor self-heals after one bounded
  failure instead of hanging on every subsequent request.
- A concurrent healthy stream on a poisoned websocket survives.
- Reader-path failure rows regain API-key attribution.
- No change to which requests may be replayed: an ambiguously dispatched request
  is still never retried.
