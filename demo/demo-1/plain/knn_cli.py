#!/usr/bin/env python3
"""KNN Regression CLI - Dataset-based numeric prediction using k-nearest-neighbors."""

import argparse
import csv
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path

import numpy as np

DATASETS_DIR = Path(".knn_datasets")


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


def error_exit(message: str) -> None:
    """Exit with a standardized error message format."""
    sys.exit(f"Error: {message}")


def get_dataset_path(name: str) -> Path:
    """Return the path to the dataset directory."""
    return DATASETS_DIR / name


def load_dataset_meta(name: str) -> dict:
    """Load dataset metadata, raising error if not found."""
    dataset_path = get_dataset_path(name)
    meta_path = dataset_path / "meta.json"

    if not dataset_path.exists():
        error_exit(f"Dataset '{name}' does not exist. Create it first with 'create --dataset {name} --dimension <int>'.")

    if not meta_path.exists():
        error_exit(f"Dataset '{name}' is corrupted (missing metadata).")

    with open(meta_path, "r") as f:
        return json.load(f)


def save_dataset_meta(name: str, meta: dict) -> None:
    """Save dataset metadata."""
    dataset_path = get_dataset_path(name)
    meta_path = dataset_path / "meta.json"

    with open(meta_path, "w") as f:
        json.dump(meta, f)


def load_training_data(name: str) -> tuple:
    """Load training data from dataset, returning (features, targets) as numpy arrays.

    Uses NumPy binary format (.npy) for fast loading. Returns fresh copies of the
    data to prevent mutation of stored training data.
    """
    dataset_path = get_dataset_path(name)
    features_path = dataset_path / "features.npy"
    targets_path = dataset_path / "targets.npy"

    if not features_path.exists() or not targets_path.exists():
        return np.array([]).reshape(0, 0), np.array([])

    features = np.load(features_path).copy()
    targets = np.load(targets_path).copy()
    return features, targets


def knn_predict(train_features: np.ndarray, train_targets: np.ndarray,
                query_features: np.ndarray, k: int = 5,
                chunk_size: int = 1000) -> np.ndarray:
    """Predict target values for query points using KNN regression.

    For each query point, finds the k nearest neighbors in the training set
    (using Euclidean distance) and returns the mean of their target values.

    Uses chunked vectorized distance computation for efficiency:
    - Computes squared distances using ||a-b||^2 = ||a||^2 + ||b||^2 - 2*a.b
    - Processes queries in chunks to balance speed and memory usage
    """
    n_queries = query_features.shape[0]
    n_train = train_features.shape[0]

    k = min(k, n_train)

    predictions = np.zeros(n_queries)

    # Precompute squared norms for training data
    train_sq = np.sum(train_features ** 2, axis=1)

    # Process queries in chunks
    for chunk_start in range(0, n_queries, chunk_size):
        chunk_end = min(chunk_start + chunk_size, n_queries)
        query_chunk = query_features[chunk_start:chunk_end]

        # Compute squared distances for this chunk
        query_sq = np.sum(query_chunk ** 2, axis=1)
        cross = query_chunk @ train_features.T
        distances_sq = query_sq[:, np.newaxis] + train_sq[np.newaxis, :] - 2 * cross

        # Find k nearest neighbors for each query in chunk
        for i, dist_row in enumerate(distances_sq):
            nearest_indices = np.argpartition(dist_row, k - 1)[:k]
            predictions[chunk_start + i] = np.mean(train_targets[nearest_indices])

    return predictions


def validate_csv_file(csv_file: str, expected_cols: int, context: str) -> int:
    """Validate CSV file structure and content.

    Args:
        csv_file: Path to CSV file
        expected_cols: Expected number of columns per row
        context: Description for error messages (e.g., "training" or "query")

    Returns:
        Number of valid rows

    Raises:
        ValidationError on any validation failure
    """
    if not os.path.exists(csv_file):
        raise ValidationError(f"File '{csv_file}' not found.")

    row_count = 0
    with open(csv_file, "r", newline="") as f:
        reader = csv.reader(f)

        for row_num, row in enumerate(reader, start=1):
            if len(row) != expected_cols:
                raise ValidationError(
                    f"Row {row_num} in '{csv_file}' has {len(row)} columns, "
                    f"expected {expected_cols}."
                )

            for col_idx, value in enumerate(row):
                try:
                    float(value)
                except ValueError:
                    raise ValidationError(
                        f"Row {row_num}, column {col_idx + 1} in '{csv_file}' "
                        f"contains non-numeric value: '{value}'."
                    )

            row_count += 1

    if row_count == 0:
        raise ValidationError(f"File '{csv_file}' is empty (no {context} data).")

    return row_count


