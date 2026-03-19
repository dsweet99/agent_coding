# TASK-08 - Reliability, Validation, and Error Quality

## Summary
Harden operational reliability and improve user-facing diagnostics.

## Objective
Make failures explicit, recoverable, and easy to troubleshoot.

## Requirements
- Expand validation for:
  - empty CSV files
  - missing required columns
  - non-numeric fields
  - dimension mismatch
  - empty dataset queries
- Standardize error messages across commands.
- Ensure failed commands do not leave partial/corrupt state.
- Add automated tests for negative/error-path scenarios.

## Acceptance Criteria
- Common invalid-input cases return actionable errors.
- Storage remains consistent after failures.
- Error-path tests pass.
