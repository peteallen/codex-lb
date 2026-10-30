# Current quota regimes and operator probes

The current quota selection requirements are in [spec.md](spec.md#requirement-current-monthly-quota-excludes-superseded-observations).

A retained monthly sample can belong to a previous quota regime. Current readers
compare it with complete primary/secondary observations using the existing
five-second same-fetch margin. History remains intact. Missing metadata cannot
prove a transition, so it does not erase a monthly observation.

For example, a Pro account with an old monthly sample at zero percent used and
a newer weekly sample at 100 percent used displays Weekly 0% remaining. The old
monthly allowance cannot hide current weekly exhaustion from probe settlement or
routing. A newer monthly-only observation is still supported.

Force Probe sends a supported minimal Codex Responses request, then refreshes
usage. It cannot replenish quota. A rejected upstream request is reported as an
error in the UI, even though the local endpoint successfully returned a result.
