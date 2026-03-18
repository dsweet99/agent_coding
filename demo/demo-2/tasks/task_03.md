# Task 03 - Transformations Pipeline

Allow users to transform series data and store results.

## Requirements
- Add `series transform --series <id> --op <operation> [args]`.
- Required operations:
  - `diff` (first difference)
  - `moving-average` (window size argument)
  - `normalize-minmax`
- Transform command creates a new derived series (does not overwrite source by default).
- Store metadata linking derived series to source series and operation used.

## Constraints
- Validate operation arguments (for example, moving average window >= 2).
- Derived data should be reproducible from metadata.

## Acceptance Criteria
- Each operation works on valid data.
- Invalid operations/arguments return clear errors.
- Original series remains unchanged unless explicitly requested.
