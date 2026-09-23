## Context

See proposal.md. Live model discovery already advertises both new model slugs for all active accounts. Execution nevertheless rejected Sol on one account and succeeded on another.

## Goals / Non-Goals

Extend existing safe recovery across all Responses transports. No aliases, model substitution, new routing configuration, negative entitlement cache, or persistent account-health changes are introduced.

## Decisions

Extend the shared exact-message classifier, keeping its callers' existing pre-acceptance, replay-count, file, continuation, exclusion, lease, and error-envelope handling. Match the error code and requested model as well as the canonical message. Treating every 404 or every invalid request as recoverable would misclassify payload defects. Updating static model names would not fix this incident because the live catalog already contains them.

## Risks / Trade-offs

An actually nonexistent model can also produce this envelope; the existing one-replacement limit bounds additional work and preserves failure when no account serves it. Catalog publication does not prove execution access. The change deliberately avoids creating durable negative access claims during rollout.

## Migration Plan

Run regression coverage, sync the requirement and context, archive the verified change, then restart the existing local LaunchAgent and check readiness. Rollback only this classifier extension while preserving pre-existing local patches.
