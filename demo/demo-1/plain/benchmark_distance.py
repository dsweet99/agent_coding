#!/usr/bin/env python3
"""Benchmark: Compare distance computation strategies for KNN regression.

Approach A: Fully vectorized all-pairs distance computation
Approach B: Chunked/batched distance computation

Target workload: 10,000 train x 10,000 query x 100 dimensions
"""

import time
import numpy as np


def knn_predict_approach_a(train_features: np.ndarray, train_targets: np.ndarray,
                           query_features: np.ndarray, k: int = 5) -> np.ndarray:
    """Approach A: Fully vectorized all-pairs distance computation.

    Computes all pairwise distances at once using broadcasting.
    Memory: O(n_train * n_query) for the distance matrix.
    """
    n_queries = query_features.shape[0]
    n_train = train_features.shape[0]
    k = min(k, n_train)

    # Compute all pairwise squared distances using the identity:
    # ||a - b||^2 = ||a||^2 + ||b||^2 - 2*a.b
    train_sq = np.sum(train_features ** 2, axis=1)  # (n_train,)
    query_sq = np.sum(query_features ** 2, axis=1)  # (n_query,)
    cross = query_features @ train_features.T       # (n_query, n_train)

    # distances[i, j] = squared distance from query i to train j
    distances_sq = query_sq[:, np.newaxis] + train_sq[np.newaxis, :] - 2 * cross

    # Find k nearest for each query
    predictions = np.zeros(n_queries)
    for i in range(n_queries):
        nearest_indices = np.argpartition(distances_sq[i], k - 1)[:k]
        predictions[i] = np.mean(train_targets[nearest_indices])

    return predictions


def knn_predict_approach_b(train_features: np.ndarray, train_targets: np.ndarray,
                           query_features: np.ndarray, k: int = 5,
                           chunk_size: int = 1000) -> np.ndarray:
    """Approach B: Chunked/batched distance computation.

    Processes queries in chunks to control memory usage while still
    using vectorized operations within each chunk.
    Memory: O(chunk_size * n_train) per chunk.
    """
    n_queries = query_features.shape[0]
    n_train = train_features.shape[0]
    k = min(k, n_train)

    predictions = np.zeros(n_queries)

    # Precompute train squared norms once
    train_sq = np.sum(train_features ** 2, axis=1)  # (n_train,)

    # Process queries in chunks
    for chunk_start in range(0, n_queries, chunk_size):
        chunk_end = min(chunk_start + chunk_size, n_queries)
        query_chunk = query_features[chunk_start:chunk_end]

        # Compute distances for this chunk
        query_sq = np.sum(query_chunk ** 2, axis=1)  # (chunk_size,)
        cross = query_chunk @ train_features.T       # (chunk_size, n_train)
        distances_sq = query_sq[:, np.newaxis] + train_sq[np.newaxis, :] - 2 * cross

        # Find k nearest for each query in chunk
        for i, dist_row in enumerate(distances_sq):
            nearest_indices = np.argpartition(dist_row, k - 1)[:k]
            predictions[chunk_start + i] = np.mean(train_targets[nearest_indices])

    return predictions


def run_benchmark(n_runs=3):
    """Run benchmark comparing both approaches with multiple runs."""
    # Target workload parameters
    n_train = 10000
    n_query = 10000
    n_dims = 100
    k = 5

    print("=" * 70)
    print("KNN Distance Computation Benchmark")
    print("=" * 70)
    print(f"Configuration: {n_train} train x {n_query} query x {n_dims} dims, k={k}")
    print(f"Number of runs: {n_runs}")
    print()

    # Generate random data
    print("Generating random data...")
    np.random.seed(42)
    train_features = np.random.randn(n_train, n_dims)
    train_targets = np.random.randn(n_train)
    query_features = np.random.randn(n_query, n_dims)
    print("Data generation complete.")
    print()

    # Benchmark Approach A
    print("Running: Approach A (fully vectorized all-pairs)...")
    times_a = []
    pred_a = None
    for run in range(n_runs):
        start = time.perf_counter()
        pred_a = knn_predict_approach_a(train_features, train_targets, query_features, k)
        elapsed = time.perf_counter() - start
        times_a.append(elapsed)
        print(f"  Run {run+1}: {elapsed:.3f} seconds")
    avg_a = np.mean(times_a)
    print(f"  Average: {avg_a:.3f} seconds")
    print()

    # Benchmark Approach B
    print("Running: Approach B (chunked, chunk_size=1000)...")
    times_b = []
    pred_b = None
    for run in range(n_runs):
        start = time.perf_counter()
        pred_b = knn_predict_approach_b(train_features, train_targets, query_features, k)
        elapsed = time.perf_counter() - start
        times_b.append(elapsed)
        print(f"  Run {run+1}: {elapsed:.3f} seconds")
    avg_b = np.mean(times_b)
    print(f"  Average: {avg_b:.3f} seconds")
    print()

    # Verify correctness
    print("-" * 70)
    print("Correctness Verification")
    print("-" * 70)
    max_diff = np.max(np.abs(pred_a - pred_b))
    print(f"Max absolute difference (A vs B): {max_diff:.2e}")
    if max_diff < 1e-10:
        print("Both approaches produce equivalent results.")
    else:
        print("WARNING: Results differ!")
    print()

    # Memory analysis
    print("-" * 70)
    print("Memory Analysis")
    print("-" * 70)
    memory_a = n_train * n_query * 8 / (1024**2)  # bytes to MB (float64)
    memory_b = 1000 * n_train * 8 / (1024**2)     # chunk_size=1000
    print(f"Approach A peak distance matrix: {memory_a:.1f} MB")
    print(f"Approach B peak distance matrix: {memory_b:.1f} MB (per chunk)")
    print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'Approach':<45} {'Avg Time (s)':<15}")
    print("-" * 60)
    print(f"{'A: Fully vectorized all-pairs':<45} {avg_a:<15.3f}")
    print(f"{'B: Chunked (chunk_size=1000)':<45} {avg_b:<15.3f}")
    print()

    if avg_a < avg_b:
        winner = "A"
        speedup = avg_b / avg_a
        print(f"WINNER: Approach A (fully vectorized)")
        print(f"Approach A is {speedup:.2f}x faster than Approach B")
    else:
        winner = "B"
        speedup = avg_a / avg_b
        print(f"WINNER: Approach B (chunked)")
        print(f"Approach B is {speedup:.2f}x faster than Approach A")

    print()
    print("-" * 70)
    print("DECISION")
    print("-" * 70)

    # When times are very close, prefer approach B for memory efficiency
    diff_pct = abs(avg_a - avg_b) / min(avg_a, avg_b) * 100
    if diff_pct < 5:
        print(f"Times are within {diff_pct:.1f}% - essentially equivalent performance.")
        print("Selecting Approach B for better memory scalability.")
        winner = "B"
    else:
        print(f"Clear performance difference ({diff_pct:.1f}%).")
        print(f"Selecting Approach {winner} as the faster option.")

    return winner, {"A": avg_a, "B": avg_b}


if __name__ == "__main__":
    winner, results = run_benchmark(n_runs=3)
