# Model catalog compatibility context

The proxy already serves the upstream Codex catalog through
`GET /backend-api/codex/models` and `GET /v1/models`. Codex desktop 0.159 and
newer has a separate client-side discovery gate for providers that supply an
`env_key` or `experimental_bearer_token`. A custom provider `base_url` alone
does not enable that path, so the client falls back to its bundled catalog and
can hide newly released models even while the proxy endpoint has them.

The supported desktop configuration enables `api_key_model_discovery` and sets
`model_catalog_url` to the proxy's Codex catalog endpoint. This is client
configuration, not a proxy-side model allowlist or a static model table; the
proxy continues to treat its refreshed upstream catalog as authoritative.
