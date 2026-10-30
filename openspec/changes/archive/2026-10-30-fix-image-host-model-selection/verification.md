# Verification

## Automated checks

- `PYTHONPATH=. /Users/pete/workspace/codex-lb/.venv/bin/python -m pytest tests/unit/test_host_models.py tests/unit/test_images_translation.py -q` — 39 passed.
- `PYTHONPATH=. /Users/pete/workspace/codex-lb/.venv/bin/python -m pytest tests/integration/test_proxy_images.py -q` — 57 passed.
- Ruff check and format checks passed for the changed Python files.
- `ty check` passed for the changed application and test files using the shared absolute interpreter. The worktree-local `.venv/bin/python` hook was unavailable, so the commit hook skipped only its duplicate ty invocation.
- OpenSpec validation with OpenSpec 1.6.0 — 49 specs passed.

## Product-path coverage

Integration tests cover canonical and Codex-native generation, multipart
edits, Codex JSON data-URL edits, public-model preservation, and authoritative
catalog suppression of `gpt-5.5` with successful selection of `gpt-5.6-luna`.

## Live diagnostic boundary

A separate read-only diagnostic through the running proxy sent an internal
Responses request with host `gpt-5.6-luna` and the `gpt-image-2`
`image_generation` tool. It returned HTTP 200 and a valid PNG in 11.65 seconds.
This confirms upstream tool support for that host at the time of testing. It
does not verify the post-deployment native route, browser rendering, or other
providers; those require the later deployment check.
