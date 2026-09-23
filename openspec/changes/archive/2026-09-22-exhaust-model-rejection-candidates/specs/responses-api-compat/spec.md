## MODIFIED Requirements

### Requirement: Canonical model-not-found rejection uses safe account recovery

The Responses proxy MUST recognize upstream error code `model_not_found` with the whitespace-normalized message "The model `<model>` does not exist or you do not have access to it." for the exact requested model as an account/model rejection eligible for safe replacement-account recovery. This behavior MUST apply to native WebSocket, HTTP streaming, and HTTP bridge requests. Recovery MUST continue through remaining eligible accounts after consecutive canonical account/model rejections, within the original request deadline. Each rejecting account MUST be excluded from further attempts for that request. Account/model rejection retries MUST NOT consume the generic transient replay allowance, and MUST stop when no eligible account remains or the deadline expires. Recovery MUST preserve the requested model and API-key scope, exclude the rejecting account for that retry, and preserve existing file-ownership and continuation replay constraints. The proxy MUST NOT replay accepted work or work with upstream output. When no replacement can be selected, the original upstream rejection MUST remain the client-visible error. A rejection with a different model or unrelated message MUST NOT qualify through this classifier.

#### Scenario: New model executes on an eligible replacement

- **WHEN** a fresh request for `gpt-6-sol` or `gpt-6-luna` receives the canonical rejection before acceptance
- **AND** another eligible account is available
- **THEN** the proxy retries the same model on a different eligible account
- **AND** a successful replacement response reaches the client without the first rejection

#### Scenario: No replacement is available

- **WHEN** a canonical model-not-found rejection qualifies for recovery but no replacement account can be selected
- **THEN** the proxy returns the original model-not-found error

#### Scenario: Unsafe or unrelated errors do not replay

- **WHEN** a request is file-pinned, has an unverified owner-bound continuation, has already been accepted, or has produced upstream output
- **THEN** a canonical model-not-found rejection does not trigger cross-account replay
- **WHEN** a model-not-found error names another model or contains an unrelated message
- **THEN** that error does not trigger account/model recovery

#### Scenario: Multiple accounts reject a released model

- **GIVEN** two eligible accounts reject the requested model before acceptance
- **AND** a third account supports it
- **WHEN** a fresh request is routed through the pool
- **THEN** the proxy excludes both rejecting accounts and completes on the third
- **AND** no account is tried twice for that request

#### Scenario: All eligible accounts reject

- **WHEN** every eligible account returns an account/model rejection
- **THEN** the proxy stops after trying each eligible account at most once
- **AND** returns the last upstream model rejection without repeating the pool
