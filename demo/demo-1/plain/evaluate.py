#!/usr/bin/env python3
"""
Evaluation script for KNN Regression CLI.

Runs end-to-end benchmark at target scale (10k train × 10k query × 100 dims)
and computes out-of-sample RMSE for comparison between agent workflows.

Usage:
    python evaluate.py [--seed SEED] [--train-size N] [--test-size M] [--dims D]
"""

import argparse
import csv
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np


def generate_synthetic_data(n_samples: int, n_dims: int, seed: int = 42):
    """Generate synthetic regression data with linear target + noise.

    Returns (features, targets) where target = sum(features * weights) + noise.
    """
    rng = np.random.default_rng(seed)
    features = rng.standard_normal((n_samples, n_dims))
    weights = rng.standard_normal(n_dims)
    noise = rng.standard_normal(n_samples) * 0.5
    targets = features @ weights + noise
    return features, targets


def write_train_csv(filepath: str, features: np.ndarray, targets: np.ndarray):
    """Write training data to CSV (features + target)."""
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        for i in range(features.shape[0]):
            row = list(features[i]) + [targets[i]]
            writer.writerow(row)


def write_query_csv(filepath: str, features: np.ndarray):
    """Write query data to CSV (features only)."""
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        for i in range(features.shape[0]):
            writer.writerow(list(features[i]))


def read_predictions(filepath: str) -> np.ndarray:
    """Read predictions from output CSV."""
    predictions = []
    with open(filepath, "r", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            predictions.append(float(row[0]))
    return np.array(predictions)


def compute_rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Compute Root Mean Squared Error."""
    return np.sqrt(np.mean((actual - predicted) ** 2))


def run_cli(cli_path: str, *args) -> tuple:
    """Run CLI command and return (returncode, stdout, stderr, elapsed_time)."""
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, cli_path] + list(args),
        capture_output=True,
        text=True
    )
    elapsed = time.perf_counter() - start
    return result.returncode, result.stdout, result.stderr, elapsed


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate KNN Regression CLI at target scale"
    )
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for data generation (default: 42)")
    parser.add_argument("--train-size", type=int, default=10000,
                        help="Number of training samples (default: 10000)")
    parser.add_argument("--test-size", type=int, default=10000,
                        help="Number of test samples (default: 10000)")
    parser.add_argument("--dims", type=int, default=100,
                        help="Number of feature dimensions (default: 100)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print verbose output")
    args = parser.parse_args()

    cli_path = str(Path(__file__).parent / "knn_cli.py")
    if not Path(cli_path).exists():
        print("Error: knn_cli.py not found", file=sys.stderr)
        sys.exit(1)

    print(f"=== KNN CLI Evaluation ===")
    print(f"Train size: {args.train_size}")
    print(f"Test size:  {args.test_size}")
    print(f"Dimensions: {args.dims}")
    print(f"Seed:       {args.seed}")
    print()

    with tempfile.TemporaryDirectory(prefix="knn_eval_") as tmpdir:
        os.chdir(tmpdir)

        print("Generating synthetic data...")
        train_features, train_targets = generate_synthetic_data(
            args.train_size, args.dims, seed=args.seed
        )
        test_features, test_targets = generate_synthetic_data(
            args.test_size, args.dims, seed=args.seed + 1
        )

        train_csv = os.path.join(tmpdir, "train.csv")
        test_csv = os.path.join(tmpdir, "test.csv")
        pred_csv = os.path.join(tmpdir, "predictions.csv")

        print("Writing CSV files...")
        write_train_csv(train_csv, train_features, train_targets)
        write_query_csv(test_csv, test_features)

        dataset_name = "eval_dataset"

        print("\n--- Running CLI Commands ---")

        # Create dataset
        rc, stdout, stderr, elapsed = run_cli(
            cli_path, "create", "--dataset", dataset_name,
            "--dimension", str(args.dims), "--overwrite"
        )
        if rc != 0:
            print(f"FAIL: create command failed: {stderr}", file=sys.stderr)
            sys.exit(1)
        print(f"create:    {elapsed:.3f}s")
        if args.verbose:
            print(f"  {stdout.strip()}")

        # Add training data
        rc, stdout, stderr, elapsed = run_cli(
            cli_path, "add-csv", "--dataset", dataset_name, "--file", train_csv
        )
        if rc != 0:
            print(f"FAIL: add-csv command failed: {stderr}", file=sys.stderr)
            sys.exit(1)
        print(f"add-csv:   {elapsed:.3f}s")
        if args.verbose:
            print(f"  {stdout.strip()}")

        # Query predictions
        rc, stdout, stderr, elapsed_query = run_cli(
            cli_path, "query-csv", "--dataset", dataset_name,
            "--file", test_csv, "--output", pred_csv
        )
        if rc != 0:
            print(f"FAIL: query-csv command failed: {stderr}", file=sys.stderr)
            sys.exit(1)
        print(f"query-csv: {elapsed_query:.3f}s")
        if args.verbose:
            print(f"  {stdout.strip()}")

        # Read predictions and compute RMSE
        print("\n--- Results ---")
        predictions = read_predictions(pred_csv)

        if len(predictions) != len(test_targets):
            print(f"FAIL: Expected {len(test_targets)} predictions, got {len(predictions)}")
            sys.exit(1)

        rmse = compute_rmse(test_targets, predictions)

        print(f"Predictions:      {len(predictions)}")
        print(f"Out-of-sample RMSE: {rmse:.6f}")
        print(f"Query runtime:    {elapsed_query:.3f}s")
        print()
        print("EVALUATION: PASS")

        # Output parseable result line
        print(f"\n[RESULT] RMSE={rmse:.6f}")


if __name__ == "__main__":
    main()
