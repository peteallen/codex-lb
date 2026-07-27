- [x] Classify the compact terminal item into required, optional-omittable, and
      absent cases instead of unconditionally requiring the last index.
- [x] Keep an oversized optional non-state tool tail omitted atomically and
      represented by the trim marker.
- [x] Keep state tools, unresolved calls, required text, apply-patch records,
      canonically classified side effects, and continuity anchors fail-closed.
- [x] Reuse the existing side-effect anchor classifier rather than adding a
      second side-effect notion, and keep historical side-effect protection.
- [x] Pair calls and outputs by protocol variant and occurrence, and match a
      terminal output to its own occurrence only.
- [x] Prune stale local occurrences of an unmatched continuity-anchored terminal
      output's call id, exempting required anchors and protected side effects.
- [x] Make the trim marker truthful about omitted terminal context.
- [x] Add unit coverage for omission, marker-budget framing, both continuity
      anchor fields, protocol-variant pairing, consumed occurrences, and every
      fail-closed tail; prove the new behavior tests fail on the unmodified
      trimming helper.
- [x] Add a route-level compact regression proving the omission and the truthful
      marker at `POST /backend-api/codex/responses/compact`.
- [x] Run focused unit/integration suites, lint, format, type checks, and strict
      OpenSpec validation.
