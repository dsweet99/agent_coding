"""Tests for command implementations."""

import tempfile
from pathlib import Path

import pytest

from knn_cli import dataset
from knn_cli.commands import add_csv, create, query_csv


def test_create_command(temp_data_dir, capsys):
    """Test the create command."""
    create("my_dataset", 5)
    captured = capsys.readouterr()
    assert "Created dataset 'my_dataset'" in captured.out
    assert dataset.dataset_exists("my_dataset")


def test_create_empty_name(temp_data_dir):
    """Test that empty dataset name raises error."""
    with pytest.raises(ValueError, match="cannot be empty"):
        create("", 5)


def test_create_invalid_dimension(temp_data_dir):
    """Test that invalid dimension raises error."""
    with pytest.raises(ValueError, match="must be positive"):
        create("my_dataset", 0)


def test_create_duplicate_without_overwrite(temp_data_dir):
    """Create dataset, then create again without overwrite raises ValueError."""
    create("dup_dataset", 5)
    with pytest.raises(ValueError, match="already exists"):
        create("dup_dataset", 5)


def test_create_duplicate_with_overwrite(temp_data_dir, capsys):
    """Create dataset, then create again with overwrite=True succeeds."""
    create("overwrite_dataset", 5)
    capsys.readouterr()
    create("overwrite_dataset", 3, overwrite=True)
    captured = capsys.readouterr()
    assert "Created dataset 'overwrite_dataset'" in captured.out
    assert dataset.dataset_exists("overwrite_dataset")


def test_add_csv_command(temp_data_dir, capsys):
    """Test the add-csv command."""
    create("my_dataset", 2)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,target\n")
        f.write("1.0,2.0,10.0\n")
        f.write("3.0,4.0,20.0\n")
        filepath = f.name

    try:
        add_csv("my_dataset", filepath)
        captured = capsys.readouterr()
        assert "Added 2 observations" in captured.out

        features, targets = dataset.load_dataset_data("my_dataset")
        assert features.shape == (2, 2)
        assert targets.shape == (2,)
    finally:
        Path(filepath).unlink()


def test_add_csv_nonexistent_dataset(temp_data_dir):
    """Test that adding to non-existent dataset raises error."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,target\n")
        f.write("1.0,10.0\n")
        filepath = f.name

    try:
        with pytest.raises(ValueError, match="does not exist"):
            add_csv("nonexistent", filepath)
    finally:
        Path(filepath).unlink()


def test_add_csv_empty_name(temp_data_dir):
    """Test that empty dataset name raises error."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,target\n")
        f.write("1.0,10.0\n")
        filepath = f.name

    try:
        with pytest.raises(ValueError, match="cannot be empty"):
            add_csv("", filepath)
    finally:
        Path(filepath).unlink()


def test_query_csv_command(temp_data_dir, capsys):
    """Test the query-csv command."""
    create("my_dataset", 2)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,target\n")
        f.write("1.0,2.0,10.0\n")
        f.write("3.0,4.0,20.0\n")
        train_file = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b\n")
        f.write("2.0,3.0\n")
        f.write("4.0,5.0\n")
        query_file = f.name

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "predictions.csv"

            add_csv("my_dataset", train_file)
            capsys.readouterr()

            query_csv("my_dataset", query_file, str(output_file))
            captured = capsys.readouterr()
            assert "Wrote 2 predictions" in captured.out

            assert output_file.exists()
            content = output_file.read_text()
            assert "prediction" in content
    finally:
        Path(train_file).unlink()
        Path(query_file).unlink()


