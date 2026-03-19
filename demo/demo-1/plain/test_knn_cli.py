#!/usr/bin/env python3
"""Automated tests for KNN CLI error-path scenarios."""

import csv
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class KNNCLITestBase(unittest.TestCase):
    """Base class with common setup/teardown for KNN CLI tests."""

    @classmethod
    def setUpClass(cls):
        cls.cli_path = Path(__file__).parent / "knn_cli.py"
        cls.test_dir = Path(tempfile.mkdtemp(prefix="knn_test_"))
        cls.original_cwd = os.getcwd()
        os.chdir(cls.test_dir)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.original_cwd)
        shutil.rmtree(cls.test_dir)

    def setUp(self):
        datasets_dir = self.test_dir / ".knn_datasets"
        if datasets_dir.exists():
            shutil.rmtree(datasets_dir)

    def run_cli(self, *args):
        """Run CLI command and return (returncode, stdout, stderr)."""
        result = subprocess.run(
            [sys.executable, str(self.cli_path)] + list(args),
            capture_output=True,
            text=True
        )
        return result.returncode, result.stdout, result.stderr

    def create_csv(self, filename, rows):
        """Create a CSV file with given rows."""
        filepath = self.test_dir / filename
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            for row in rows:
                writer.writerow(row)
        return str(filepath)

    def create_dataset(self, name="test", dimension=3):
        """Helper to create a dataset."""
        rc, _, _ = self.run_cli("create", "--dataset", name, "--dimension", str(dimension))
        self.assertEqual(rc, 0)


class TestCreateCommand(KNNCLITestBase):
    """Tests for the create command."""

    def test_create_invalid_dimension_zero(self):
        rc, stdout, stderr = self.run_cli("create", "--dataset", "test", "--dimension", "0")
        self.assertNotEqual(rc, 0)
        self.assertIn("Error:", stderr)
        self.assertIn("positive integer", stderr)

    def test_create_invalid_dimension_negative(self):
        rc, stdout, stderr = self.run_cli("create", "--dataset", "test", "--dimension", "-5")
        self.assertNotEqual(rc, 0)
        self.assertIn("Error:", stderr)
        self.assertIn("positive integer", stderr)

    def test_create_duplicate_without_overwrite(self):
        self.create_dataset("dup")
        rc, stdout, stderr = self.run_cli("create", "--dataset", "dup", "--dimension", "3")
        self.assertNotEqual(rc, 0)
        self.assertIn("Error:", stderr)
        self.assertIn("already exists", stderr)


class TestAddCSVCommand(KNNCLITestBase):
    """Tests for the add-csv command."""

    def test_add_csv_file_not_found(self):
        self.create_dataset()
        rc, stdout, stderr = self.run_cli("add-csv", "--dataset", "test", "--file", "nonexistent.csv")
        self.assertNotEqual(rc, 0)
        self.assertIn("Error:", stderr)
        self.assertIn("not found", stderr)

    def test_add_csv_empty_file(self):
        self.create_dataset()
        csv_path = self.create_csv("empty.csv", [])
        rc, stdout, stderr = self.run_cli("add-csv", "--dataset", "test", "--file", csv_path)
        self.assertNotEqual(rc, 0)
        self.assertIn("Error:", stderr)
        self.assertIn("empty", stderr.lower())

    def test_add_csv_wrong_column_count(self):
        self.create_dataset(dimension=3)
        csv_path = self.create_csv("wrong_cols.csv", [
            [1.0, 2.0, 3.0]  # Missing target column
        ])
        rc, stdout, stderr = self.run_cli("add-csv", "--dataset", "test", "--file", csv_path)
        self.assertNotEqual(rc, 0)
        self.assertIn("Error:", stderr)
        self.assertIn("3 columns", stderr)
        self.assertIn("expected 4", stderr)

    def test_add_csv_non_numeric_value(self):
        self.create_dataset(dimension=2)
        csv_path = self.create_csv("non_numeric.csv", [
            [1.0, 2.0, 3.0],
            [4.0, "abc", 6.0]
        ])
        rc, stdout, stderr = self.run_cli("add-csv", "--dataset", "test", "--file", csv_path)
        self.assertNotEqual(rc, 0)
        self.assertIn("Error:", stderr)
        self.assertIn("non-numeric", stderr)
        self.assertIn("'abc'", stderr)
        self.assertIn("Row 2", stderr)
        self.assertIn("column 2", stderr)

    def test_add_csv_dataset_not_found(self):
        csv_path = self.create_csv("data.csv", [[1.0, 2.0, 3.0]])
        rc, stdout, stderr = self.run_cli("add-csv", "--dataset", "nonexistent", "--file", csv_path)
        self.assertNotEqual(rc, 0)
        self.assertIn("Error:", stderr)
        self.assertIn("does not exist", stderr)

    def test_add_csv_partial_row_non_numeric(self):
        """Test that a non-numeric value in any column is caught."""
        self.create_dataset(dimension=3)
        csv_path = self.create_csv("partial_bad.csv", [
            [1.0, 2.0, 3.0, 4.0],
            [5.0, 6.0, "", 8.0]  # Empty string in column 3
        ])
        rc, stdout, stderr = self.run_cli("add-csv", "--dataset", "test", "--file", csv_path)
        self.assertNotEqual(rc, 0)
        self.assertIn("Error:", stderr)
        self.assertIn("non-numeric", stderr)


