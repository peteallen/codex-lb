## Why

Compact trimming currently treats the last input item as an unconditional
fail-closed anchor. A compact trigger commonly follows a very large command
result, so the terminal item is often an ordinary tool call/output pair that is
too big to survive byte-identical. Requiring it makes compaction impossible and
the client receives `responses_compact_input_too_large` for a turn that could
have been compacted safely.

The terminal item is not uniformly load-bearing:

- an `apply_patch`/`exec`/collaboration call or its output records a side effect
  the model already performed, so omitting it rewrites history;
- an unresolved terminal call, a state-tool item, and required text are also
  load-bearing;
- an unmatched terminal output under `previous_response_id` or `conversation`
  continuity is the turn's only new content;
- an ordinary paired output whose call is present locally is *not* load-bearing:
  omitting the whole pair is representable by the trim marker.

Pairing also currently matches by `call_id` alone. One `call_id` can be reused
across the function/custom/apply-patch protocols, so an output can be paired
with an incompatible call variant or with an already-consumed occurrence.

Finally, the trim marker claims "the initial context, most recent context, and
compact state anchors were preserved", which becomes untrue as soon as a terminal
pair is omitted.

## What Changes

- Classify the compact terminal item instead of requiring it unconditionally.
  Only an optional non-state, non-side-effecting terminal tool pair may be
  omitted, and only atomically (call and output together), and only when it
  cannot fit alongside required anchors and the trim marker.
- Keep the historical side-effect protection already in place: side-effect
  anchors identified by the canonical tool-safety classifier remain required and
  are never pruned by terminal-delta handling.
- Pair tool calls and outputs per protocol variant and per occurrence, so a
  reused `call_id` cannot pair an output with an incompatible or already-consumed
  call.
- Under `previous_response_id` or `conversation` continuity, drop stale local
  occurrences of an unmatched terminal output's `call_id` so upstream cannot pair
  the delta with the wrong occurrence. Required anchors and protected side
  effects are exempt.
- Make the trim marker truthful: it no longer promises that the most recent
  context survived.

## Impact

- Affected capability: `responses-api-compat`.
- Oversized compact turns whose only blocker was an ordinary terminal tool pair
  now compact successfully instead of failing.
- State tools, side-effecting calls, unresolved calls, required text and
  continuity anchors still fail closed with
  `responses_compact_input_too_large`.
- Route-level compact behavior is covered so the omission is observable at the
  product path, not only in the trimming helper.
