## Context

Live requests from the LAN pool tried openai5 and openai6, both rejected Sol, and stopped at the one-replay limit; openai10 successfully served the same remote client. The initial fix was incomplete for multiple rejecting accounts.

## Goals / Non-Goals

Traverse remaining API-key-eligible candidates for exact account/model rejections before acceptance. Preserve generic transient budgets, all replay safety checks, and the original deadline. No account bans, model changes, credential or scope changes.

## Decisions

Use the existing request-local excluded-account set to guarantee progress. Account/model rejections have independent accounting from generic transient retries, like the existing separation for explicit overloads, but rejected accounts never reenter this request's candidate pool. Retain existing lease and API-key reservation ownership and terminal error preservation.

## Risks / Trade-offs

Multiple rejected candidates add latency, bounded by the original deadline and finite eligible pool. Tests must prove at least three-account success, all-rejected termination, no revisits, and unchanged file/continuation/output guards.
