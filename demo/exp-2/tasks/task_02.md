# Task 02 - Descriptive Statistics

Add statistics analysis for a chosen series.

## Requirements
- Implement `stats describe --series <id>`.
- Output at least:
  - count
  - mean
  - median
  - variance
  - standard deviation
  - min/max
- Implement `stats zscore --series <id>` to print each value and its z-score.
- Handle empty/too-short series gracefully with clear errors.

## Constraints
- Use clear numeric formatting (consistent decimal precision).
- Preserve existing series commands from prior tasks.

## Acceptance Criteria
- Stats are correct for known small datasets.
- Z-score output is stable and readable.
