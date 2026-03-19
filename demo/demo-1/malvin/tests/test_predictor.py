"""Tests for the predictor module."""

import numpy as np
import pytest

from knn_cli.predictor import predict


def test_predict_knn_single_neighbor():
    """Test KNN with k=1 returns target of nearest neighbor."""
    train_features = np.array([[0.0, 0.0], [10.0, 10.0], [20.0, 20.0]])
    train_targets = np.array([100.0, 200.0, 300.0])
    query_features = np.array([[1.0, 1.0], [11.0, 11.0]])

    predictions = predict(train_features, train_targets, query_features, k=1)

    np.testing.assert_array_almost_equal(predictions, [100.0, 200.0])


def test_predict_knn_multiple_neighbors():
    """Test KNN averages k nearest neighbors."""
    train_features = np.array([
        [0.0, 0.0],
        [1.0, 0.0],
        [2.0, 0.0],
        [100.0, 100.0],
    ])
    train_targets = np.array([10.0, 20.0, 30.0, 1000.0])
    query_features = np.array([[0.5, 0.0]])

    predictions = predict(train_features, train_targets, query_features, k=2)

    expected = (10.0 + 20.0) / 2
    np.testing.assert_array_almost_equal(predictions, [expected])


def test_predict_uses_k_nearest_not_all():
    """Test that only k nearest neighbors are used, not all."""
    train_features = np.array([
        [0.0, 0.0],
        [1.0, 0.0],
        [100.0, 0.0],
    ])
    train_targets = np.array([10.0, 20.0, 10000.0])
    query_features = np.array([[0.5, 0.0]])

    predictions_k2 = predict(train_features, train_targets, query_features, k=2)
    predictions_k3 = predict(train_features, train_targets, query_features, k=3)

    assert predictions_k2[0] == pytest.approx(15.0)
    assert predictions_k3[0] != predictions_k2[0]


def test_predict_output_shape():
    """Test that prediction output has correct shape."""
    train_features = np.array([[1.0, 2.0]])
    train_targets = np.array([10.0])
    query_features = np.array([[2.0, 3.0], [4.0, 5.0], [6.0, 7.0]])

    predictions = predict(train_features, train_targets, query_features)

    assert predictions.shape == (3,)


def test_predict_empty_training_data():
    """Test that prediction with no training data raises error."""
    train_features = np.empty((0, 2))
    train_targets = np.empty((0,))
    query_features = np.array([[2.0, 3.0]])

    with pytest.raises(ValueError, match="No training data"):
        predict(train_features, train_targets, query_features)


def test_predict_dimension_mismatch():
    """Test that dimension mismatch raises clear error."""
    train_features = np.array([[1.0, 2.0, 3.0]])
    train_targets = np.array([10.0])
    query_features = np.array([[1.0, 2.0]])

    with pytest.raises(ValueError, match="dimension mismatch"):
        predict(train_features, train_targets, query_features)


def test_predict_fewer_training_points_than_k():
    """Test graceful handling when n_train < k."""
    train_features = np.array([[0.0, 0.0], [1.0, 1.0]])
    train_targets = np.array([10.0, 20.0])
    query_features = np.array([[0.5, 0.5]])

    predictions = predict(train_features, train_targets, query_features, k=10)

    expected = (10.0 + 20.0) / 2
    np.testing.assert_array_almost_equal(predictions, [expected])


def test_predict_default_k():
    """Test that default k=5 is used."""
    train_features = np.array([
        [0.0], [1.0], [2.0], [3.0], [4.0], [100.0], [101.0],
    ])
    train_targets = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 100.0, 101.0])
    query_features = np.array([[2.0]])

    predictions = predict(train_features, train_targets, query_features)

    expected = (0.0 + 1.0 + 2.0 + 3.0 + 4.0) / 5
    np.testing.assert_array_almost_equal(predictions, [expected])


@pytest.mark.parametrize("invalid_k", [0, -1, -5])
def test_predict_invalid_k_raises_error(invalid_k):
    """Test that k < 1 raises ValueError."""
    train_features = np.array([[0.0, 0.0], [1.0, 1.0]])
    train_targets = np.array([1.0, 2.0])
    query_features = np.array([[0.5, 0.5]])

    with pytest.raises(ValueError, match="k must be"):
        predict(train_features, train_targets, query_features, k=invalid_k)


def test_predict_large_batch_consistent_results():
    """Test that batched processing produces consistent results."""
    from knn_cli.predictor import QUERY_BATCH_SIZE

    rng = np.random.default_rng(42)
    n_train = 100
    n_features = 10
    n_queries = QUERY_BATCH_SIZE + 50

    train_features = rng.random((n_train, n_features))
    train_targets = rng.random(n_train) * 100
    query_features = rng.random((n_queries, n_features))

    predictions = predict(train_features, train_targets, query_features, k=5)

    assert predictions.shape == (n_queries,)

    small_preds = predict(train_features, train_targets, query_features[:10], k=5)
    np.testing.assert_array_almost_equal(predictions[:10], small_preds)

    end_preds = predict(train_features, train_targets, query_features[-10:], k=5)
    np.testing.assert_array_almost_equal(predictions[-10:], end_preds)


def test_target_scale_performance():
    """Verify predictor handles target scale: 10k train, 10k query, 100 features."""
    import time

    rng = np.random.default_rng(12345)
    n_train = 10000
    n_query = 10000
    n_features = 100

    train_features = rng.random((n_train, n_features))
    train_targets = rng.random(n_train) * 100
    query_features = rng.random((n_query, n_features))

    start = time.perf_counter()
    predictions = predict(train_features, train_targets, query_features, k=5)
    elapsed = time.perf_counter() - start

    assert predictions.shape == (n_query,)
    assert np.all(np.isfinite(predictions))
    assert elapsed < 60.0  # should complete well under 60s
