# Verification

## Incident and reproduction

The five screenshot rows at 2026-09-08 03:56:05–03:58:35 UTC all recorded
`previous_response_not_found` as their failure detail, with no response-created
timing. The shared plain HTTP session received a proxy-injected durable anchor
and then retried the same anchor as if client-supplied. The process was stable
at PID 23353 before the repair.

A public-route regression reproduced both collected and streamed HTTP failures
before the fix: 2 failed, 4 passed. After the reconnect eligibility change, all
6 cases pass, including explicit previous-response and turn-state controls.

## Validation

- Relevant bridge integration/unit suites: 704 passed in 67.02 seconds.
- Ruff lint and formatting, focused ty checking, architecture checks, and
  git diff whitespace checks passed.
- Strict OpenSpec validation: all 49 main specs and this change passed.
- Existing deployed overload-recovery files matched their previous manifest;
  existing dirty work was preserved without committing.

## Local rollout

Sent SIGTERM to the existing LaunchAgent so its configured shutdown handling
could run. Its bounded cleanup ultimately hit its exit deadline; launchd
started PID 52580 at 04:09:23 UTC and startup completed at 04:09:27 UTC.
Readiness reports database OK and the process remains stable. Clara completed
three gpt-5.6-sol requests and one gpt-5.6-luna request in the first observed
post-startup sample. No request errors appeared in that sample. This is a
bounded observation, not a guarantee against unrelated upstream failures.

Rollback source, prior dirty patch, candidate hash, test output, spec output,
and deployment observations are in the ignored local directory
`.codex-lb/deploy-backups/implicit-continuity-20260908/`.

At 04:10:44 UTC the expanded sample contained 41 successes and one upstream
`server_is_overloaded` error, with no `stream_incomplete` errors. Clara accounted
for 18 successes (six Sol and twelve Luna) and the overload error.
