# Verification

## Completeness and design

The shared pool/account timeline replaces the diagnostic-heavy default card.
It follows the supplied mockup: blue availability, brown labeled pool gaps,
neutral account exhaustion, reset diamonds and shared reset offsets. Evidence,
exclusions and limitations are inside one closed-by-default Details disclosure.

The compact visual coverage requirement and all three scenarios are covered by
component and browser checks: incomplete pool remains unknown; independent
account intervals end at reset; stale accounts have no available interval;
excluded accounts remain in Details; evidence opens through the shared control.
Timeline descriptions include clipped interval dates and unknown spans.

## Local checks

- 141 focused frontend tests passed, including 8 coverage component tests.
- Frontend typecheck, lint and production build passed.
- Eight screenshot scenarios passed, covering ready desktop/mobile, learning,
  limited, legacy compatibility, and compact light/dark crops.
- Five included accounts fit in 398 CSS pixels at desktop width. Narrow view
  has no horizontal overflow. Details starts closed.
- Strict OpenSpec change validation and all 50 main specs passed.
- Whitespace validation passed.

`before.jpg` preserves the prior noisy layout. `after.png` shows the compact
layout with synthetic accounts; the full screenshot set lives in
`docs/screenshots/dashboard-weekly-coverage-*`.

## Local deployment

Selective UI, documentation and screenshot files were copied from the feature
worktree to the running checkout. The tested immutable static assets were
installed before swapping index.html. Original rollback backups and unrelated
working-tree changes were preserved. No backend code changed or service restart
was required.

The local service returned HTTP 200 with readiness `ok`. The served dashboard
index and all 20 directly referenced assets matched the tested build. Index
SHA-256: `5af89bb3be11d90b756516fec0f4961252fb82ad1e8132ee4bb2bb04c12e5afb`.
The authenticated live dashboard rendered five included account rows at 398px
high, versus 1,473px before deployment, with Details closed. Its pool remained
unavailable as required by the unchanged estimator evidence.

The existing rollback script passed its integrity check after deployment.