def cmd_create(args):
    """Create a new dataset with specified dimensionality."""
    name = args.dataset
    dimension = args.dimension
    overwrite = args.overwrite

    if dimension < 1:
        error_exit(f"Dimension must be a positive integer, got {dimension}.")

    dataset_path = get_dataset_path(name)

    if dataset_path.exists():
        if not overwrite:
            error_exit(
                f"Dataset '{name}' already exists. "
                f"Use --overwrite to replace it."
            )
        shutil.rmtree(dataset_path)

    DATASETS_DIR.mkdir(exist_ok=True)
    dataset_path.mkdir()

    meta = {
        "name": name,
        "dimension": dimension,
        "observation_count": 0
    }
    save_dataset_meta(name, meta)

    print(f"Created dataset '{name}' with dimension {dimension}.")


def cmd_add_csv(args):
    """Add training observations from a CSV file to the dataset.

    Uses two-pass approach: first validates all rows (streaming), then loads
    and appends to NumPy binary storage. Supports repeated calls by loading
    existing data and concatenating new observations.

    Uses atomic writes: new data is written to temp files first, then moved
    into place only after all writes succeed. This prevents partial state on failure.
    """
    name = args.dataset
    csv_file = args.file

    meta = load_dataset_meta(name)
    dimension = meta["dimension"]
    expected_cols = dimension + 1  # features + target

    dataset_path = get_dataset_path(name)
    features_path = dataset_path / "features.npy"
    targets_path = dataset_path / "targets.npy"

    # First pass: validate all rows
    try:
        row_count = validate_csv_file(csv_file, expected_cols, "training")
    except ValidationError as e:
        error_exit(str(e))

    # Second pass: load all new data into memory
    new_rows = []
    with open(csv_file, "r", newline="") as infile:
        reader = csv.reader(infile)
        for row in reader:
            new_rows.append([float(v) for v in row])

    new_data = np.array(new_rows)
    new_features = new_data[:, :-1]
    new_targets = new_data[:, -1]

    # Load existing data and concatenate (supports repeated add-csv)
    if features_path.exists() and targets_path.exists():
        existing_features = np.load(features_path)
        existing_targets = np.load(targets_path)
        combined_features = np.vstack([existing_features, new_features])
        combined_targets = np.concatenate([existing_targets, new_targets])
    else:
        combined_features = new_features
        combined_targets = new_targets

    # Atomic write: save to temp files first, then move into place
    temp_dir = dataset_path
    try:
        with tempfile.NamedTemporaryFile(dir=temp_dir, suffix=".npy", delete=False) as f_feat:
            temp_features_path = Path(f_feat.name)
        with tempfile.NamedTemporaryFile(dir=temp_dir, suffix=".npy", delete=False) as f_targ:
            temp_targets_path = Path(f_targ.name)
        with tempfile.NamedTemporaryFile(dir=temp_dir, suffix=".json", delete=False) as f_meta:
            temp_meta_path = Path(f_meta.name)

        np.save(temp_features_path, combined_features)
        np.save(temp_targets_path, combined_targets)

        new_meta = meta.copy()
        new_meta["observation_count"] += row_count
        with open(temp_meta_path, "w") as f:
            json.dump(new_meta, f)

        # Atomic move (on same filesystem, this is atomic)
        temp_features_path.replace(features_path)
        temp_targets_path.replace(targets_path)
        temp_meta_path.replace(dataset_path / "meta.json")

    except Exception as e:
        # Clean up temp files on failure
        for temp_path in [temp_features_path, temp_targets_path, temp_meta_path]:
            if temp_path.exists():
                temp_path.unlink()
        error_exit(f"Failed to save data: {e}")

    print(f"Added {row_count} observations to dataset '{name}'. Total: {new_meta['observation_count']}.")


