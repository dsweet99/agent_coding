"""Tests for the CLI module."""

import subprocess
import sys
from unittest import mock

from knn_cli import dataset
from knn_cli.cli import build_parser, main


def test_cli_help():
    """Test that CLI help works."""
    result = subprocess.run(
        [sys.executable, "-m", "knn_cli.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "KNN Regression CLI" in result.stdout
    assert "create" in result.stdout
    assert "add-csv" in result.stdout
    assert "query-csv" in result.stdout


def test_create_help():
    """Test that create command help works."""
    result = subprocess.run(
        [sys.executable, "-m", "knn_cli.cli", "create", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--dataset" in result.stdout
    assert "--dimension" in result.stdout


def test_add_csv_help():
    """Test that add-csv command help works."""
    result = subprocess.run(
        [sys.executable, "-m", "knn_cli.cli", "add-csv", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--dataset" in result.stdout
    assert "--file" in result.stdout


def test_query_csv_help():
    """Test that query-csv command help works."""
    result = subprocess.run(
        [sys.executable, "-m", "knn_cli.cli", "query-csv", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--dataset" in result.stdout
    assert "--file" in result.stdout
    assert "--output" in result.stdout


def test_build_parser():
    """Test that build_parser creates a valid parser."""
    parser = build_parser()
    assert parser is not None
    assert parser.prog == "knn"


def test_build_parser_subcommands():
    """Test that parser has all required subcommands."""
    parser = build_parser()

    args = parser.parse_args(["create", "--dataset", "test", "--dimension", "5"])
    assert args.command == "create"
    assert args.dataset == "test"
    assert args.dimension == 5

    args = parser.parse_args(["add-csv", "--dataset", "test", "--file", "data.csv"])
    assert args.command == "add-csv"
    assert args.dataset == "test"
    assert args.file == "data.csv"

    args = parser.parse_args([
        "query-csv", "--dataset", "test", "--file", "q.csv", "--output", "out.csv"
    ])
    assert args.command == "query-csv"
    assert args.dataset == "test"
    assert args.file == "q.csv"
    assert args.output == "out.csv"


def test_main_no_command(capsys):
    """Test main with no command prints help."""
    with mock.patch("sys.argv", ["knn"]):
        result = main()
    assert result == 1
    captured = capsys.readouterr()
    assert "usage" in captured.out.lower() or "KNN" in captured.out


def test_main_create_command(temp_data_dir, capsys):
    """Test main with create command."""
    args = ["knn", "create", "--dataset", "test", "--dimension", "3"]
    with mock.patch("sys.argv", args):
        result = main()
    assert result == 0
    captured = capsys.readouterr()
    assert "Created dataset" in captured.out


def test_main_error_handling(temp_data_dir, capsys):
    """Test main handles ValueError appropriately."""
    with mock.patch("sys.argv", ["knn", "create", "--dataset", "", "--dimension", "3"]):
        result = main()
    assert result == 1
    captured = capsys.readouterr()
    assert "Error" in captured.err


def test_main_file_not_found(temp_data_dir, capsys):
    """Test main handles FileNotFoundError appropriately."""
    dataset.create_dataset("test_ds", 2)
    with mock.patch(
        "sys.argv", ["knn", "add-csv", "--dataset", "test_ds", "--file", "/nonexistent"]
    ):
        result = main()
    assert result == 1
    captured = capsys.readouterr()
    assert "Error" in captured.err


def test_main_create_duplicate_fails(temp_data_dir, capsys):
    """Create dataset via CLI, then create again without overwrite fails."""
    args = ["knn", "create", "--dataset", "dup_ds", "--dimension", "3"]
    with mock.patch("sys.argv", args):
        result = main()
    assert result == 0
    capsys.readouterr()

    with mock.patch("sys.argv", args):
        result = main()
    assert result == 1
    captured = capsys.readouterr()
    assert "Error" in captured.err
    assert "already exists" in captured.err


def test_main_create_with_overwrite(temp_data_dir, capsys):
    """Create dataset, then create again with --overwrite flag succeeds."""
    args = ["knn", "create", "--dataset", "ow_ds", "--dimension", "3"]
    with mock.patch("sys.argv", args):
        result = main()
    assert result == 0
    capsys.readouterr()

    args_overwrite = [
        "knn", "create", "--dataset", "ow_ds", "--dimension", "5", "--overwrite"
    ]
    with mock.patch("sys.argv", args_overwrite):
        result = main()
    assert result == 0
    captured = capsys.readouterr()
    assert "Created dataset" in captured.out


def test_main_query_empty_dataset(temp_data_dir, capsys):
    """Test query-csv on empty dataset returns error and prints 'no training data'."""
    dataset.create_dataset("empty_ds", 2)

    query_csv = temp_data_dir / "query.csv"
    query_csv.write_text("a,b\n1.0,2.0\n")

    output_path = temp_data_dir / "predictions.csv"

    with mock.patch(
        "sys.argv",
        [
            "knn", "query-csv",
            "--dataset", "empty_ds",
            "--file", str(query_csv),
            "--output", str(output_path),
        ],
    ):
        result = main()

    assert result == 1
    captured = capsys.readouterr()
    assert "Error" in captured.err
    assert "no training data" in captured.err


def test_main_handles_permission_error(temp_data_dir, capsys):
    """Test main handles PermissionError with clean error message."""
    dataset.create_dataset("perm_ds", 2)

    train_csv = temp_data_dir / "train.csv"
    train_csv.write_text("a,b,target\n1.0,2.0,10.0\n")

    query_csv = temp_data_dir / "query.csv"
    query_csv.write_text("a,b\n1.5,2.5\n")

    readonly_dir = temp_data_dir / "readonly"
    readonly_dir.mkdir()
    readonly_dir.chmod(0o444)

    try:
        args = [
            "knn", "query-csv",
            "--dataset", "perm_ds",
            "--file", str(query_csv),
            "--output", str(readonly_dir / "predictions.csv"),
        ]

        from knn_cli.commands import add_csv as add_csv_cmd
        add_csv_cmd("perm_ds", str(train_csv))
        capsys.readouterr()

        with mock.patch("sys.argv", args):
            result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err
    finally:
        readonly_dir.chmod(0o755)
