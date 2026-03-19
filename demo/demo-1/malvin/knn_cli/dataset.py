"""Dataset storage and management."""

import json
import os
import tempfile
from pathlib import Path

import numpy as np

DATA_DIR = Path.home() / ".knn_cli" / "datasets"


def get_dataset_dir(name: str) -> Path:
    """Get the directory for a dataset."""
    return DATA_DIR / name


def dataset_exists(name: str) -> bool:
    """Check if a dataset exists."""
    dataset_dir = get_dataset_dir(name)
    return dataset_dir.exists() and (dataset_dir / "meta.json").exists()


def create_dataset(name: str, dimension: int) -> None:
    """Create a new dataset with the specified dimensionality."""
    if dimension < 1:
        raise ValueError(f"Dimension must be positive, got {dimension}")

    dataset_dir = get_dataset_dir(name)
    dataset_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "name": name,
        "dimension": dimension,
        "num_observations": 0,
    }

    with open(dataset_dir / "meta.json", "w") as f:
        json.dump(meta, f)

    features_path = dataset_dir / "features.npy"
    targets_path = dataset_dir / "targets.npy"

    np.save(features_path, np.empty((0, dimension), dtype=np.float64))
    np.save(targets_path, np.empty((0,), dtype=np.float64))


def load_dataset_meta(name: str) -> dict:
    """Load dataset metadata."""
    if not dataset_exists(name):
        raise ValueError(f"Dataset '{name}' does not exist")

    dataset_dir = get_dataset_dir(name)
    with open(dataset_dir / "meta.json") as f:
        return json.load(f)


def load_dataset_data(name: str) -> tuple[np.ndarray, np.ndarray]:
    """Load dataset features and targets."""
    if not dataset_exists(name):
        raise ValueError(f"Dataset '{name}' does not exist")

    dataset_dir = get_dataset_dir(name)
    features = np.load(dataset_dir / "features.npy")
    targets = np.load(dataset_dir / "targets.npy")
    return features, targets


def _prepare_temp_npy(path: Path, array: np.ndarray) -> str:
    """Write array to temp file, return temp path. Caller must clean up."""
    fd, tmp_path = tempfile.mkstemp(
        suffix=".npy", dir=path.parent, prefix=".tmp_"
    )
    os.close(fd)
    np.save(tmp_path, array)
    return tmp_path


def _prepare_temp_json(path: Path, data: dict) -> str:
    """Write JSON to temp file, return temp path. Caller must clean up."""
    fd, tmp_path = tempfile.mkstemp(
        suffix=".json", dir=path.parent, prefix=".tmp_"
    )
    os.close(fd)
    with open(tmp_path, "w") as f:
        json.dump(data, f)
    return tmp_path


def _cleanup_temps(temps: list[str]) -> None:
    """Remove temp files, ignoring errors."""
    for t in temps:
        if t and os.path.exists(t):
            os.unlink(t)


def _rollback_features(features_path: Path, old_features: np.ndarray) -> None:
    """Restore features file to previous state."""
    backup = _prepare_temp_npy(features_path, old_features)
    os.replace(backup, features_path)


def _rollback_both(
    features_path: Path,
    targets_path: Path,
    old_features: np.ndarray,
    old_targets: np.ndarray,
) -> None:
    """Restore both features and targets to previous state."""
    feat_backup = _prepare_temp_npy(features_path, old_features)
    targ_backup = _prepare_temp_npy(targets_path, old_targets)
    os.replace(feat_backup, features_path)
    os.replace(targ_backup, targets_path)


def append_to_dataset(
    name: str, features: np.ndarray, targets: np.ndarray
) -> None:
    """Append observations to an existing dataset.

    Uses atomic file operations to ensure partial failures do not
    corrupt stored data. All three files (features, targets, metadata)
    are prepared first, then committed together with rollback on failure.
    """
    meta = load_dataset_meta(name)
    expected_dim = meta["dimension"]

    if features.shape[1] != expected_dim:
        got = features.shape[1]
        msg = f"Feature dimension mismatch: expected {expected_dim}, got {got}"
        raise ValueError(msg)

    if features.shape[0] != targets.shape[0]:
        msg = (
            f"Number of features ({features.shape[0]}) "
            f"must match number of targets ({targets.shape[0]})"
        )
        raise ValueError(msg)

    existing_features, existing_targets = load_dataset_data(name)

    new_features = np.vstack([existing_features, features])
    new_targets = np.concatenate([existing_targets, targets])
    meta["num_observations"] = new_features.shape[0]

    dataset_dir = get_dataset_dir(name)
    features_path = dataset_dir / "features.npy"
    targets_path = dataset_dir / "targets.npy"
    meta_path = dataset_dir / "meta.json"

    feat_tmp = targ_tmp = meta_tmp = None
    try:
        feat_tmp = _prepare_temp_npy(features_path, new_features)
        targ_tmp = _prepare_temp_npy(targets_path, new_targets)
        meta_tmp = _prepare_temp_json(meta_path, meta)
    except Exception:
        _cleanup_temps([feat_tmp, targ_tmp, meta_tmp])
        raise

    os.replace(feat_tmp, features_path)
    try:
        os.replace(targ_tmp, targets_path)
    except Exception:
        _rollback_features(features_path, existing_features)
        _cleanup_temps([meta_tmp])
        raise

    try:
        os.replace(meta_tmp, meta_path)
    except Exception:
        _rollback_both(
            features_path, targets_path, existing_features, existing_targets
        )
        raise
