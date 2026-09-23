## ADDED Requirements

### Requirement: Canonical model-not-found rejection uses safe account recovery

The Responses proxy MUST recognize upstream error code `model_not_found` with the whitespace-normalized message "The model `<model>` does not exist or you do not have access to it." for the exact requested model as an account/model rejection eligible for the existing single replacement-account retry. This behavior MUST apply to native WebSocket, HTTP streaming, and HTTP bridge requests. Recovery MUST preserve the requested model and API-key scope, exclude the rejecting account for that retry, and preserve existing file-ownership and continuation replay constraints. The proxy MUST NOT replay accepted work or work with upstream output. When no replacement can be selected, the original upstream rejection MUST remain the client-visible error. A rejection with a different model or unrelated message MUST NOT qualify through this classifier.

#### Scenario: New model executes on an eligible replacement

- **WHEN** a fresh request for `gpt-6-sol` or `gpt-6-luna` receives the canonical rejection before acceptance
- **AND** another eligible account is available
- **THEN** the proxy retries the same model once on a different account
- **AND** a successful replacement response reaches the client without the first rejection

#### Scenario: No replacement is available

- **WHEN** a canonical model-not-found rejection qualifies for recovery but no replacement account can be selected
- **THEN** the proxy returns the original model-not-found error

#### Scenario: Unsafe or unrelated errors do not replay

- **WHEN** a request is file-pinned, has an unverified owner-bound continuation, has already been accepted, or has produced upstream output
- **THEN** a canonical model-not-found rejection does not trigger cross-account replay
- **WHEN** a model-not-found error names another model or contains an unrelated message
- **THEN** that error does not trigger account/model recovery
