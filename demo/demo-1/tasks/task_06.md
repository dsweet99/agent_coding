# TASK-06 - Memory Scaling and Batch Processing

## Summary
Reduce memory pressure and improve stability for 10k x 100 workloads.

## Objective
Keep memory usage bounded while preserving prediction quality and throughput.

## Requirements
- Ensure query execution avoids unbounded memory growth at benchmark scale.
- Add/adjust batching so large CSV files are processed safely.
- Keep repeated `add-csv` and repeated `query-csv` behavior correct.
- Include a simple benchmark or measurement note showing memory-aware behavior.

## Acceptance Criteria
- The application completes train/load/query workflow at 10,000 train + 10,000 query, 100 dims.
- No out-of-memory failures in normal local execution.
- Results remain numerically consistent with prior validated behavior.
