"""CSV file reading and writing utilities."""

import csv
import math
from pathlib import Path

import numpy as np


def _parse_row(row: list[str], line_num: int, filepath: str) -> list[float]:
    """Parse a CSV row into floats."""
    try:
        values = [float(v) for v in row]
    except ValueError as e:
        msg = f"Invalid numeric value at line {line_num} in {filepath}: {e}"
        raise ValueError(msg) from e

    for i, v in enumerate(values):
        if not math.isfinite(v):
            raw_val = row[i]
            msg = f"Invalid value at line {line_num} in {filepath}: '{raw_val}'"
            raise ValueError(msg)

    return values


def _read_csv_rows(filepath: str, file_type: str) -> list[list[float]]:
    """Read all data rows from a CSV file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"{file_type} file not found: {filepath}")

    rows = []
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            raise ValueError(f"CSV file is empty: {filepath}")

        expected_cols = len(header)
        for line_num, row in enumerate(reader, start=2):
            if not row:
                continue
            if len(row) != expected_cols:
                msg = (
                    f"Row {line_num} has {len(row)} columns, "
                    f"expected {expected_cols} in {filepath}"
                )
                raise ValueError(msg)
            rows.append(_parse_row(row, line_num, filepath))

    if not rows:
        raise ValueError(f"No data rows in CSV file: {filepath}")

    return rows


def read_training_csv(filepath: str) -> tuple[np.ndarray, np.ndarray]:
    """Read a training CSV file with features and target.

    The last column is treated as the target value.
    All other columns are features.
    """
    rows = _read_csv_rows(filepath, "Training")
    data = np.array(rows, dtype=np.float64)
    features = data[:, :-1]
    targets = data[:, -1]
    return features, targets


def read_query_csv(filepath: str) -> np.ndarray:
    """Read a query CSV file with features only."""
    rows = _read_csv_rows(filepath, "Query")
    return np.array(rows, dtype=np.float64)


def _write_csv_content(tmp_path: str, predictions: np.ndarray) -> None:
    """Write prediction content to a temporary file."""
    with open(tmp_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["prediction"])
        for pred in predictions:
            writer.writerow([pred])


def write_predictions_csv(filepath: str, predictions: np.ndarray) -> None:
    """Write predictions to a CSV file atomically."""
    import os
    import tempfile

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(suffix=".csv", dir=path.parent, prefix=".tmp_")
    os.close(fd)
    try:
        _write_csv_content(tmp_path, predictions)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
