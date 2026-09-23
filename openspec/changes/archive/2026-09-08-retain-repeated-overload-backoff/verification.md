# Verification

## Incident
All 16 overload errors recorded between 04:00 and 04:25 UTC on September 8 came
from openai8 across Sol, Astra, and Luna. The screenshot request used upstream
HTTP due to an inline image. Its missing response-created timing does not prove
non-acceptance: direct HTTP request logs do not write that timing. No replay
safety gates were weakened or account status changed.

## Reproduction and checks
Two deterministic recurrence tests failed before the repair (30 seconds instead
of 60). After repair, the public HTTP image-request test proves that accepted
failures are surfaced without replay, recurrent holds escalate after expiry,
and independent work uses a healthy alternative. Intervening successes, bounded
history and cooldown, and 15-minute quiet reset are covered.

106 relevant overload, transient retry, ownership and cancellation tests passed.
Two suite warnings remain: existing Starlette/httpx deprecation and a SQLAlchemy
connection cleanup warning in WebSocket overload testing. Ruff, focused ty,
architecture, whitespace, strict change validation and all 49 main specs passed.

## Deployment
Preserved all earlier dirty work and saved the two prior runtime files plus
candidate hashes under `.codex-lb/deploy-backups/repeated-overload-20260908/`.
Sent SIGTERM to the local LaunchAgent. Its bounded drain exhausted cleanup time;
launchd started PID 59324 at 04:30:58 UTC and startup completed at 04:31:02 UTC.
Readiness reports database OK. Initial post-startup requests completed on other
accounts; observed client cancellations are recorded separately. Runtime
recurrence history starts fresh at process startup. This observation does not
prove that provider overloads have ceased.
