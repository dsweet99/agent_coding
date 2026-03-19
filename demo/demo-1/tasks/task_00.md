# TASK-00 - Skeleton CLI with End-to-End Placeholder Flow

## Summary
Create a rough first version of the full application surface so the complete workflow exists, even if prediction quality is not yet production-ready.

## Objective
Ship a minimal but runnable CLI that supports the required commands and file contract:
- `create`
- `add-csv`
- `query-csv`

## Requirements
- Add a runnable CLI entry point with clear `--help`.
- Implement all required commands and required flags from grounding.
- `create` initializes a dataset with configured dimensionality.
- `add-csv` accepts training CSV input and stores data in some local form.
- `query-csv` accepts query CSV input and writes predictions CSV.
- In this ticket, prediction behavior may be simplistic (for example, constant prediction), but command execution must succeed on valid inputs.
- Errors for missing files, unknown datasets, and bad arguments must be explicit.

## Acceptance Criteria
- A user can run all three commands in order without crashes.
- `query-csv` produces a prediction file with one numeric prediction per row.
- CLI help text lists commands and required arguments.
