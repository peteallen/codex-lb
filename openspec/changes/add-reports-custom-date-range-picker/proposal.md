# Add reports custom date range picker

## Why

Operators need quick date filters for common report windows while still being able to inspect an arbitrary date range without editing always-visible raw date fields. The reports toolbar should make `1d`, `7d`, and `30d` fast paths obvious, and keep custom date selection available as a named range picker.

## What Changes

- Replace the reports quick presets with `1d`, `7d`, and `30d`.
- Add a Custom range popover that contains start and end date controls plus a calendar range picker.
- Keep custom range edits wired through the existing `startDate` and `endDate` report filter state.
- Keep future dates disabled for custom range selection.

## Impact

- Affects the `/reports` dashboard filter toolbar only.
- Does not change the reports API contract or query parameter names.
