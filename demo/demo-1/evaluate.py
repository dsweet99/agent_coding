#!/usr/bin/env python3
"""Evaluate a KNN CLI implementation on a fixed synthetic benchmark.

This script is intentionally standalone (stdlib + numpy only) and drives a CLI
tool via subprocess. It generates reproducible train/test data, loads training
data through the CLI, requests predictions for test inputs, and reports out-of-
sample RMSE.

Required CLI contract:
  1) Create dataset:
       <cli> create --dataset <name> --dimension <int>
  2) Add training rows from CSV:
       <cli> add-csv --dataset <name> --file <train_csv>
  3) Predict from CSV:
       <cli> query-csv --dataset <name> --file <test_csv> --output <pred_csv>

Data format:
  - train_csv: x0..x{d-1},y (header row required)
  - test_csv:  x0..x{d-1}    (header row required)
  - pred_csv:  one numeric prediction per row; optional header allowed
"""

from __future__ import annotations

import argparse
import math
import shlex
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class EvalConfig:
    cli: str
    dataset: str
    n_train: int
    n_test: int
    dimension: int
    train_chunks: int
    test_chunks: int
    seed: int
    noise_std: float
    work_dir: Path | None
    keep_files: bool


def _parse_args() -> EvalConfig:
    parser = argparse.ArgumentParser(
        description=(
            "Run deterministic KNN benchmark by calling the candidate CLI and "
            "report out-of-sample RMSE."
        )
    )
    parser.add_argument(
        "cli",
        help='CLI command prefix, e.g. "python -m knn_app".',
    )
    parser.add_argument("--dataset", default="benchmark", help="Dataset name/id for the CLI.")
    parser.add_argument("--n-train", type=int, default=10_000, help="Training observations.")
    parser.add_argument("--n-test", type=int, default=10_000, help="Test observations.")
    parser.add_argument("--dimension", type=int, default=100, help="Feature count.")
    parser.add_argument(
        "--train-chunks",
        type=int,
        default=10,
        help="Number of add-csv calls (training data chunks).",
    )
    parser.add_argument(
        "--test-chunks",
        type=int,
        default=10,
        help="Number of query-csv calls (test data chunks).",
    )
    parser.add_argument("--seed", type=int, default=20260318, help="Random seed.")
    parser.add_argument("--noise-std", type=float, default=0.10, help="Noise std for DGP.")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Optional work directory. Defaults to a temporary directory.",
    )
    parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Keep generated CSVs (useful for debugging).",
    )
    args = parser.parse_args()

    if (
        args.n_train <= 0
        or args.n_test <= 0
        or args.dimension <= 0
        or args.train_chunks <= 0
        or args.test_chunks <= 0
    ):
        raise SystemExit(
            "n-train, n-test, dimension, train-chunks, and test-chunks must all be positive."
        )
    if args.noise_std < 0:
        raise SystemExit("noise-std must be non-negative.")

    return EvalConfig(
        cli=args.cli,
        dataset=args.dataset,
        n_train=args.n_train,
        n_test=args.n_test,
        dimension=args.dimension,
        train_chunks=args.train_chunks,
        test_chunks=args.test_chunks,
        seed=args.seed,
        noise_std=args.noise_std,
        work_dir=args.work_dir,
        keep_files=args.keep_files,
    )


