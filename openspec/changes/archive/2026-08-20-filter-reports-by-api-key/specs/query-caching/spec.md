## MODIFIED Requirements

### Requirement: Distinct-conversation reads combine the presence rollup with a raw live tail in one statement

The dashboard conversation activity metrics (`conversation_count`, `conversation_request_count`), the dashboard conversation trend buckets, and the UNFILTERED reports summary and per-day conversation counts MUST serve folded history from the presence satellite and the remainder from raw `request_logs`, merged in a single statement per read: the fold watermark joined into both branches of a UNION so the folded segment, its exact raw complement, and the watermark come from one database snapshot, and `COUNT(DISTINCT ...)` deduplicates across the fold boundary. Merged results MUST equal the legacy full-raw aggregation whenever the underlying raw rows still exist. With an epoch or missing watermark the reads MUST degrade to exactly the legacy raw queries (no kill switch). Reports reads carrying account, API-key, model, or useragent filters MUST keep the legacy raw statement (the satellite has no such dimensions), and non-hour-multiple dashboard display buckets MUST keep the full-raw path. This reverses the `add-request-log-usage-rollups` non-goal that kept distinct conversation counts raw-bound: conversation statistics over folded history now survive request-log retention pruning, except the documented raw-bound residues (sub-hour window edges, filtered reports reads, and daily-report day-row membership, which stays raw-driven).

#### Scenario: Switched conversation reads equal legacy reads while raw exists

- **GIVEN** a corpus with conversations spanning hours, blank and NULL conversation ids, warmup kinds, and soft-deleted rows
- **WHEN** each switched conversation read runs with the conversation watermark at epoch, mid-history on an hour boundary, and at the fold target — including states where the hourly and conversation watermarks differ
- **THEN** every result equals the legacy raw-only implementation exactly

#### Scenario: Conversation statistics survive raw pruning

- **GIVEN** folded conversation presence whose source raw rows have been pruned by retention
- **WHEN** the dashboard conversation activity metrics, hour-multiple conversation trend buckets, or the unfiltered reports summary conversation count are read over that period
- **THEN** the distinct-conversation values equal those reported before the pruning (modulo the documented sub-bucket window edges)

#### Scenario: Filtered reports reads stay raw-bound

- **GIVEN** a reports summary or daily read filtered by account, API key, model, or useragent group
- **WHEN** the read executes
- **THEN** it uses the legacy raw statement and reaches only as far back as raw retention keeps rows

#### Scenario: Non-hour-multiple conversation buckets degrade to full raw

- **GIVEN** a conversation trend request with a display bucket that is not a whole multiple of the rollup hour
- **WHEN** the aggregate is calculated
- **THEN** the legacy full-raw query is used unchanged
