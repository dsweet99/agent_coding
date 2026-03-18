# Task 06 - Removal: Drop In-place Overwrite

Users keep losing source data by mistake. Remove overwrite behavior from transforms.

## Requirements
- Remove any option/behavior that overwrites source series during `series transform`.
- Transform must always create a new derived series.
- Ensure CLI help and docs reflect this removal.
- If user passes old overwrite flags/options, fail with a clear migration message.

## Constraints
- Existing datasets must remain readable.
- No silent behavior changes.

## Acceptance Criteria
- Transform operations always produce a new series ID.
- Legacy overwrite usage is rejected with actionable guidance.
