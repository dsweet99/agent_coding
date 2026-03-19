"""Prediction engine for KNN regression."""

import numpy as np

DEFAULT_K = 5
QUERY_BATCH_SIZE = 1000


def _predict_batch(
    train_features: np.ndarray,
    train_targets: np.ndarray,
    query_batch: np.ndarray,
    train_sq: np.ndarray,
    effective_k: int,
) -> np.ndarray:
    """Predict for a single batch of queries."""
    query_sq = np.sum(query_batch**2, axis=1, keepdims=True)
    cross = query_batch @ train_features.T
    sq_dists = query_sq + train_sq - 2 * cross
    np.maximum(sq_dists, 0, out=sq_dists)
    distances = np.sqrt(sq_dists)
    part = np.argpartition(distances, effective_k - 1, axis=1)[:, :effective_k]
    return np.mean(train_targets[part], axis=1)


def predict(
    train_features: np.ndarray,
    train_targets: np.ndarray,
    query_features: np.ndarray,
    k: int = DEFAULT_K,
) -> np.ndarray:
    """Generate predictions for query observations using KNN regression.

    Uses vectorized all-pairs distance computation with the formula:
    ||a-b||^2 = ||a||^2 + ||b||^2 - 2*a·b

    Processes queries in batches to bound memory usage for large workloads.

    Args:
        train_features: Training feature matrix of shape (n_train, n_features).
        train_targets: Training target values of shape (n_train,).
        query_features: Query feature matrix of shape (n_query, n_features).
        k: Number of nearest neighbors to use.

    Returns:
        Predictions for each query point, shape (n_query,).

    Raises:
        ValueError: If no training data or dimension mismatch.
    """
    if k < 1:
        raise ValueError(f"k must be at least 1, got {k}")

    n_train = train_features.shape[0]
    if n_train == 0:
        raise ValueError("No training data available for prediction")

    if train_features.shape[1] != query_features.shape[1]:
        expected = train_features.shape[1]
        got = query_features.shape[1]
        msg = f"Feature dimension mismatch: expected {expected}, got {got}"
        raise ValueError(msg)

    effective_k = min(k, n_train)
    train_sq = np.sum(train_features**2, axis=1)

    n_query = query_features.shape[0]
    if n_query <= QUERY_BATCH_SIZE:
        return _predict_batch(
            train_features, train_targets, query_features, train_sq, effective_k
        )

    predictions = np.empty(n_query, dtype=np.float64)
    for start in range(0, n_query, QUERY_BATCH_SIZE):
        end = min(start + QUERY_BATCH_SIZE, n_query)
        batch = query_features[start:end]
        predictions[start:end] = _predict_batch(
            train_features, train_targets, batch, train_sq, effective_k
        )
    return predictions
