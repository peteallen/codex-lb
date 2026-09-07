## ADDED Requirements

### Requirement: Current text-model API estimates include Astra and Daybreak

The pricing registry MUST recognize the official text-model rates verified September 4, 2026, including `gpt-6-astra`, `gpt-5.6-cyber`, `gpt-5.5-cyber`, `gpt-daybreak-blue-latest`, `gpt-daybreak-red-latest`, `chat-latest`, GPT-5 Mini/Nano/Pro, GPT-4.1, GPT-4o, and the o-series. Exact models MUST take precedence over snapshot aliases. Unpublished models including GPT-5.3 Codex Spark MUST remain unpriced rather than inherit another model's rate.

Astra Standard input/cached/output rates MUST be `10 / 1 / 50` USD per million tokens through 272,000 input tokens and `20 / 2 / 75` above that boundary. Fast/priority MUST use twice those rates; Flex MUST use half those rates. Daybreak Blue MUST resolve to Sol; Daybreak Red MUST resolve to GPT-5.6 Cyber at `12.5 / 1.25 / 75` Standard rates. Existing supported model rates MUST remain consistent with the verified official table.

#### Scenario: Astra Fast long context
- **WHEN** an Astra Fast request reports 300,000 input, 50,000 cached input, and 100,000 output tokens
- **THEN** its estimate is `$25.20`

#### Scenario: Spark has no published API rate
- **WHEN** pricing resolves `gpt-5.3-codex-spark` or its dated snapshot
- **THEN** no API rate is returned

### Requirement: Reported cache writes contribute to API cost

Astra and GPT-5.6 cache-write tokens MUST be charged at 1.25 times the effective uncached input rate, including tier and long-context selection. Cache-read, cache-write, and ordinary-input counts MUST NOT overlap or exceed reported total input. Missing counts MUST NOT result in inferred writes. Cache-write cost MUST be included in the existing input-cost segment and API-key completed-usage settlement.

#### Scenario: Mixed cached and written Astra input
- **WHEN** Standard Astra usage reports 200,000 input, 100,000 cached input, 40,000 cache-write, and 100,000 output tokens
- **THEN** its estimate is `$6.20`, comprising `$1.10` input, `$0.10` cached input, and `$5.00` output

### Requirement: Historical estimate repair preserves aggregate history

A repair command MUST default to dry-run, require an explicit model scope, and price retained rows using current rates and retained usage. Applying repairs MUST atomically mirror cost changes into every aggregate that already folded those rows, using the fold-state lock. It MUST preserve custom model-source costs, pruned historical aggregate contributions, and API-key enforcement counters. Repeating the same repair MUST make no further changes. Missing historical cache-write data MUST remain unknown.

#### Scenario: Previously unpriced Astra becomes visible in folded totals
- **WHEN** an operator applies a repair to a retained Astra row with null cost that was already folded
- **THEN** the row and corresponding hourly, demand, account, and API-key aggregate costs reflect the new estimate
- **AND** unrelated and pruned historical contributions are unchanged

#### Scenario: Preview is read only
- **WHEN** the repair command runs without its apply option
- **THEN** it reports proposed changes without persisting row or aggregate changes

## MODIFIED Requirements

### Requirement: Represented OpenAI model pricing matches the current published rates

For the additional GPT-5 models represented by the canonical pricing registry,
the system MUST use the USD-per-1M-token rates published on the official
OpenAI API pricing page on September 4, 2026. Each triplet is uncached input /
cached input / output; a dash means the published table has no rate for that
dimension or context tier.

| Model | Standard short | Standard long | Fast short | Flex short | Flex long |
| --- | --- | --- | --- | --- | --- |
| `gpt-5.5` | `5 / 0.50 / 30` | `10 / 1 / 45` | `12.5 / 1.25 / 75` | `2.5 / 0.25 / 15` | `5 / 0.50 / 22.5` |
| `gpt-5.5-pro` | `30 / - / 180` | `60 / - / 270` | `-` | `15 / - / 90` | `-` |
| `gpt-5.4` | `2.5 / 0.25 / 15` | `5 / 0.50 / 22.5` | `5 / 0.50 / 30` | `1.25 / 0.13 / 7.5` | `2.5 / 0.25 / 11.25` |
| `gpt-5.4-mini` | `0.75 / 0.075 / 4.5` | `-` | `1.5 / 0.15 / 9` | `0.375 / 0.0375 / 2.25` | `-` |
| `gpt-5.4-nano` | `0.20 / 0.02 / 1.25` | `-` | `-` | `0.10 / 0.01 / 0.625` | `-` |
| `gpt-5.4-pro` | `30 / - / 180` | `60 / - / 270` | `-` | `15 / - / 90` | `30 / - / 135` |

When a request uses an unsupported tier/context combination, cost accounting
MUST fall back to the configured rate for that tier, or to Standard pricing
when no tier-specific rate exists. It MUST NOT derive a new rate from a
generic multiplier. Long-context rates MUST apply only when input tokens
exceed 272,000. Snapshot aliases MUST resolve to the corresponding canonical
registry entry.

#### Scenario: GPT-5.5 Fast usage uses the published short-context rate

- **WHEN** a `gpt-5.5` request uses `fast` or `priority`
- **THEN** the system computes cost using `12.5 / 1.25 / 75` per 1M tokens

#### Scenario: GPT-5.5 Flex long-context usage uses the published rate

- **WHEN** a `gpt-5.5` request uses `flex` and exceeds 272,000 input tokens
- **THEN** the system computes cost using `5 / 0.50 / 22.5` per 1M tokens

#### Scenario: GPT-5.4 Mini unsupported long-context tier falls back safely

- **WHEN** a `gpt-5.4-mini` request exceeds 272,000 input tokens and uses `fast`, `priority`, or `flex`
- **THEN** the system uses the configured short-context rate for that tier
- **AND** it does not invent a long-context multiplier

#### Scenario: GPT-5.4 Pro Flex long-context usage uses the published rate

- **WHEN** a `gpt-5.4-pro` request uses `flex` and exceeds 272,000 input tokens
- **THEN** the system computes cost using `30 / - / 135` per 1M tokens

