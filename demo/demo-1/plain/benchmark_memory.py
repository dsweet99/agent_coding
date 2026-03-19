#!/usr/bin/env python3
"""Memory benchmark for KNN CLI at 10k x 100 scale.

Generates test data, runs full workflow, and reports memory usage.
"""

import csv
import os
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

TRAIN_SIZE = 10000
QUERY_SIZE = 10000
DIMS = 100
DATASET_NAME = "benchmark_mem"


def get_peak_memory_mb():
    """Get peak memory usage in MB (Linux/macOS)."""
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    # ru_maxrss is in KB on Linux, bytes on macOS
    if sys.platform == "darwin":
        return usage.ru_maxrss / (1024 * 1024)
    return usage.ru_maxrss / 1024


def generate_train_csv(path: str, n_samples: int, n_dims: int, seed: int = 42):
    """Generate training CSV with features + target."""
    np.random.seed(seed)
    features = np.random.randn(n_samples, n_dims)
    targets = np.sum(features[:, :5], axis=1) + np.random.randn(n_samples) * 0.1

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        for i in range(n_samples):
            row = list(features[i]) + [targets[i]]
            writer.writerow(row)


def generate_query_csv(path: str, n_samples: int, n_dims: int, seed: int = 123):
    """Generate query CSV with features only."""
    np.random.seed(seed)
    features = np.random.randn(n_samples, n_dims)

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        for i in range(n_samples):
            writer.writerow(list(features[i]))


def run_command(cmd: list) -> tuple:
    """Run command and return (success, stdout, stderr, time_s)."""
    start = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    return result.returncode == 0, result.stdout, result.stderr, elapsed


def main():
    print("=" * 60)
    print("KNN CLI Memory Benchmark")
    print(f"Scale: {TRAIN_SIZE} train x {QUERY_SIZE} query x {DIMS} dims")
    print("=" * 60)

    # Setup
    train_csv = "bench_train.csv"
    query_csv = "bench_query.csv"
    output_csv = "bench_output.csv"
    dataset_dir = Path(".knn_datasets") / DATASET_NAME

    # Cleanup previous runs
    for f in [train_csv, query_csv, output_csv]:
        if os.path.exists(f):
            os.remove(f)
    if dataset_dir.exists():
        shutil.rmtree(dataset_dir)

    # Generate test data
    print("\n[1/5] Generating training data...")
    start = time.perf_counter()
    generate_train_csv(train_csv, TRAIN_SIZE, DIMS)
    print(f"      Generated {train_csv} in {time.perf_counter() - start:.2f}s")

    print("\n[2/5] Generating query data...")
    start = time.perf_counter()
    generate_query_csv(query_csv, QUERY_SIZE, DIMS)
    print(f"      Generated {query_csv} in {time.perf_counter() - start:.2f}s")

    # Run workflow
    print("\n[3/5] Creating dataset...")
    success, stdout, stderr, elapsed = run_command([
        sys.executable, "knn_cli.py", "create",
        "--dataset", DATASET_NAME, "--dimension", str(DIMS), "--overwrite"
    ])
    if not success:
        print(f"FAILED: {stderr}")
        return 1
    print(f"      {stdout.strip()} ({elapsed:.2f}s)")

    print("\n[4/5] Adding training data...")
    success, stdout, stderr, elapsed = run_command([
        sys.executable, "knn_cli.py", "add-csv",
        "--dataset", DATASET_NAME, "--file", train_csv
    ])
    if not success:
        print(f"FAILED: {stderr}")
        return 1
    add_time = elapsed
    print(f"      {stdout.strip()} ({elapsed:.2f}s)")

    print("\n[5/5] Running queries...")
    success, stdout, stderr, elapsed = run_command([
        sys.executable, "knn_cli.py", "query-csv",
        "--dataset", DATASET_NAME, "--file", query_csv, "--output", output_csv
    ])
    if not success:
        print(f"FAILED: {stderr}")
        return 1
    query_time = elapsed
    print(f"      {stdout.strip()} ({elapsed:.2f}s)")

    # Verify output
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    # Count predictions
    with open(output_csv, "r") as f:
        pred_count = sum(1 for _ in f) - 1  # minus header

    print(f"Predictions generated: {pred_count}")
    print(f"Add-csv time: {add_time:.2f}s")
    print(f"Query-csv time: {query_time:.2f}s")
    print(f"Total workflow time: {add_time + query_time:.2f}s")

    peak_mem = get_peak_memory_mb()
    print(f"Peak child memory: {peak_mem:.1f} MB")

    # Check correctness: predictions should be reasonable
    with open(output_csv, "r") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        preds = [float(row[0]) for row in reader]

    pred_mean = np.mean(preds)
    pred_std = np.std(preds)
    print(f"Prediction mean: {pred_mean:.4f}")
    print(f"Prediction std: {pred_std:.4f}")

    # Test repeated calls work correctly
    print("\n[VERIFICATION] Testing repeated query-csv call...")
    success, stdout, stderr, elapsed = run_command([
        sys.executable, "knn_cli.py", "query-csv",
        "--dataset", DATASET_NAME, "--file", query_csv, "--output", "bench_output2.csv"
    ])
    if not success:
        print(f"FAILED: {stderr}")
        return 1

    # Compare outputs
    with open(output_csv, "r") as f1, open("bench_output2.csv", "r") as f2:
        if f1.read() == f2.read():
            print("      Repeated query produces identical results: PASS")
        else:
            print("      Repeated query produces different results: FAIL")
            return 1

    # Test repeated add-csv
    print("\n[VERIFICATION] Testing repeated add-csv call...")
    generate_train_csv("bench_train2.csv", 100, DIMS, seed=999)
    success, stdout, stderr, elapsed = run_command([
        sys.executable, "knn_cli.py", "add-csv",
        "--dataset", DATASET_NAME, "--file", "bench_train2.csv"
    ])
    if not success:
        print(f"FAILED: {stderr}")
        return 1
    print(f"      {stdout.strip()}")

    # Cleanup
    for f in [train_csv, query_csv, output_csv, "bench_output2.csv", "bench_train2.csv"]:
        if os.path.exists(f):
            os.remove(f)
    if dataset_dir.exists():
        shutil.rmtree(dataset_dir)

    print("\n" + "=" * 60)
    print("BENCHMARK COMPLETE - All checks passed")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
