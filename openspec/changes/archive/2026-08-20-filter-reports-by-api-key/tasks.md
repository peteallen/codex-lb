## 1. Backend report filtering

- [x] 1.1 Add repeatable `api_key_id` input to the Reports route and thread typed API-key IDs through the service.
- [x] 1.2 Apply API-key IDs to every report condition, daily aggregate, speed median, distribution, and comparison-eligibility query.
- [x] 1.3 Add backend regression coverage for one key, multiple keys, combined filters, and omitted-filter behavior through repository, service, and API paths.
- [x] 1.4 Document API-key-filtered conversation counts as raw-retention-bound, consistent with the existing filtered Reports contract.

## 2. Reports page filter

- [x] 2.1 Add API-key filter state and repeated query serialization to the Reports API hook with focused tests.
- [x] 2.2 Load the shared API-key catalog, render name/prefix options in the Reports multi-select, preserve stale selected IDs, and include catalog failures in Retry.
- [x] 2.3 Add localized API-key filter and error labels for every supported dashboard locale.
- [x] 2.4 Add component and page regression coverage for selection, option labels, stale values, request refetching, and non-blocking catalog errors.

## 3. Validation

- [x] 3.1 Run focused backend Reports tests and the relevant frontend Reports test suite.
- [x] 3.2 Run backend lint/type checks, frontend lint/type/build checks, and strict OpenSpec validation.
- [x] 3.3 Exercise the Reports API-key filter in the rendered dashboard and record before/after evidence for a dashboard-visible change.