def test_query_csv_empty_name(temp_data_dir):
    """Test that empty dataset name raises error."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a\n")
        f.write("1.0\n")
        filepath = f.name

    try:
        with pytest.raises(ValueError, match="cannot be empty"):
            query_csv("", filepath, "output.csv")
    finally:
        Path(filepath).unlink()


def test_end_to_end_workflow(temp_data_dir, capsys):
    """Test the full workflow: create, add-csv, query-csv."""
    create("workflow_test", 3)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("f1,f2,f3,target\n")
        f.write("1.0,2.0,3.0,100.0\n")
        f.write("4.0,5.0,6.0,200.0\n")
        train_file = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("f1,f2,f3\n")
        f.write("2.5,3.5,4.5\n")
        query_file = f.name

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "out.csv"

            add_csv("workflow_test", train_file)
            query_csv("workflow_test", query_file, str(output_file))

            assert output_file.exists()
            content = output_file.read_text().strip().split("\n")
            assert len(content) == 2

            pred_value = float(content[1])
            assert isinstance(pred_value, float)
    finally:
        Path(train_file).unlink()
        Path(query_file).unlink()


def test_add_csv_multiple_calls_cumulative(temp_data_dir, capsys):
    """Multiple add-csv calls increase training-set size cumulatively."""
    create("cumulative_ds", 2)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,target\n")
        f.write("1.0,2.0,10.0\n")
        f.write("3.0,4.0,20.0\n")
        file1 = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,target\n")
        f.write("5.0,6.0,30.0\n")
        file2 = f.name

    try:
        add_csv("cumulative_ds", file1)
        features, targets = dataset.load_dataset_data("cumulative_ds")
        assert features.shape[0] == 2

        add_csv("cumulative_ds", file2)
        features, targets = dataset.load_dataset_data("cumulative_ds")
        assert features.shape[0] == 3
        assert targets.shape[0] == 3

        meta = dataset.load_dataset_meta("cumulative_ds")
        assert meta["num_observations"] == 3
    finally:
        Path(file1).unlink()
        Path(file2).unlink()


def test_add_csv_invalid_file_preserves_existing_data(temp_data_dir):
    """Failed add attempt due to invalid CSV leaves existing data intact."""
    create("preserved_ds", 2)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,target\n")
        f.write("1.0,2.0,10.0\n")
        valid_file = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,target\n")
        f.write("1.0,nan,10.0\n")
        invalid_file = f.name

    try:
        add_csv("preserved_ds", valid_file)
        features_before, targets_before = dataset.load_dataset_data("preserved_ds")
        assert features_before.shape[0] == 1

        with pytest.raises(ValueError):
            add_csv("preserved_ds", invalid_file)

        features_after, targets_after = dataset.load_dataset_data("preserved_ds")
        assert features_after.shape[0] == 1
        assert features_after[0, 0] == 1.0
        assert targets_after[0] == 10.0
    finally:
        Path(valid_file).unlink()
        Path(invalid_file).unlink()


def test_add_csv_dimension_mismatch_preserves_data(temp_data_dir):
    """Failed add due to dimension mismatch leaves existing data intact."""
    create("dim_ds", 2)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,target\n")
        f.write("1.0,2.0,10.0\n")
        valid_file = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,c,target\n")
        f.write("1.0,2.0,3.0,10.0\n")
        wrong_dim_file = f.name

    try:
        add_csv("dim_ds", valid_file)
        features_before, _ = dataset.load_dataset_data("dim_ds")
        assert features_before.shape == (1, 2)

        with pytest.raises(ValueError, match="dimension mismatch"):
            add_csv("dim_ds", wrong_dim_file)

        features_after, _ = dataset.load_dataset_data("dim_ds")
        assert features_after.shape == (1, 2)
    finally:
        Path(valid_file).unlink()
        Path(wrong_dim_file).unlink()


def test_query_csv_repeated_calls_succeed(temp_data_dir, capsys):
    """Back-to-back query-csv calls with different files both succeed."""
    create("repeat_ds", 2)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,target\n")
        f.write("1.0,2.0,10.0\n")
        f.write("3.0,4.0,20.0\n")
        train_file = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b\n")
        f.write("2.0,3.0\n")
        query1 = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b\n")
        f.write("1.5,2.5\n")
        f.write("2.5,3.5\n")
        f.write("3.5,4.5\n")
        query2 = f.name

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out1 = Path(tmpdir) / "out1.csv"
            out2 = Path(tmpdir) / "out2.csv"

            add_csv("repeat_ds", train_file)
            capsys.readouterr()

            query_csv("repeat_ds", query1, str(out1))
            query_csv("repeat_ds", query2, str(out2))

            assert out1.exists()
            assert out2.exists()

            lines1 = out1.read_text().strip().split("\n")
            lines2 = out2.read_text().strip().split("\n")
            assert len(lines1) == 2  # header + 1 prediction
            assert len(lines2) == 4  # header + 3 predictions
    finally:
        Path(train_file).unlink()
        Path(query1).unlink()
        Path(query2).unlink()


def test_query_csv_preserves_row_order(temp_data_dir, capsys):
    """Output row order must match query row order."""
    create("order_ds", 1)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("x,target\n")
        f.write("0.0,0.0\n")
        f.write("1.0,10.0\n")
        f.write("2.0,20.0\n")
        f.write("3.0,30.0\n")
        f.write("4.0,40.0\n")
        f.write("5.0,50.0\n")
        f.write("6.0,60.0\n")
        f.write("7.0,70.0\n")
        f.write("8.0,80.0\n")
        f.write("9.0,90.0\n")
        f.write("10.0,100.0\n")
        train_file = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("x\n")
        f.write("9.0\n")
        f.write("1.0\n")
        f.write("5.0\n")
        query_file = f.name

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "preds.csv"

            add_csv("order_ds", train_file)
            capsys.readouterr()

            query_csv("order_ds", query_file, str(out_file))

            lines = out_file.read_text().strip().split("\n")
            assert len(lines) == 4  # header + 3 predictions

            pred1 = float(lines[1])
            pred2 = float(lines[2])
            pred3 = float(lines[3])

            assert pred1 > pred3 > pred2
    finally:
        Path(train_file).unlink()
        Path(query_file).unlink()


def test_query_csv_invalid_file_preserves_dataset(temp_data_dir, capsys):
    """Invalid query file fails without modifying dataset state."""
    create("preserve_ds", 2)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,target\n")
        f.write("1.0,2.0,10.0\n")
        train_file = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b\n")
        f.write("1.0,nan\n")
        invalid_query = f.name

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "preds.csv"

            add_csv("preserve_ds", train_file)
            features_before, targets_before = dataset.load_dataset_data("preserve_ds")
            capsys.readouterr()

            with pytest.raises(ValueError):
                query_csv("preserve_ds", invalid_query, str(out_file))

            features_after, targets_after = dataset.load_dataset_data("preserve_ds")
            assert features_after.shape == features_before.shape
            assert targets_after.shape == targets_before.shape
            assert features_after[0, 0] == features_before[0, 0]
    finally:
        Path(train_file).unlink()
        Path(invalid_query).unlink()


def test_query_csv_dimension_mismatch(temp_data_dir, capsys):
    """Query with wrong dimension fails with clear error."""
    create("dim_query_ds", 2)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,target\n")
        f.write("1.0,2.0,10.0\n")
        train_file = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b,c\n")
        f.write("1.0,2.0,3.0\n")
        wrong_dim_query = f.name

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "preds.csv"

            add_csv("dim_query_ds", train_file)
            capsys.readouterr()

            with pytest.raises(ValueError, match="dimension mismatch"):
                query_csv("dim_query_ds", wrong_dim_query, str(out_file))
    finally:
        Path(train_file).unlink()
        Path(wrong_dim_query).unlink()


def test_query_csv_empty_dataset(temp_data_dir):
    """Query on dataset with no training data raises ValueError."""
    create("empty_ds", 2)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("a,b\n")
        f.write("1.0,2.0\n")
        query_file = f.name

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "preds.csv"

            with pytest.raises(ValueError, match="no training data"):
                query_csv("empty_ds", query_file, str(out_file))
    finally:
        Path(query_file).unlink()


def test_deterministic_output_same_data_same_result(temp_data_dir, capsys):
    """Same data and settings produce identical predictions across runs."""
    create("det_ds", 3)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("f1,f2,f3,target\n")
        for i in range(20):
            f.write(f"{i*0.1},{i*0.2},{i*0.3},{i*10.0}\n")
        train_file = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("f1,f2,f3\n")
        f.write("0.5,1.0,1.5\n")
        f.write("1.0,2.0,3.0\n")
        f.write("1.5,3.0,4.5\n")
        query_file = f.name

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out1 = Path(tmpdir) / "pred1.csv"
            out2 = Path(tmpdir) / "pred2.csv"

            add_csv("det_ds", train_file)
            capsys.readouterr()

            query_csv("det_ds", query_file, str(out1))
            query_csv("det_ds", query_file, str(out2))

            content1 = out1.read_text()
            content2 = out2.read_text()
            assert content1 == content2

            lines = content1.strip().split("\n")
            assert len(lines) == 4
    finally:
        Path(train_file).unlink()
        Path(query_file).unlink()


def test_deterministic_output_fresh_dataset_same_result(temp_data_dir, capsys):
    """Recreating dataset from scratch produces identical predictions."""
    import numpy as np

    train_content = "f1,f2,target\n1.0,2.0,10.0\n3.0,4.0,20.0\n5.0,6.0,30.0\n"
    query_content = "f1,f2\n2.0,3.0\n4.0,5.0\n"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(train_content)
        train_file = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(query_content)
        query_file = f.name

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out1 = Path(tmpdir) / "pred1.csv"

            create("det_fresh_1", 2)
            add_csv("det_fresh_1", train_file)
            capsys.readouterr()
            query_csv("det_fresh_1", query_file, str(out1))

            preds1 = [
                float(line)
                for line in out1.read_text().strip().split("\n")[1:]
            ]

            out2 = Path(tmpdir) / "pred2.csv"
            create("det_fresh_2", 2)
            add_csv("det_fresh_2", train_file)
            capsys.readouterr()
            query_csv("det_fresh_2", query_file, str(out2))

            preds2 = [
                float(line)
                for line in out2.read_text().strip().split("\n")[1:]
            ]

            np.testing.assert_array_almost_equal(preds1, preds2)
    finally:
        Path(train_file).unlink()
        Path(query_file).unlink()
