## Context and decision
Cooldown expiry is permission to attempt recovery, not evidence that overload has recovered. Track the latest overload timestamp separately from the eligibility deadline. Preserve its bounded escalation count through successes and selector deadline cleanup for a 15-minute quiet window, then reset lazily on the next overload. This avoids a stream of failed 30-second probes without permanently removing an account.

The window is a fixed internal default. All transports already share `record_overload`; replay eligibility and settlement remain unchanged. In particular, missing HTTP response-created timing in request logs is not proof of non-acceptance and does not authorize replaying a failed accepted request.

## Validation and rollout
Use deterministic clock tests and public HTTP requests with real account selection. Prove recurrence after expired holds, intervening success, maximum cooldown, reset after quiet time, alternate routing, and existing owner-bound/cancellation behavior. Preserve dirty work and deploy the validated change locally.
