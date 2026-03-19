# TASK-03 - First Real KNN Regression Implementation

## Summary
Replace placeholder prediction with real KNN regression using Python and NumPy only.

## Objective
Produce numerically valid predictions based on nearest-neighbor averaging.

## Requirements
- Implement KNN regression logic in the application.
- Use only Python standard library + NumPy.
- No external KNN or scientific/maths libraries beyond NumPy.
- `query-csv` must read feature rows and write one prediction per row.
- Validate input dimension and fail clearly on mismatch.

## Acceptance Criteria
- Predictions change based on training data and query input (no constant fallback behavior).
- Query with valid data produces numeric outputs for all rows.
- Invalid feature shapes are rejected with explicit error messaging.
