"""Tests for the CSV I/O module."""

import inspect
import tempfile
from pathlib import Path

import numpy as np
import pytest

import knn_cli.csv_io as csv_io_module
from knn_cli.csv_io import read_query_csv, read_training_csv, write_predictions_csv


def test_read_training_csv():
    """Test reading a training CSV file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,target\n")
        f.write("1.0,2.0,10.0\n")
        f.write("3.0,4.0,20.0\n")
        filepath = f.name

    try:
        features, targets = read_training_csv(filepath)
        expected_features = np.array([[1.0, 2.0], [3.0, 4.0]])
        expected_targets = np.array([10.0, 20.0])

        np.testing.assert_array_equal(features, expected_features)
        np.testing.assert_array_equal(targets, expected_targets)
    finally:
        Path(filepath).unlink()


def test_read_training_csv_file_not_found():
    """Test that reading a non-existent file raises error."""
    with pytest.raises(FileNotFoundError, match="not found"):
        read_training_csv("/nonexistent/file.csv")


def test_read_training_csv_empty():
    """Test that reading an empty CSV raises error."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        filepath = f.name

    try:
        with pytest.raises(ValueError, match="empty"):
            read_training_csv(filepath)
    finally:
        Path(filepath).unlink()


def test_read_training_csv_header_only():
    """Test that reading a CSV with only header (no data rows) raises error."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,target\n")
        filepath = f.name

    try:
        with pytest.raises(ValueError, match="data rows"):
            read_training_csv(filepath)
    finally:
        Path(filepath).unlink()


def test_read_query_csv():
    """Test reading a query CSV file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b\n")
        f.write("1.0,2.0\n")
        f.write("3.0,4.0\n")
        filepath = f.name

    try:
        features = read_query_csv(filepath)
        expected = np.array([[1.0, 2.0], [3.0, 4.0]])
        np.testing.assert_array_equal(features, expected)
    finally:
        Path(filepath).unlink()


def test_read_query_csv_header_only():
    """Test that reading a query CSV with only header (no data rows) raises error."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b\n")
        filepath = f.name

    try:
        with pytest.raises(ValueError, match="data rows"):
            read_query_csv(filepath)
    finally:
        Path(filepath).unlink()


def test_write_predictions_csv():
    """Test writing predictions to a CSV file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "predictions.csv"
        predictions = np.array([1.5, 2.5, 3.5])

        write_predictions_csv(str(filepath), predictions)

        content = filepath.read_text()
        assert "prediction" in content
        assert "1.5" in content
        assert "2.5" in content
        assert "3.5" in content


def test_read_training_csv_non_numeric_value():
    """Test that non-numeric values in CSV raise ValueError."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,target\n")
        f.write("1.0,abc,10.0\n")
        filepath = f.name

    try:
        with pytest.raises(ValueError, match="Invalid"):
            read_training_csv(filepath)
    finally:
        Path(filepath).unlink()


def test_read_training_csv_rejects_nan_string():
    """Test that 'nan' string values are rejected as invalid."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,target\n")
        f.write("1.0,nan,10.0\n")
        filepath = f.name

    try:
        with pytest.raises(ValueError, match="[Ii]nvalid"):
            read_training_csv(filepath)
    finally:
        Path(filepath).unlink()


def test_read_training_csv_rejects_inf_string():
    """Test that 'inf' string values are rejected as invalid."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,target\n")
        f.write("1.0,inf,10.0\n")
        filepath = f.name

    try:
        with pytest.raises(ValueError, match="[Ii]nvalid"):
            read_training_csv(filepath)
    finally:
        Path(filepath).unlink()


def test_read_training_csv_rejects_negative_inf_string():
    """Test that '-inf' string values are rejected as invalid."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,target\n")
        f.write("1.0,-inf,10.0\n")
        filepath = f.name

    try:
        with pytest.raises(ValueError, match="[Ii]nvalid"):
            read_training_csv(filepath)
    finally:
        Path(filepath).unlink()


def test_read_query_csv_rejects_nan_string():
    """Test that 'nan' string values in query CSV are rejected."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b\n")
        f.write("1.0,nan\n")
        filepath = f.name

    try:
        with pytest.raises(ValueError, match="[Ii]nvalid"):
            read_query_csv(filepath)
    finally:
        Path(filepath).unlink()


def test_read_training_csv_inconsistent_row_lengths():
    """Test that rows with different column counts raise a clear error.

    Bug: Currently raises a confusing numpy error instead of a clear
    validation message as required by grounding.md.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,target\n")
        f.write("1.0,2.0,10.0\n")
        f.write("3.0,4.0\n")  # Missing target column
        filepath = f.name

    try:
        with pytest.raises(ValueError, match="column"):
            read_training_csv(filepath)
    finally:
        Path(filepath).unlink()


def test_write_predictions_csv_uses_atomic_writes():
    """Test that write_predictions_csv uses temp file + os.replace() pattern.

    Per style guide, writes that must not corrupt on failure should use
    atomic file operations. We verify this by checking that the function
    uses tempfile/os.replace patterns (not direct file writes).
    """
    source = inspect.getsource(csv_io_module.write_predictions_csv)

    uses_temp = "tempfile" in source or "mkstemp" in source
    uses_replace = "os.replace" in source or "replace(" in source

    assert uses_temp and uses_replace, (
        "write_predictions_csv should use atomic writes "
        "(temp file + os.replace pattern) like dataset.py does"
    )
