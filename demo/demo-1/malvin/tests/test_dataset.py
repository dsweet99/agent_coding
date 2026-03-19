"""Tests for the dataset module."""

import numpy as np
import pytest

from knn_cli import dataset


def test_create_dataset(temp_data_dir):
    """Test creating a new dataset."""
    dataset.create_dataset("test_ds", 5)

    assert dataset.dataset_exists("test_ds")
    meta = dataset.load_dataset_meta("test_ds")
    assert meta["name"] == "test_ds"
    assert meta["dimension"] == 5
    assert meta["num_observations"] == 0


def test_create_dataset_invalid_dimension(temp_data_dir):
    """Test that creating a dataset with invalid dimension raises error."""
    with pytest.raises(ValueError, match="Dimension must be positive"):
        dataset.create_dataset("test_ds", 0)


def test_dataset_not_exists(temp_data_dir):
    """Test checking for non-existent dataset."""
    assert not dataset.dataset_exists("nonexistent")


def test_load_nonexistent_dataset(temp_data_dir):
    """Test loading a non-existent dataset raises error."""
    with pytest.raises(ValueError, match="does not exist"):
        dataset.load_dataset_meta("nonexistent")


def test_append_to_dataset(temp_data_dir):
    """Test appending data to a dataset."""
    dataset.create_dataset("test_ds", 3)

    features = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    targets = np.array([10.0, 20.0])

    dataset.append_to_dataset("test_ds", features, targets)

    loaded_features, loaded_targets = dataset.load_dataset_data("test_ds")
    np.testing.assert_array_equal(loaded_features, features)
    np.testing.assert_array_equal(loaded_targets, targets)

    meta = dataset.load_dataset_meta("test_ds")
    assert meta["num_observations"] == 2


def test_append_multiple_times(temp_data_dir):
    """Test appending data multiple times to a dataset."""
    dataset.create_dataset("test_ds", 2)

    features1 = np.array([[1.0, 2.0]])
    targets1 = np.array([10.0])
    dataset.append_to_dataset("test_ds", features1, targets1)

    features2 = np.array([[3.0, 4.0], [5.0, 6.0]])
    targets2 = np.array([20.0, 30.0])
    dataset.append_to_dataset("test_ds", features2, targets2)

    loaded_features, loaded_targets = dataset.load_dataset_data("test_ds")
    expected_features = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    expected_targets = np.array([10.0, 20.0, 30.0])

    np.testing.assert_array_equal(loaded_features, expected_features)
    np.testing.assert_array_equal(loaded_targets, expected_targets)


def test_append_dimension_mismatch(temp_data_dir):
    """Test that appending data with wrong dimension raises error."""
    dataset.create_dataset("test_ds", 3)

    features = np.array([[1.0, 2.0]])
    targets = np.array([10.0])

    with pytest.raises(ValueError, match="dimension mismatch"):
        dataset.append_to_dataset("test_ds", features, targets)


def _make_failing_replace(fail_on_call: int):
    """Create a mock os.replace that fails on the nth call."""
    import os

    original_replace = os.replace
    call_count = [0]

    def failing_replace(src, dst):
        call_count[0] += 1
        if call_count[0] == fail_on_call:
            raise OSError(f"Simulated disk failure on call {fail_on_call}")
        return original_replace(src, dst)

    return failing_replace


def test_append_failure_preserves_consistency(temp_data_dir):
    """Failed append must not leave features/targets out of sync.

    If os.replace succeeds for features but fails for targets,
    rollback must restore original features so counts remain equal.
    """
    from unittest import mock

    dataset.create_dataset("test_ds", 2)

    features1 = np.array([[1.0, 2.0]])
    targets1 = np.array([10.0])
    dataset.append_to_dataset("test_ds", features1, targets1)

    features2 = np.array([[3.0, 4.0]])
    targets2 = np.array([20.0])

    with (
        mock.patch("os.replace", _make_failing_replace(fail_on_call=2)),
        pytest.raises(OSError),
    ):
        dataset.append_to_dataset("test_ds", features2, targets2)

    f_after, t_after = dataset.load_dataset_data("test_ds")
    assert f_after.shape[0] == t_after.shape[0], (
        f"Features ({f_after.shape[0]}) and targets ({t_after.shape[0]}) "
        "count mismatch after failed append"
    )


def test_append_metadata_failure_preserves_consistency(temp_data_dir):
    """Failed metadata update must roll back both features and targets."""
    from unittest import mock

    dataset.create_dataset("test_ds", 2)

    features1 = np.array([[1.0, 2.0]])
    targets1 = np.array([10.0])
    dataset.append_to_dataset("test_ds", features1, targets1)

    features2 = np.array([[3.0, 4.0]])
    targets2 = np.array([20.0])

    with (
        mock.patch("os.replace", _make_failing_replace(fail_on_call=3)),
        pytest.raises(OSError),
    ):
        dataset.append_to_dataset("test_ds", features2, targets2)

    f_after, t_after = dataset.load_dataset_data("test_ds")
    meta = dataset.load_dataset_meta("test_ds")

    assert f_after.shape[0] == 1, f"Expected 1 feature row, got {f_after.shape[0]}"
    assert t_after.shape[0] == 1, f"Expected 1 target row, got {t_after.shape[0]}"
    assert meta["num_observations"] == 1, (
        f"Metadata claims {meta['num_observations']} observations, expected 1"
    )
