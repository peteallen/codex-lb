## Context

The WebSocket replay trimmer currently treats any leading assistant/tool-call items as output already present in `previous_response_id`. A client-created visualization call can therefore be removed while its output remains. The observed request was trimmed from three items to two, but its original body was not retained; a deterministic route-level reproduction is required.

## Goals / Non-Goals

Preserve client-created tool-call dependencies and continue removing proven duplicate calls. Do not change account selection, retries, HTTP bridge handling, or upstream error contracts.

## Decisions

Use the existing continuity state's completed response ID and pending tool-call type map. Only pass that map to the trimmer when the request references exactly that completed response. Remove a leading tool call only when both its call ID and type match the recorded upstream call. Retain other leading calls in order, along with all outputs. This supports function, custom, and apply-patch calls without name-specific exceptions or new state.

Continue the existing treatment of leading assistant/reasoning items and non-replay prefixes. Preserve the original full resend body used by existing recovery logic.

## Risks / Trade-offs

- Missing continuity evidence means a duplicate call may be forwarded. Preserving supplied context is preferable to destructively guessing; matching-response tests verify that proven duplicates still get removed.
- A continuity entry for another response is not evidence. Explicit mismatch tests prevent accidental cross-response trimming.
- The incident cannot be attributed conclusively without its input body. Route tests will establish the independently reproducible defect and fix.

## Migration Plan

No schema or settings changes. Deploy the updated process after tests pass; reversing this code change restores the previous behavior.
