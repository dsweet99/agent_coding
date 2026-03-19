# KNN CLI Benchmark Report

## Memory Scaling and Batch Processing (TASK-06)

### Summary

Memory-aware batching implemented to ensure stable operation at 10k x 100 scale without out-of-memory failures.

### Changes Implemented

1. **add-csv batching**: Two-pass approach with streaming validation (no row storage during validation), then batched writes (1000 rows per batch)
2. **query-csv batching**: Streaming validation, then batched prediction with immediate output streaming (1000 queries per batch)
3. **Precomputed training norms**: Training squared norms computed once and reused across query batches

### Benchmark Results (10,000 train × 10,000 query × 100 dims)

| Metric | Value |
|--------|-------|
| Training data load (add-csv) | 2.45s |
| Query execution (query-csv) | 5.18s |
| Total workflow time | 7.63s |
| Peak memory | 300.7 MB |
| Predictions generated | 10,000 |

### Memory Behavior

- **Bounded growth**: CSV processing uses fixed batch sizes (1000 rows)
- **No accumulation**: Predictions streamed directly to output, not accumulated
- **Repeated calls**: Both add-csv and query-csv verified to work correctly on repeated calls
- **Numerical consistency**: Repeated query-csv calls produce identical results

### Verification

Run the memory benchmark:
```bash
python3 benchmark_memory.py
```

---

# Distance Computation Strategy Benchmark Report

## Summary

This report documents the evaluation and selection of the distance computation strategy for the KNN regression CLI as specified in TASK-05.

## Approaches Evaluated

### Approach A: Fully Vectorized All-Pairs
- Computes all pairwise squared distances at once using: `||a-b||^2 = ||a||^2 + ||b||^2 - 2*a·b`
- Single matrix multiplication: `query_features @ train_features.T`
- Memory: O(n_train × n_query) for the full distance matrix

### Approach B: Chunked Vectorized Distance Computation
- Same mathematical approach as A, but processes queries in chunks
- Chunk size: 1000 queries per batch
- Memory: O(chunk_size × n_train) per chunk

## Benchmark Configuration

- **Training samples:** 10,000
- **Query samples:** 10,000
- **Dimensions:** 100
- **k (neighbors):** 5
- **Runs per approach:** 3

## Results

| Approach | Run 1 (s) | Run 2 (s) | Run 3 (s) | Average (s) |
|----------|-----------|-----------|-----------|-------------|
| A: Fully vectorized | 4.092 | 4.049 | 3.919 | **4.020** |
| B: Chunked (chunk=1000) | 3.047 | 3.045 | 3.040 | **3.044** |

### Performance Comparison
- **Approach B is 1.32x faster** (32% improvement)
- Time saved: ~1 second per 10,000 queries

### Memory Usage
| Approach | Peak Distance Matrix Memory |
|----------|----------------------------|
| A | 762.9 MB |
| B | 76.3 MB (per chunk) |

- **Approach B uses 10x less memory**

### Correctness Verification
- Maximum absolute difference between approaches: **0.00e+00**
- Both approaches produce identical predictions within floating-point precision

## Decision

**Selected: Approach B (Chunked Vectorized Distance Computation)**

### Rationale
1. **Faster execution:** 32% improvement in query runtime
2. **Lower memory footprint:** 10x reduction in peak memory usage
3. **Better scalability:** Chunking allows handling larger datasets without memory issues
4. **Identical accuracy:** No loss in prediction quality

## Implementation

The winning approach has been integrated into `knn_cli.py` in the `knn_predict()` function with:
- Chunk size of 1000 queries (optimal based on testing)
- Precomputed training data squared norms for efficiency
- Vectorized distance computation within each chunk

## Reproduction

To reproduce the benchmark:
```bash
python3 benchmark_distance.py
```
