# TASK-04 - Query CSV Robustness and Contract Compliance

## Summary
Strengthen `query-csv` behavior to match evaluation expectations and improve operator trust.

## Objective
Guarantee consistent output shape and safe behavior for repeated queries.

## Requirements
- `query-csv` must support repeated calls on the same dataset.
- Output CSV must contain one numeric prediction per input row (header optional).
- Preserve input row order in output predictions.
- Validate query CSV format and row dimensionality with clear errors.
- Do not mutate training data during query operations.

## Acceptance Criteria
- Back-to-back `query-csv` calls with different files both succeed and return correctly sized outputs.
- Output row order matches query row order.
- Invalid query files fail without modifying dataset state.
