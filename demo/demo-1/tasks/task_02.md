# TASK-02 - Training CSV Ingestion and Append Semantics

## Summary
Implement robust ingestion of training observations from CSV, including repeated imports.

## Objective
Support reliable data loading at scale while protecting against malformed input.

## Requirements
- `add-csv` must read training CSV with feature columns and target column.
- Validate row shape against dataset dimension.
- Reject malformed rows with actionable messages (include row information).
- Support repeated `add-csv` calls that append observations to the same dataset.
- Ensure partial failures do not silently corrupt stored data.

## Acceptance Criteria
- Multiple `add-csv` calls for the same dataset increase training-set size cumulatively.
- Invalid CSV content fails with clear diagnostics.
- Previously loaded valid data remains usable after a failed add attempt.
