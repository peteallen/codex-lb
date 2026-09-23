## Context

The repository orders request logs by `requested_at DESC, id DESC`. Retry attempts intentionally share request IDs; the table currently uses `requestId` as its React key. The API omits the database row ID.

## Goals / Non-Goals

**Goals:** Preserve persisted attempt identity through the API and React reconciliation.

**Non-Goals:** Change retry policy, sort logs in the browser, or diagnose the upstream model rejection through UI behavior.

## Decisions

- Expose the existing database primary key as required string `logId`, and use it as the row key. Strings avoid JavaScript integer precision limits. No migration or new persisted state is required.
- Keep `requestId` unchanged for correlation and request details.
- Reject a composite key based on request ID, account ID, and timestamp: the repository permits distinct rows with all three fields equal, and existing rollup tests exercise that case.
- Test actual rendered row order and count through successive refreshes, including insertion and pagination/removal. Test the listing route for distinct stable IDs even with identical correlation fields.

## Risks / Trade-offs

- New frontend assets require the updated backend response contract. Deploy the backend before publishing the new assets; older frontends ignore the additive field.
- Browsers with an existing dashboard tab retain its old JavaScript until reload. Verify the served build and instruct the user to refresh.
- This fixes display reconciliation, not the underlying upstream errors; real retries remain visible.