def _dgp(
    *,
    rng: np.random.Generator,
    n_train: int,
    n_test: int,
    d: int,
    noise_std: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate deterministic benchmark data from a smooth nonlinear function."""
    x_train = rng.normal(0.0, 1.0, size=(n_train, d))
    x_test = rng.normal(0.0, 1.0, size=(n_test, d))

    w_linear = rng.normal(0.0, 1.0, size=d)
    w_nonlinear = rng.normal(0.0, 1.0, size=d)
    w_quadratic = rng.normal(0.0, 0.25, size=d)

    def signal(x: np.ndarray) -> np.ndarray:
        linear = x @ w_linear
        nonlinear = 0.35 * np.sin((x @ w_nonlinear) / math.sqrt(d))
        quadratic = 0.05 * ((x * x) @ w_quadratic)
        return linear + nonlinear + quadratic

    y_train = signal(x_train) + rng.normal(0.0, noise_std, size=n_train)
    y_test = signal(x_test) + rng.normal(0.0, noise_std, size=n_test)
    return x_train, y_train, x_test, y_test


def _write_train_csv(path: Path, x: np.ndarray, y: np.ndarray) -> None:
    header = ",".join([f"x{i}" for i in range(x.shape[1])] + ["y"])
    train_matrix = np.column_stack([x, y])
    np.savetxt(path, train_matrix, delimiter=",", header=header, comments="", fmt="%.10f")


def _write_test_csv(path: Path, x: np.ndarray) -> None:
    header = ",".join([f"x{i}" for i in range(x.shape[1])])
    np.savetxt(path, x, delimiter=",", header=header, comments="", fmt="%.10f")


def _read_predictions(path: Path, expected_rows: int) -> np.ndarray:
    raw = np.genfromtxt(path, delimiter=",", dtype=np.float64)
    if raw.size == 0:
        raise RuntimeError(f"Prediction file is empty: {path}")

    if raw.ndim == 0:
        preds = np.array([float(raw)], dtype=np.float64)
    elif raw.ndim == 1:
        preds = raw.astype(np.float64, copy=False)
    else:
        preds = raw[:, 0].astype(np.float64, copy=False)

    if preds.shape[0] == expected_rows:
        return preds

    # Try again skipping one header row.
    raw_skip = np.genfromtxt(path, delimiter=",", dtype=np.float64, skip_header=1)
    if raw_skip.size == 0:
        raise RuntimeError(
            f"Prediction row count mismatch: expected {expected_rows}, got {preds.shape[0]} "
            f"for {path}"
        )
    if raw_skip.ndim == 0:
        preds_skip = np.array([float(raw_skip)], dtype=np.float64)
    elif raw_skip.ndim == 1:
        preds_skip = raw_skip.astype(np.float64, copy=False)
    else:
        preds_skip = raw_skip[:, 0].astype(np.float64, copy=False)

    if preds_skip.shape[0] != expected_rows:
        raise RuntimeError(
            f"Prediction row count mismatch: expected {expected_rows}, got {preds_skip.shape[0]} "
            f"for {path}"
        )
    return preds_skip


def _run_cli(prefix: str, args: list[str]) -> float:
    command = shlex.split(prefix) + args
    start = time.perf_counter()
    completed = subprocess.run(command, capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(command)}\n{err}")
    return elapsed


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def _chunk_slices(total_rows: int, chunk_count: int) -> list[tuple[int, int]]:
    """Return [start, end) slices that cover all rows in order."""
    if chunk_count > total_rows:
        chunk_count = total_rows
    base = total_rows // chunk_count
    remainder = total_rows % chunk_count
    slices: list[tuple[int, int]] = []
    start = 0
    for idx in range(chunk_count):
        size = base + (1 if idx < remainder else 0)
        end = start + size
        slices.append((start, end))
        start = end
    return slices


def _evaluate(config: EvalConfig) -> dict[str, float]:
    rng = np.random.default_rng(config.seed)
    x_train, y_train, x_test, y_test = _dgp(
        rng=rng,
        n_train=config.n_train,
        n_test=config.n_test,
        d=config.dimension,
        noise_std=config.noise_std,
    )

    context_manager = (
        tempfile.TemporaryDirectory(prefix="knn_eval_")
        if config.work_dir is None
        else None
    )
    base_dir = config.work_dir if config.work_dir is not None else Path(context_manager.__enter__())
    base_dir = Path(base_dir).resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    train_slices = _chunk_slices(config.n_train, config.train_chunks)
    test_slices = _chunk_slices(config.n_test, config.test_chunks)

    train_csv_paths: list[Path] = []
    for idx, (start, end) in enumerate(train_slices):
        path = base_dir / f"train_chunk_{idx:03d}.csv"
        _write_train_csv(path, x_train[start:end], y_train[start:end])
        train_csv_paths.append(path)

    test_csv_paths: list[Path] = []
    pred_csv_paths: list[Path] = []
    for idx, (start, end) in enumerate(test_slices):
        test_path = base_dir / f"test_chunk_{idx:03d}.csv"
        pred_path = base_dir / f"pred_chunk_{idx:03d}.csv"
        _write_test_csv(test_path, x_test[start:end])
        test_csv_paths.append(test_path)
        pred_csv_paths.append(pred_path)

    try:
        t_create = _run_cli(
            config.cli,
            [
                "create",
                "--dataset",
                config.dataset,
                "--dimension",
                str(config.dimension),
            ],
        )
        t_add = 0.0
        for train_csv in train_csv_paths:
            t_add += _run_cli(
                config.cli,
                ["add-csv", "--dataset", config.dataset, "--file", str(train_csv)],
            )

        t_query = 0.0
        preds_parts: list[np.ndarray] = []
        for expected_rows, test_csv, pred_csv in zip(
            (end - start for start, end in test_slices),
            test_csv_paths,
            pred_csv_paths,
            strict=True,
        ):
            t_query += _run_cli(
                config.cli,
                [
                    "query-csv",
                    "--dataset",
                    config.dataset,
                    "--file",
                    str(test_csv),
                    "--output",
                    str(pred_csv),
                ],
            )
            preds_parts.append(_read_predictions(pred_csv, expected_rows=expected_rows))

        preds = np.concatenate(preds_parts)
        rmse = _rmse(y_test, preds)
    finally:
        if context_manager is not None and not config.keep_files:
            context_manager.__exit__(None, None, None)

    return {
        "rmse": rmse,
        "time_create_s": t_create,
        "time_add_s": t_add,
        "time_query_s": t_query,
        "time_total_s": t_create + t_add + t_query,
    }


def main() -> None:
    config = _parse_args()
    metrics = _evaluate(config)
    print(
        "EVAL_RESULT "
        f"dataset={config.dataset} "
        f"seed={config.seed} "
        f"n_train={config.n_train} "
        f"n_test={config.n_test} "
        f"dimension={config.dimension} "
        f"train_chunks={config.train_chunks} "
        f"test_chunks={config.test_chunks} "
        f"rmse={metrics['rmse']:.8f} "
        f"time_create_s={metrics['time_create_s']:.6f} "
        f"time_add_s={metrics['time_add_s']:.6f} "
        f"time_query_s={metrics['time_query_s']:.6f} "
        f"time_total_s={metrics['time_total_s']:.6f}"
    )


if __name__ == "__main__":
    main()
