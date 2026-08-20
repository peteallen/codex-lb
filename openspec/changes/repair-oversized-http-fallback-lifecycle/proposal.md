# Repair oversized HTTP fallback lifecycle

## Why

The oversized Responses WebSocket fallback is now a real upstream transport
boundary. Its routing, capability lineage, drain behavior, and reservation
cleanup must match the ordinary WebSocket path before it is enabled in the
release branch.

## What Changes

- Preserve Trusted Cyber capability requirements when the fallback selects an
  upstream account.
- Persist capability lineage aliases before exposing a fallback response ID.
- Keep active HTTP fallback tasks visible to graceful WebSocket drain checks.
- Release the API-key reservation and response-create admission when fallback
  setup is cancelled before a relay task takes ownership.
- Add regression coverage for each lifecycle boundary.

## Impact

This is a proxy lifecycle and compatibility hardening change. It adds no
settings or migrations and does not change the Reports API-key filter.
