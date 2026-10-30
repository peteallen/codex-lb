## ADDED Requirements

### Requirement: Images routes select a routable internal host model

The Images generation and edit routes MUST select the first model in the
ordered internal host candidate list that has non-empty model-registry plan
visibility and is not suppressed by the authoritative registry. The candidate
list MUST be ordered as `gpt-5.6-luna`, `gpt-6-astra`, and `gpt-5.5` so current
catalogs prefer the GPT-5.6 host, catalogs that expose the documented GPT-6
image-tool host can fall through, and older catalogs retain compatibility. If
no candidate qualifies, the routes MUST use the deterministic first candidate
and let existing account-selection error handling apply. The selected host model MUST NOT replace the public `gpt-image-*` model
in request validation, image-tool configuration, responses, or accounting.

#### Scenario: Bootstrap catalog selects the preferred host

- **WHEN** the registry has no authoritative suppression for
  `gpt-5.6-luna`
- **THEN** both generation and edit routes use `gpt-5.6-luna` as the outer
  Responses model
- **AND** the image-generation tool still carries the requested `gpt-image-*`
  model

#### Scenario: A suppressed preferred host falls through

- **WHEN** the registry suppresses `gpt-5.6-luna` and advertises another
  candidate with non-empty plan visibility
- **THEN** both routes use the first remaining eligible candidate

#### Scenario: No host candidate is eligible

- **WHEN** every internal host candidate is absent or suppressed
- **THEN** both routes use the deterministic first candidate and preserve the
  existing downstream `no_plan_support_for_model` or upstream error behavior
