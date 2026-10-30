## Approach

Restore the supplied prototype's shared time scale: one pool row and one slim row per included account. Use muted blue for available quota, brown with a Gap label for pool exhaustion, neutral gray for individual exhaustion, neutral patterned space for unknown time, and a diamond for resets. Keep the top axis to Now and the selected horizon, with shared reset offsets below the rows; nearby reset times share a label. Do not add a per-account outcome column. Every bar has an accessible description; dates and evidence remain available in one keyboard-operable disclosure.

When the pool estimate is incomplete, its row is unknown. Fresh individual projections run only until the current reset; do not fabricate post-reset cycles or transferred demand. A short visible label states that these are independent account paces. Unavailable or stale rows have no reassuring green segment.

Keep the normal desktop card below 400px for five included accounts. Excluded accounts have no default chart row. They remain listed with reasons in Details. There are no repeated account badges, nested cards, percentage gauges, warning boxes or per-row legends. Use the same layout on narrow screens with truncated labels and accessible full descriptions.

## Deployment

Validate visual geometry, semantics and mobile overflow, then copy only changed UI files and rebuild the local static assets. Preserve the existing rollback's original snapshot while updating its deployed-file checksums. Backend restart is unnecessary for a frontend-only change.