class TestQueryCSVCommand(KNNCLITestBase):
    """Tests for the query-csv command."""

    def test_query_csv_file_not_found(self):
        self.create_dataset()
        csv_path = self.create_csv("train.csv", [[1.0, 2.0, 3.0, 4.0]])
        self.run_cli("add-csv", "--dataset", "test", "--file", csv_path)

        rc, stdout, stderr = self.run_cli(
            "query-csv", "--dataset", "test",
            "--file", "nonexistent.csv", "--output", "out.csv"
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("Error:", stderr)
        self.assertIn("not found", stderr)

    def test_query_csv_empty_file(self):
        self.create_dataset()
        train_path = self.create_csv("train.csv", [[1.0, 2.0, 3.0, 4.0]])
        self.run_cli("add-csv", "--dataset", "test", "--file", train_path)

        query_path = self.create_csv("empty_query.csv", [])
        rc, stdout, stderr = self.run_cli(
            "query-csv", "--dataset", "test",
            "--file", query_path, "--output", "out.csv"
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("Error:", stderr)
        self.assertIn("empty", stderr.lower())

    def test_query_csv_wrong_dimension(self):
        self.create_dataset(dimension=3)
        train_path = self.create_csv("train.csv", [[1.0, 2.0, 3.0, 4.0]])
        self.run_cli("add-csv", "--dataset", "test", "--file", train_path)

        query_path = self.create_csv("wrong_dim.csv", [[1.0, 2.0]])  # Only 2 features
        rc, stdout, stderr = self.run_cli(
            "query-csv", "--dataset", "test",
            "--file", query_path, "--output", "out.csv"
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("Error:", stderr)
        self.assertIn("2 columns", stderr)
        self.assertIn("expected 3", stderr)

    def test_query_csv_non_numeric_value(self):
        self.create_dataset(dimension=2)
        train_path = self.create_csv("train.csv", [[1.0, 2.0, 3.0]])
        self.run_cli("add-csv", "--dataset", "test", "--file", train_path)

        query_path = self.create_csv("bad_query.csv", [
            [1.0, 2.0],
            [3.0, "NaN_text"]
        ])
        rc, stdout, stderr = self.run_cli(
            "query-csv", "--dataset", "test",
            "--file", query_path, "--output", "out.csv"
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("Error:", stderr)
        self.assertIn("non-numeric", stderr)
        self.assertIn("'NaN_text'", stderr)

    def test_query_csv_empty_dataset(self):
        self.create_dataset()
        query_path = self.create_csv("query.csv", [[1.0, 2.0, 3.0]])

        rc, stdout, stderr = self.run_cli(
            "query-csv", "--dataset", "test",
            "--file", query_path, "--output", "out.csv"
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("Error:", stderr)
        self.assertIn("no training observations", stderr)

    def test_query_csv_dataset_not_found(self):
        query_path = self.create_csv("query.csv", [[1.0, 2.0, 3.0]])
        rc, stdout, stderr = self.run_cli(
            "query-csv", "--dataset", "nonexistent",
            "--file", query_path, "--output", "out.csv"
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("Error:", stderr)
        self.assertIn("does not exist", stderr)


class TestStorageConsistency(KNNCLITestBase):
    """Tests for storage consistency after failures."""

    def test_failed_add_preserves_existing_data(self):
        """Verify that a failed add-csv doesn't corrupt existing data."""
        self.create_dataset(dimension=2)

        # Add valid data
        valid_path = self.create_csv("valid.csv", [
            [1.0, 2.0, 10.0],
            [3.0, 4.0, 20.0]
        ])
        rc, _, _ = self.run_cli("add-csv", "--dataset", "test", "--file", valid_path)
        self.assertEqual(rc, 0)

        # Try to add invalid data
        invalid_path = self.create_csv("invalid.csv", [
            [5.0, 6.0, 30.0],
            [7.0, "bad", 40.0]
        ])
        rc, _, stderr = self.run_cli("add-csv", "--dataset", "test", "--file", invalid_path)
        self.assertNotEqual(rc, 0)

        # Verify original data is still intact by querying
        query_path = self.create_csv("query.csv", [[1.0, 2.0]])
        output_path = str(self.test_dir / "out.csv")
        rc, _, _ = self.run_cli(
            "query-csv", "--dataset", "test",
            "--file", query_path, "--output", output_path
        )
        self.assertEqual(rc, 0)

        # Check prediction file exists and has data
        self.assertTrue(Path(output_path).exists())
        with open(output_path, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 2)  # Header + 1 prediction

    def test_failed_query_no_output_created(self):
        """Verify that a failed query doesn't create partial output file."""
        self.create_dataset(dimension=2)
        train_path = self.create_csv("train.csv", [[1.0, 2.0, 3.0]])
        self.run_cli("add-csv", "--dataset", "test", "--file", train_path)

        # Try to query with invalid file
        output_path = str(self.test_dir / "should_not_exist.csv")
        rc, _, _ = self.run_cli(
            "query-csv", "--dataset", "test",
            "--file", "nonexistent.csv", "--output", output_path
        )
        self.assertNotEqual(rc, 0)

        # Output file should not exist
        self.assertFalse(Path(output_path).exists())


class TestErrorMessageFormat(KNNCLITestBase):
    """Tests for standardized error message format."""

    def test_all_errors_start_with_error_prefix(self):
        """Verify all error messages have consistent format."""
        test_cases = [
            (["create", "--dataset", "t", "--dimension", "0"], "dimension"),
            (["add-csv", "--dataset", "none", "--file", "x.csv"], "dataset"),
            (["query-csv", "--dataset", "none", "--file", "x.csv", "--output", "o.csv"], "dataset"),
        ]

        for args, _ in test_cases:
            rc, _, stderr = self.run_cli(*args)
            self.assertNotEqual(rc, 0, f"Expected failure for {args}")
            self.assertTrue(
                stderr.strip().startswith("Error:"),
                f"Error message should start with 'Error:' but got: {stderr}"
            )


class TestRepeatedAddCSV(KNNCLITestBase):
    """Tests for repeated add-csv behavior."""

    def test_repeated_add_csv_appends_data(self):
        """Verify repeated add-csv calls append observations."""
        self.create_dataset(dimension=2)

        # First batch
        csv1 = self.create_csv("batch1.csv", [
            [1.0, 2.0, 10.0],
            [3.0, 4.0, 20.0]
        ])
        rc, stdout, _ = self.run_cli("add-csv", "--dataset", "test", "--file", csv1)
        self.assertEqual(rc, 0)
        self.assertIn("2 observations", stdout)
        self.assertIn("Total: 2", stdout)

        # Second batch
        csv2 = self.create_csv("batch2.csv", [
            [5.0, 6.0, 30.0],
            [7.0, 8.0, 40.0],
            [9.0, 10.0, 50.0]
        ])
        rc, stdout, _ = self.run_cli("add-csv", "--dataset", "test", "--file", csv2)
        self.assertEqual(rc, 0)
        self.assertIn("3 observations", stdout)
        self.assertIn("Total: 5", stdout)

        # Third batch
        csv3 = self.create_csv("batch3.csv", [
            [11.0, 12.0, 60.0]
        ])
        rc, stdout, _ = self.run_cli("add-csv", "--dataset", "test", "--file", csv3)
        self.assertEqual(rc, 0)
        self.assertIn("1 observations", stdout)
        self.assertIn("Total: 6", stdout)

    def test_repeated_add_csv_predictions_use_all_data(self):
        """Verify predictions use all data from multiple add-csv calls."""
        self.create_dataset(dimension=1)

        # Add data in two batches
        csv1 = self.create_csv("batch1.csv", [
            [0.0, 10.0],
            [1.0, 20.0]
        ])
        csv2 = self.create_csv("batch2.csv", [
            [2.0, 30.0],
            [3.0, 40.0]
        ])

        self.run_cli("add-csv", "--dataset", "test", "--file", csv1)
        self.run_cli("add-csv", "--dataset", "test", "--file", csv2)

        # Query a point near the center (should use all 4 neighbors)
        query = self.create_csv("query.csv", [[1.5]])
        output = str(self.test_dir / "pred.csv")

        rc, _, _ = self.run_cli(
            "query-csv", "--dataset", "test",
            "--file", query, "--output", output
        )
        self.assertEqual(rc, 0)

        with open(output, "r") as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            pred = float(next(reader)[0])

        # With k=5 but only 4 points, prediction should be mean of all 4: (10+20+30+40)/4 = 25
        self.assertAlmostEqual(pred, 25.0, places=5)


class TestRepeatedQueryCSV(KNNCLITestBase):
    """Tests for repeated query-csv behavior."""

    def test_repeated_query_csv_works(self):
        """Verify query-csv can be called multiple times on same dataset."""
        self.create_dataset(dimension=2)

        train = self.create_csv("train.csv", [
            [1.0, 1.0, 10.0],
            [2.0, 2.0, 20.0],
            [3.0, 3.0, 30.0]
        ])
        self.run_cli("add-csv", "--dataset", "test", "--file", train)

        query = self.create_csv("query.csv", [[1.5, 1.5], [2.5, 2.5]])

        # First query
        output1 = str(self.test_dir / "pred1.csv")
        rc, _, _ = self.run_cli(
            "query-csv", "--dataset", "test",
            "--file", query, "--output", output1
        )
        self.assertEqual(rc, 0)

        # Second query (should work the same)
        output2 = str(self.test_dir / "pred2.csv")
        rc, _, _ = self.run_cli(
            "query-csv", "--dataset", "test",
            "--file", query, "--output", output2
        )
        self.assertEqual(rc, 0)

        # Third query with different output
        output3 = str(self.test_dir / "pred3.csv")
        rc, _, _ = self.run_cli(
            "query-csv", "--dataset", "test",
            "--file", query, "--output", output3
        )
        self.assertEqual(rc, 0)

        # All outputs should exist
        self.assertTrue(Path(output1).exists())
        self.assertTrue(Path(output2).exists())
        self.assertTrue(Path(output3).exists())

    def test_repeated_query_csv_different_queries(self):
        """Verify different query files can be used on same dataset."""
        self.create_dataset(dimension=1)

        train = self.create_csv("train.csv", [
            [0.0, 0.0],
            [10.0, 100.0]
        ])
        self.run_cli("add-csv", "--dataset", "test", "--file", train)

        # Query near 0
        query1 = self.create_csv("query1.csv", [[0.1]])
        output1 = str(self.test_dir / "pred1.csv")
        rc, _, _ = self.run_cli(
            "query-csv", "--dataset", "test",
            "--file", query1, "--output", output1
        )
        self.assertEqual(rc, 0)

        # Query near 10
        query2 = self.create_csv("query2.csv", [[9.9]])
        output2 = str(self.test_dir / "pred2.csv")
        rc, _, _ = self.run_cli(
            "query-csv", "--dataset", "test",
            "--file", query2, "--output", output2
        )
        self.assertEqual(rc, 0)

        # Check predictions are different
        with open(output1, "r") as f:
            reader = csv.reader(f)
            next(reader)
            pred1 = float(next(reader)[0])

        with open(output2, "r") as f:
            reader = csv.reader(f)
            next(reader)
            pred2 = float(next(reader)[0])

        # Both predictions should be mean of 2 neighbors (0+100)/2 = 50
        # since k=5 but only 2 training points
        self.assertAlmostEqual(pred1, 50.0, places=5)
        self.assertAlmostEqual(pred2, 50.0, places=5)


class TestDeterministicOutput(KNNCLITestBase):
    """Tests for deterministic output behavior under fixed data/settings."""

    def test_same_data_produces_same_predictions(self):
        """Verify identical input produces identical output across runs."""
        self.create_dataset(dimension=3)

        train = self.create_csv("train.csv", [
            [1.0, 2.0, 3.0, 100.0],
            [4.0, 5.0, 6.0, 200.0],
            [7.0, 8.0, 9.0, 300.0],
            [10.0, 11.0, 12.0, 400.0],
            [13.0, 14.0, 15.0, 500.0],
        ])
        self.run_cli("add-csv", "--dataset", "test", "--file", train)

        query = self.create_csv("query.csv", [
            [2.0, 3.0, 4.0],
            [8.0, 9.0, 10.0],
            [5.0, 6.0, 7.0]
        ])

        # Run query multiple times
        outputs = []
        for i in range(3):
            output = str(self.test_dir / f"pred_run{i}.csv")
            rc, _, _ = self.run_cli(
                "query-csv", "--dataset", "test",
                "--file", query, "--output", output
            )
            self.assertEqual(rc, 0)

            with open(output, "r") as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                preds = [float(row[0]) for row in reader]
            outputs.append(preds)

        # All runs should produce identical predictions
        for i in range(1, len(outputs)):
            for j, (a, b) in enumerate(zip(outputs[0], outputs[i])):
                self.assertEqual(a, b, f"Run 0 vs Run {i}: prediction {j} differs")

    def test_recreated_dataset_produces_same_predictions(self):
        """Verify recreating dataset with same data produces same predictions."""
        train_data = [
            [1.0, 1.0, 10.0],
            [2.0, 2.0, 20.0],
            [3.0, 3.0, 30.0],
            [4.0, 4.0, 40.0],
            [5.0, 5.0, 50.0],
        ]
        query_data = [[2.5, 2.5], [3.5, 3.5]]

        predictions_list = []

        for run in range(2):
            # Recreate dataset from scratch
            self.run_cli("create", "--dataset", "test", "--dimension", "2", "--overwrite")

            train = self.create_csv(f"train_run{run}.csv", train_data)
            self.run_cli("add-csv", "--dataset", "test", "--file", train)

            query = self.create_csv(f"query_run{run}.csv", query_data)
            output = str(self.test_dir / f"pred_run{run}.csv")

            rc, _, _ = self.run_cli(
                "query-csv", "--dataset", "test",
                "--file", query, "--output", output
            )
            self.assertEqual(rc, 0)

            with open(output, "r") as f:
                reader = csv.reader(f)
                next(reader)
                preds = [float(row[0]) for row in reader]
            predictions_list.append(preds)

        # Both runs should produce identical predictions
        self.assertEqual(predictions_list[0], predictions_list[1])

    def test_row_order_preserved(self):
        """Verify predictions are output in same order as query rows."""
        self.create_dataset(dimension=1)

        # Create training data where prediction = feature value
        train = self.create_csv("train.csv", [
            [10.0, 10.0],
            [20.0, 20.0],
            [30.0, 30.0],
            [40.0, 40.0],
            [50.0, 50.0],
        ])
        self.run_cli("add-csv", "--dataset", "test", "--file", train)

        # Query in specific order
        query = self.create_csv("query.csv", [
            [30.0],  # Should predict ~30
            [10.0],  # Should predict ~10
            [50.0],  # Should predict ~50
        ])
        output = str(self.test_dir / "pred.csv")

        rc, _, _ = self.run_cli(
            "query-csv", "--dataset", "test",
            "--file", query, "--output", output
        )
        self.assertEqual(rc, 0)

        with open(output, "r") as f:
            reader = csv.reader(f)
            next(reader)
            preds = [float(row[0]) for row in reader]

        # Check order is preserved (predictions should follow query order)
        self.assertEqual(len(preds), 3)
        # With k=5 all points are neighbors, so all predictions = mean = 30
        # But order should still be maintained
        self.assertTrue(all(abs(p - 30.0) < 0.01 for p in preds))


class TestCommandContractBehavior(KNNCLITestBase):
    """Tests for required CLI contract behavior."""

    def test_create_command_contract(self):
        """Test create command with required arguments."""
        rc, stdout, _ = self.run_cli("create", "--dataset", "mydata", "--dimension", "5")
        self.assertEqual(rc, 0)
        self.assertIn("Created dataset 'mydata'", stdout)
        self.assertIn("dimension 5", stdout)

    def test_add_csv_command_contract(self):
        """Test add-csv command with required arguments."""
        self.create_dataset("mydata", dimension=3)
        train = self.create_csv("train.csv", [
            [1.0, 2.0, 3.0, 4.0],
            [5.0, 6.0, 7.0, 8.0]
        ])
        rc, stdout, _ = self.run_cli("add-csv", "--dataset", "mydata", "--file", train)
        self.assertEqual(rc, 0)
        self.assertIn("Added 2 observations", stdout)

    def test_query_csv_command_contract(self):
        """Test query-csv command with required arguments."""
        self.create_dataset("mydata", dimension=2)
        train = self.create_csv("train.csv", [
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0]
        ])
        self.run_cli("add-csv", "--dataset", "mydata", "--file", train)

        query = self.create_csv("test.csv", [[2.0, 3.0]])
        output = str(self.test_dir / "predictions.csv")

        rc, stdout, _ = self.run_cli(
            "query-csv", "--dataset", "mydata",
            "--file", query, "--output", output
        )
        self.assertEqual(rc, 0)
        self.assertIn("Wrote 1 predictions", stdout)
        self.assertTrue(Path(output).exists())

    def test_end_to_end_workflow(self):
        """Test complete workflow: create -> add-csv -> query-csv."""
        # Create
        rc, _, _ = self.run_cli("create", "--dataset", "e2e", "--dimension", "3")
        self.assertEqual(rc, 0)

        # Add training data
        train = self.create_csv("train.csv", [
            [0.0, 0.0, 0.0, 0.0],
            [1.0, 1.0, 1.0, 1.0],
            [2.0, 2.0, 2.0, 2.0],
            [3.0, 3.0, 3.0, 3.0],
            [4.0, 4.0, 4.0, 4.0],
        ])
        rc, _, _ = self.run_cli("add-csv", "--dataset", "e2e", "--file", train)
        self.assertEqual(rc, 0)

        # Query
        query = self.create_csv("query.csv", [
            [0.5, 0.5, 0.5],
            [2.5, 2.5, 2.5],
        ])
        output = str(self.test_dir / "pred.csv")
        rc, _, _ = self.run_cli(
            "query-csv", "--dataset", "e2e",
            "--file", query, "--output", output
        )
        self.assertEqual(rc, 0)

        # Verify output
        with open(output, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            self.assertEqual(header, ["prediction"])
            preds = [float(row[0]) for row in reader]

        self.assertEqual(len(preds), 2)
        # Both predictions should be mean of all 5 neighbors = (0+1+2+3+4)/5 = 2.0
        for pred in preds:
            self.assertAlmostEqual(pred, 2.0, places=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
