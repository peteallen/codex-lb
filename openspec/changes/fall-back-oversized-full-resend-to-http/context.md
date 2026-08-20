## Failure shape

The motivating request had no `previous_response_id`. Its final websocket wire
body was 17,579,656 bytes, of which 17,578,317 bytes were `input`. Eighteen
inline screenshots accounted for 17,212,670 bytes. All image-bearing tool
outputs followed the last user message, so the existing history slimmer kept
them as recent context and the 15 MiB websocket guard rejected the request.

## Decision

Use the existing direct upstream HTTP relay for an oversized request whose
final body has neither a `previous_response_id` nor a nonblank `conversation`.
The body is already a complete request, so changing only its upstream transport
preserves more information than replacing recent screenshots with omission
notices. The decision is made from the final serialized body, including
projected per-account metadata, and before any upstream websocket connection or
send.

Client-anchored requests still need the narrower current-tool-output proof.
Proxy-injected anchors remain ineligible because their bodies were rewritten
against state the client did not provide.

The transport hop preserves the WebSocket path's routing evidence: a turn-state
generated for the current handshake remains a placeholder rather than becoming
a hard owner, and a resolved input-file owner crosses the boundary without a
second lookup. Reservation ownership moves only after routing preflight reaches
the stream settlement guard. A second unanchored full resend remains blocked
while the relay is active, while an anchored concurrent request stays possible
and keeps connection-level cancellation when it is newer.

## Example

A websocket request contains a full user turn followed by several completed
image-inspection calls and their inline screenshot outputs. It has no
`previous_response_id`, and its projected frame is 17 MiB. codex-lb sends the
unchanged request over upstream HTTP and relays the normal response events over
the same downstream websocket.