def cmd_query_csv(args):
    """Generate predictions for query observations and write to output CSV.

    Supports repeated calls on the same dataset. Training data is loaded fresh
    each time and never mutated. Output preserves input row order.

    Memory-bounded: processes queries in batches and streams predictions to output.
    Uses atomic writes: predictions are written to a temp file first, then moved
    into place only after all predictions succeed.
    """
    name = args.dataset
    query_file = args.file
    output_file = args.output
    query_batch_size = 1000

    meta = load_dataset_meta(name)
    dimension = meta["dimension"]

    if meta["observation_count"] == 0:
        error_exit(f"Dataset '{name}' has no training observations. Add data first with 'add-csv'.")

    # First pass: validate all rows
    try:
        row_count = validate_csv_file(query_file, dimension, "query")
    except ValidationError as e:
        error_exit(str(e))

    # Load training data once (required for KNN)
    train_features, train_targets = load_training_data(name)

    # Precompute training squared norms (reused across batches)
    train_sq = np.sum(train_features ** 2, axis=1)

    # Second pass: process queries in batches, stream predictions to temp file
    total_predictions = 0
    k = 5
    k_effective = min(k, train_features.shape[0])

    output_path = Path(output_file)
    output_dir = output_path.parent if output_path.parent.exists() else Path(".")
    temp_output_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=output_dir, suffix=".csv", delete=False, newline=""
        ) as temp_file:
            temp_output_path = Path(temp_file.name)
            writer = csv.writer(temp_file)
            writer.writerow(["prediction"])

            with open(query_file, "r", newline="") as infile:
                reader = csv.reader(infile)

                batch = []
                for row in reader:
                    values = [float(v) for v in row]
                    batch.append(values)

                    if len(batch) >= query_batch_size:
                        query_chunk = np.array(batch)
                        preds = _predict_batch(train_features, train_targets, train_sq,
                                              query_chunk, k_effective)
                        for pred in preds:
                            writer.writerow([pred])
                        total_predictions += len(preds)
                        batch = []

                if batch:
                    query_chunk = np.array(batch)
                    preds = _predict_batch(train_features, train_targets, train_sq,
                                          query_chunk, k_effective)
                    for pred in preds:
                        writer.writerow([pred])
                    total_predictions += len(preds)

        assert total_predictions == row_count, "Prediction count must match query count"

        # Atomic move to final location
        temp_output_path.replace(output_path)

    except Exception as e:
        if temp_output_path and temp_output_path.exists():
            temp_output_path.unlink()
        if isinstance(e, AssertionError):
            raise
        error_exit(f"Failed to write predictions: {e}")

    print(f"Wrote {total_predictions} predictions to '{output_file}'.")


def _predict_batch(train_features: np.ndarray, train_targets: np.ndarray,
                   train_sq: np.ndarray, query_chunk: np.ndarray, k: int) -> np.ndarray:
    """Compute KNN predictions for a batch of queries.

    Uses precomputed training squared norms for efficiency.
    """
    query_sq = np.sum(query_chunk ** 2, axis=1)
    cross = query_chunk @ train_features.T
    distances_sq = query_sq[:, np.newaxis] + train_sq[np.newaxis, :] - 2 * cross

    predictions = np.zeros(query_chunk.shape[0])
    for i, dist_row in enumerate(distances_sq):
        nearest_indices = np.argpartition(dist_row, k - 1)[:k]
        predictions[i] = np.mean(train_targets[nearest_indices])

    return predictions


def main():
    parser = argparse.ArgumentParser(
        description="KNN Regression CLI - Dataset-based numeric prediction using k-nearest-neighbors.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  create      Create a new dataset with specified dimensionality
  add-csv     Add training observations from a CSV file
  query-csv   Generate predictions for query observations

Examples:
  %(prog)s create --dataset mydata --dimension 5
  %(prog)s add-csv --dataset mydata --file train.csv
  %(prog)s query-csv --dataset mydata --file test.csv --output predictions.csv
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # create command
    create_parser = subparsers.add_parser(
        "create",
        help="Create a new dataset with specified dimensionality"
    )
    create_parser.add_argument(
        "--dataset",
        required=True,
        help="Name of the dataset to create"
    )
    create_parser.add_argument(
        "--dimension",
        type=int,
        required=True,
        help="Number of feature dimensions (positive integer)"
    )
    create_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing dataset if it exists"
    )

    # add-csv command
    add_parser = subparsers.add_parser(
        "add-csv",
        help="Add training observations from a CSV file"
    )
    add_parser.add_argument(
        "--dataset",
        required=True,
        help="Name of the dataset"
    )
    add_parser.add_argument(
        "--file",
        required=True,
        help="Path to training CSV file (features + target)"
    )

    # query-csv command
    query_parser = subparsers.add_parser(
        "query-csv",
        help="Generate predictions for query observations"
    )
    query_parser.add_argument(
        "--dataset",
        required=True,
        help="Name of the dataset"
    )
    query_parser.add_argument(
        "--file",
        required=True,
        help="Path to query CSV file (features only)"
    )
    query_parser.add_argument(
        "--output",
        required=True,
        help="Path to output predictions CSV file"
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "create":
        cmd_create(args)
    elif args.command == "add-csv":
        cmd_add_csv(args)
    elif args.command == "query-csv":
        cmd_query_csv(args)


if __name__ == "__main__":
    main()
