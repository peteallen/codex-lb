## Evidence and example

On 2026-09-22, the persisted catalog advertised `gpt-6-sol` and `gpt-6-luna` for all five active accounts. Request logs showed two successful Sol requests on one account and ten canonical `model_not_found` errors on another. The failing remote client used the native Responses WebSocket route. Discovery was functioning; the shared recovery classifier did not recognize this error envelope.

For example, a fresh Sol request rejected before `response.created` can safely retry the identical model on another eligible account. A file-owned or unverified response continuation cannot be moved. Existing bounded recovery is reused; no new inference about lasting model entitlement is stored.

Official model reference: https://learn.chatgpt.com/docs/models
