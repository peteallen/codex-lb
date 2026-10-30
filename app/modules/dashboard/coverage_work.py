"""Measured work accounting for weekly quota coverage.

Weekly quota responses expose a percentage of an account's current window,
not an absolute allowance.  Coverage therefore learns an account-specific
allowance from a local, additive work unit.  The unit is deliberately simple:
one unit is one million measured input and output tokens.

The model, service tier, context classification and provider pricing catalog
are retained as request metadata for other features, but none of them gate or
weight coverage work.  Cached input and cache-write counts are subsets of
input and are therefore not added separately.
"""

from __future__ import annotations

from math import isfinite

from app.modules.dashboard.coverage_types import CoverageWorkBucket

TOKENS_PER_WORK_UNIT = 1_000_000.0


def estimate_work_units(bucket: CoverageWorkBucket) -> float | None:
    """Return the measured work in one aggregated bucket.

    A bucket is usable only when all requests in it have complete, valid
    input/output accounting.  Optional cache fields are validated when
    present, but are not added because they describe portions of input.
    Unknown model names, service tiers and context metadata do not affect the
    result.
    """

    if bucket.request_count <= 0:
        return 0.0
    if bucket.missing_usage_count > 0:
        return None
    if bucket.input_tokens is None or bucket.output_tokens is None:
        return None
    if (
        bucket.input_tokens < 0
        or bucket.output_tokens < 0
        or (bucket.cached_input_tokens or 0) < 0
        or (bucket.cache_write_tokens or 0) < 0
    ):
        return None

    work_units = (float(bucket.input_tokens) + float(bucket.output_tokens)) / TOKENS_PER_WORK_UNIT
    if not isfinite(work_units) or work_units < 0:
        return None
    return work_units
