"""Command implementations for the CLI."""

from knn_cli.csv_io import read_query_csv, read_training_csv, write_predictions_csv
from knn_cli.dataset import (
    append_to_dataset,
    create_dataset,
    dataset_exists,
    load_dataset_data,
    load_dataset_meta,
)
from knn_cli.predictor import predict


def create(
    dataset: str, dimension: int, *, overwrite: bool = False
) -> None:
    """Create a new dataset with specified dimensionality."""
    if not dataset:
        raise ValueError("Dataset name cannot be empty")
    if dimension < 1:
        raise ValueError(f"Dimension must be positive, got {dimension}")

    if dataset_exists(dataset) and not overwrite:
        raise ValueError(
            f"Dataset '{dataset}' already exists. "
            "Use --overwrite to replace it."
        )

    create_dataset(dataset, dimension)
    print(f"Created dataset '{dataset}' with dimension {dimension}")


def add_csv(dataset: str, filepath: str) -> None:
    """Add training observations from a CSV file to a dataset."""
    if not dataset:
        raise ValueError("Dataset name cannot be empty")

    meta = load_dataset_meta(dataset)
    features, targets = read_training_csv(filepath)

    expected_dim = meta["dimension"]
    if features.shape[1] != expected_dim:
        got = features.shape[1]
        msg = f"Feature dimension mismatch: expected {expected_dim}, got {got}"
        raise ValueError(msg)

    append_to_dataset(dataset, features, targets)
    print(f"Added {features.shape[0]} observations to dataset '{dataset}'")


def query_csv(dataset: str, filepath: str, output: str) -> None:
    """Generate predictions for query observations and write to output file."""
    if not dataset:
        raise ValueError("Dataset name cannot be empty")

    meta = load_dataset_meta(dataset)
    if meta["num_observations"] == 0:
        raise ValueError(
            f"Dataset '{dataset}' has no training data. "
            "Use add-csv to add observations before querying."
        )

    query_features = read_query_csv(filepath)

    expected_dim = meta["dimension"]
    if query_features.shape[1] != expected_dim:
        msg = (
            f"Feature dimension mismatch: expected {expected_dim}, "
            f"got {query_features.shape[1]}"
        )
        raise ValueError(msg)

    train_features, train_targets = load_dataset_data(dataset)
    predictions = predict(train_features, train_targets, query_features)

    write_predictions_csv(output, predictions)
    print(f"Wrote {len(predictions)} predictions to '{output}'")
