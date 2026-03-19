# Algorithm Implementation Details

## KNN Regression (`predictor.py`)

### Vectorized Distance Computation
Uses algebraic identity to avoid 3D intermediate arrays:
```
||a - b||² = ||a||² + ||b||² - 2 * a · b
```

Implementation:
```python
train_sq = np.sum(train_features**2, axis=1)           # (n_train,)
query_sq = np.sum(query_features**2, axis=1, keepdims=True)  # (n_query, 1)
cross = query_features @ train_features.T              # (n_query, n_train)
sq_dists = query_sq + train_sq - 2 * cross
np.maximum(sq_dists, 0, out=sq_dists)  # numerical stability
distances = np.sqrt(sq_dists)
```

**Why**: Naive broadcast `train[np.newaxis,:,:] - query[:,np.newaxis,:]` creates `(n_query, n_train, n_features)` array → OOM on 10k×10k×100 (74GB). Algebraic form uses O(n_query × n_train) memory.

**Performance**: ~10x speedup vs per-query loop on 10k×10k×100 workload.

### Batch Processing for Memory Bounds
For large workloads, process queries in batches to bound memory:

```python
QUERY_BATCH_SIZE = 1000

def _predict_batch(train_features, train_targets, query_batch, train_sq, effective_k):
    # Process single batch (train_sq pre-computed outside loop)
    ...

def predict(...):
    train_sq = np.sum(train_features**2, axis=1)  # Compute once
    predictions = np.empty(n_query, dtype=np.float64)  # Preallocate
    for start in range(0, n_query, QUERY_BATCH_SIZE):
        end = min(start + QUERY_BATCH_SIZE, n_query)
        predictions[start:end] = _predict_batch(..., query_features[start:end], ...)
```

**Why**: Bounds peak memory (~305MB for 10k×10k×100) vs unbounded growth.

**Testing batch consistency**: Compare full predictions against independently computed subsets:
```python
small_preds = predict(..., query_features[:10], ...)
np.testing.assert_array_almost_equal(predictions[:10], small_preds)
```

### Selection & Prediction
- **Selection**: `np.argpartition` for O(n) k-nearest lookup (not full sort)
- **Prediction**: Mean of k nearest neighbors' targets
- **Default k**: 5

### Edge Cases
- `n_train < k`: Use `effective_k = min(k, n_train)`
- `k <= 0`: Raise `ValueError("k must be at least 1")`
- Dimension mismatch: Validate `train_features.shape[1] == query_features.shape[1]`
- Empty training data: Raise `ValueError("No training data available")`

### Constraints
- Only Python stdlib + NumPy (no sklearn, scipy, etc.)

## Dataset Storage (`dataset.py`)

### Format: NumPy Binary (`.npy`)
Benchmarked CSV vs NPY vs NPZ (compressed). NPY chosen for:
- **Load speed**: 24-400x faster than CSV across dataset sizes
- **Query latency**: Lowest cold-start time
- **Size**: ~60% smaller than CSV; NPZ saves only ~4% more

NPZ rejected: decompression latency outweighs marginal size savings.

### Storage Layout
```
~/.knn_cli/datasets/{name}/
  meta.json      # {name, dimension, num_observations}
  features.npy   # (n_samples, n_features) float64
  targets.npy    # (n_samples,) float64
```

### Benchmark Reference
See `_malvin/20260318_185648_d9a00d12/benchmark_report.md` for full metrics.
