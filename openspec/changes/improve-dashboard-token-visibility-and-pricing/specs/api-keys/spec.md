## MODIFIED Requirements

### Requirement: GPT-5.6 usage cost pricing matches the current published rates

When computing API-key usage, request-log, reservation, or aggregate cost for the canonical GPT-5.6 models, the system MUST use these USD-per-1M-token rates for input, cached input, and output, as published by the official OpenAI API pricing table on August 26, 2026:

| Model | Standard short | Fast/priority short | Flex short | Standard long | Fast/priority long | Flex long |
| --- | --- | --- | --- | --- | --- | --- |
| `gpt-5.6-sol` | `4 / 0.40 / 20` | `8 / 0.80 / 40` | `2 / 0.20 / 10` | `8 / 0.80 / 30` | `16 / 1.60 / 60` | `4 / 0.40 / 15` |
| `gpt-5.6-terra` | `2 / 0.20 / 12` | `4 / 0.40 / 24` | `1 / 0.10 / 6` | `4 / 0.40 / 18` | `8 / 0.80 / 36` | `2 / 0.20 / 9` |
| `gpt-5.6-luna` | `0.20 / 0.02 / 1.20` | `0.40 / 0.04 / 2.40` | `0.10 / 0.01 / 0.60` | `0.40 / 0.04 / 1.80` | `0.80 / 0.08 / 3.60` | `0.20 / 0.02 / 0.90` |

The existing `priority` and `fast` service-tier aliases MUST both use Fast rates. Long-context rates MUST apply only when input tokens exceed 272,000. Model aliases with a version or snapshot suffix MUST resolve to the corresponding canonical table entry.

Batch rates, regional-processing uplifts, and cache-write rates MUST NOT be introduced into this contract without corresponding proxy request and usage fields.

#### Scenario: Sol standard usage uses the current promotional rate

- **WHEN** a short-context Standard request for `gpt-5.6` or `gpt-5.6-sol` has 200,000 input tokens and one million output tokens
- **THEN** the token cost is `$20.80`

#### Scenario: Luna Fast and Flex usage use their short-context tier rates

- **WHEN** a `gpt-5.6-luna` request has 200,000 input tokens, 100,000 cached input tokens, and 1,000,000 output tokens
- **AND** the request uses `priority` or `fast`
- **THEN** the token cost is `$2.444`
- **WHEN** the same usage uses `flex`
- **THEN** the token cost is `$0.611`

#### Scenario: Terra standard usage retains its published rate

- **WHEN** a standard-tier `gpt-5.6-terra` request has 200,000 input tokens and 1,000,000 output tokens
- **THEN** the token cost is `$12.40`

#### Scenario: Terra standard long-context usage uses the current long-context rate

- **WHEN** a standard-tier `gpt-5.6-terra` request has 300,000 input tokens, 50,000 cached input tokens, and 100,000 output tokens
- **THEN** the token cost is `$2.82`

#### Scenario: Sol Fast long-context usage uses the published long-context row

- **WHEN** a `gpt-5.6-sol` Fast request has 300,000 input tokens, 50,000 cached input tokens, and 100,000 output tokens
- **THEN** the token cost is `$10.08`
- **AND** the system does not reuse the short-context Fast rates

#### Scenario: Sol Flex long-context usage uses the published long-context row

- **WHEN** a `gpt-5.6-sol` Flex request has 300,000 input tokens, 50,000 cached input tokens, and 100,000 output tokens
- **THEN** the token cost is `$2.52`

#### Scenario: Versioned aliases use canonical GPT-5.6 pricing

- **WHEN** the requested model is `gpt-5.6-luna-2026-07-13`
- **THEN** cost accounting resolves it to the `gpt-5.6-luna` price entry

## ADDED Requirements

### Requirement: Represented OpenAI models use current published pricing

The system MUST compute costs for the built-in OpenAI models represented by the canonical pricing registry using the prices published by the official OpenAI API pricing table on August 26, 2026. Where that table distinguishes Standard, Flex, Fast, short-context, and long-context rates, the cost calculation MUST select the applicable published input, cached-input, and output rates.

The system MUST NOT infer cache-write, regional-processing, Batch, or modality-specific token charges when the completed-request usage contract does not expose the required billing dimension.

#### Scenario: GPT-5.5 long context uses its published rate

- **WHEN** a Standard GPT-5.5 request exceeds 272,000 input tokens
- **THEN** the system uses the published long-context input, cached-input, and output prices
- **AND** it does not reuse the short-context prices

#### Scenario: GPT-5.4 Mini Fast usage uses its published rate

- **WHEN** a GPT-5.4 Mini request uses `fast` or `priority`
- **THEN** the system uses the published Fast input, cached-input, and output prices

#### Scenario: Published long-context Flex usage uses its explicit rate

- **WHEN** a GPT-5.5, GPT-5.4, or GPT-5.4 Pro Flex request exceeds 272,000 input tokens
- **THEN** the system uses that model's published long-context Flex input, cached-input when available, and output prices
- **AND** it does not derive those prices from a generic multiplier

#### Scenario: Current legacy image model prices remain model-specific

- **WHEN** the registry prices GPT Image 1.5, GPT Image 1, or GPT Image 1 Mini usage
- **THEN** it uses the current published rate mapped through the documented single-input-rate approximation for that exact model
- **AND** it does not reuse GPT Image 2's output price for every image model

#### Scenario: Unsupported billing dimensions are not guessed

- **WHEN** the official table includes a cache-write, regional, Batch, or modality-specific dimension not present in completed-request usage
- **THEN** the cost calculation omits that dimension
- **AND** the system does not fabricate a token count or processing mode

#### Scenario: Distinct model variants do not inherit a family price

- **WHEN** a model ID names a distinct public variant that is not represented by an explicit canonical registry entry
- **THEN** cost accounting leaves that model unpriced
- **AND** a broad family wildcard does not silently assign a neighboring model's price

#### Scenario: Supported Spark compatibility uses the Codex row

- **WHEN** the repo-supported `gpt-5.3-codex-spark` compatibility ID is priced
- **THEN** it resolves explicitly to the published `gpt-5.3-codex` rates
