# TASK-05 - Decision Ticket: Distance Computation Strategy

## Summary
Choose and implement the faster distance-computation strategy for the target workload.

## Objective
Minimize `query-csv` runtime on large inputs while preserving prediction correctness.

## Decision Required
Implement either approach A or B, then keep whichever is objectively faster:
- **A:** fully vectorized all-pairs distance computation
- **B:** chunked/vectorized distance computation over query or train batches

## Requirements
- Measure runtime on representative data size (10,000 train x 10,000 query x 100 dims).
- Keep numerical outputs equivalent within floating-point tolerance.
- Document the measured result and which approach was selected.
- Retain only the winning implementation path in active code.

## Acceptance Criteria
- A benchmark artifact/report is produced showing timings for both options.
- Selected implementation has lower end-to-end query runtime.
- Prediction outputs remain stable and valid.
