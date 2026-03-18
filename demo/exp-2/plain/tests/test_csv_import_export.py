"""Tests for CSV import/export functionality."""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from sequencelab.cli import is_header_row, main, parse_csv_value
from sequencelab.storage import SeriesStore


class TestParseCsvValue:
    """Test the parse_csv_value helper function."""

    def test_valid_integer(self):
        """Parses integer values."""
        assert parse_csv_value("42", 1) == 42.0

    def test_valid_float(self):
        """Parses float values."""
        assert parse_csv_value("3.14159", 1) == 3.14159

    def test_negative_number(self):
        """Parses negative numbers."""
        assert parse_csv_value("-5.5", 1) == -5.5

    def test_scientific_notation(self):
        """Parses scientific notation."""
        assert parse_csv_value("1.5e-3", 1) == 0.0015

    def test_whitespace_stripped(self):
        """Strips surrounding whitespace."""
        assert parse_csv_value("  42.0  ", 1) == 42.0

    def test_empty_value_raises(self):
        """Raises ValueError for empty value."""
        with pytest.raises(ValueError, match="Line 5: empty value"):
            parse_csv_value("", 5)

    def test_whitespace_only_raises(self):
        """Raises ValueError for whitespace-only value."""
        with pytest.raises(ValueError, match="Line 3: empty value"):
            parse_csv_value("   ", 3)

    def test_invalid_number_raises(self):
        """Raises ValueError for non-numeric value."""
        with pytest.raises(ValueError, match="Line 2: 'abc' is not a valid number"):
            parse_csv_value("abc", 2)


class TestIsHeaderRow:
    """Test the is_header_row helper function."""

    def test_text_is_header(self):
        """Text values are detected as headers."""
        assert is_header_row("value") is True
        assert is_header_row("Value") is True
        assert is_header_row("data") is True

    def test_number_is_not_header(self):
        """Numeric values are not headers."""
        assert is_header_row("42") is False
        assert is_header_row("3.14") is False
        assert is_header_row("-5") is False

    def test_empty_is_not_header(self):
        """Empty string is not a header."""
        assert is_header_row("") is False

    def test_scientific_notation_not_header(self):
        """Scientific notation is not a header."""
        assert is_header_row("1e5") is False


class TestImportCsvCLI:
    """Test the series import-csv command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def isolated_store(self, runner):
        """Provide an isolated storage directory for tests."""
        with runner.isolated_filesystem() as tmpdir:
            data_dir = Path(tmpdir) / ".sequencelab"
            with patch("sequencelab.cli.get_store", lambda: SeriesStore(data_dir=data_dir)):
                yield tmpdir

    def test_import_simple_csv(self, runner, isolated_store):
        """Imports a simple CSV with one value per line."""
        with open("data.csv", "w") as f:
            f.write("1.0\n2.0\n3.0\n")

        result = runner.invoke(
            main, ["series", "import-csv", "--name", "test", "--file", "data.csv"]
        )
        assert result.exit_code == 0
        assert "Imported series 'test'" in result.output
        assert "Values: 3" in result.output

        show_result = runner.invoke(main, ["series", "show", "test"])
        assert "1.0" in show_result.output
        assert "2.0" in show_result.output
        assert "3.0" in show_result.output

    def test_import_csv_with_header(self, runner, isolated_store):
        """Skips header row if first line is non-numeric."""
        with open("data.csv", "w") as f:
            f.write("value\n10.5\n20.5\n30.5\n")

        result = runner.invoke(
            main, ["series", "import-csv", "--name", "test", "--file", "data.csv"]
        )
        assert result.exit_code == 0
        assert "Values: 3" in result.output

    def test_import_csv_no_header(self, runner, isolated_store):
        """Includes first row if it's numeric."""
        with open("data.csv", "w") as f:
            f.write("100\n200\n300\n")

        result = runner.invoke(
            main, ["series", "import-csv", "--name", "test", "--file", "data.csv"]
        )
        assert result.exit_code == 0
        assert "Values: 3" in result.output

        show_result = runner.invoke(main, ["series", "show", "test"])
        assert "100" in show_result.output

    def test_import_csv_with_blank_lines(self, runner, isolated_store):
        """Skips blank lines in CSV."""
        with open("data.csv", "w") as f:
            f.write("1.0\n\n2.0\n\n3.0\n")

        result = runner.invoke(
            main, ["series", "import-csv", "--name", "test", "--file", "data.csv"]
        )
        assert result.exit_code == 0
        assert "Values: 3" in result.output

    def test_import_csv_duplicate_name_fails(self, runner, isolated_store):
        """Fails if series name already exists."""
        runner.invoke(main, ["series", "add", "existing", "1,2,3"])

        with open("data.csv", "w") as f:
            f.write("4\n5\n6\n")

        result = runner.invoke(
            main, ["series", "import-csv", "--name", "existing", "--file", "data.csv"]
        )
        assert result.exit_code != 0
        assert "already exists" in result.output

    def test_import_csv_file_not_found(self, runner, isolated_store):
        """Fails if file does not exist."""
        result = runner.invoke(
            main, ["series", "import-csv", "--name", "test", "--file", "missing.csv"]
        )
        assert result.exit_code != 0

    def test_import_csv_malformed_row_reports_line_number(self, runner, isolated_store):
        """Reports line number for malformed rows."""
        with open("data.csv", "w") as f:
            f.write("1.0\n2.0\nbad\n4.0\n")

        result = runner.invoke(
            main, ["series", "import-csv", "--name", "test", "--file", "data.csv"]
        )
        assert result.exit_code != 0
        assert "Line 3:" in result.output
        assert "'bad' is not a valid number" in result.output

    def test_import_csv_multiple_errors_reported(self, runner, isolated_store):
        """Reports all malformed rows, not just the first."""
        with open("data.csv", "w") as f:
            f.write("1.0\nerror1\n3.0\nerror2\n")

        result = runner.invoke(
            main, ["series", "import-csv", "--name", "test", "--file", "data.csv"]
        )
        assert result.exit_code != 0
        assert "Line 2:" in result.output
        assert "Line 4:" in result.output

    def test_import_csv_no_partial_series_on_failure(self, runner, isolated_store):
        """Does not create a series if any row is malformed."""
        with open("data.csv", "w") as f:
            f.write("1.0\n2.0\nbad\n")

        result = runner.invoke(
            main, ["series", "import-csv", "--name", "test", "--file", "data.csv"]
        )
        assert result.exit_code != 0

        list_result = runner.invoke(main, ["series", "list"])
        assert "test" not in list_result.output

    def test_import_csv_empty_file_fails(self, runner, isolated_store):
        """Fails for empty CSV file."""
        with open("data.csv", "w") as f:
            f.write("")

        result = runner.invoke(
            main, ["series", "import-csv", "--name", "test", "--file", "data.csv"]
        )
        assert result.exit_code != 0
        assert "no valid numeric values" in result.output

    def test_import_csv_header_only_fails(self, runner, isolated_store):
        """Fails for CSV with only a header."""
        with open("data.csv", "w") as f:
            f.write("value\n")

        result = runner.invoke(
            main, ["series", "import-csv", "--name", "test", "--file", "data.csv"]
        )
        assert result.exit_code != 0
        assert "no valid numeric values" in result.output


class TestExportCsvCLI:
    """Test the series export-csv command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def isolated_store(self, runner):
        """Provide an isolated storage directory for tests."""
        with runner.isolated_filesystem() as tmpdir:
            data_dir = Path(tmpdir) / ".sequencelab"
            with patch("sequencelab.cli.get_store", lambda: SeriesStore(data_dir=data_dir)):
                yield tmpdir

    def test_export_simple_series(self, runner, isolated_store):
        """Exports a series to CSV."""
        runner.invoke(main, ["series", "add", "test", "1.0,2.0,3.0"])

        result = runner.invoke(
            main, ["series", "export-csv", "--series", "test", "--file", "output.csv"]
        )
        assert result.exit_code == 0
        assert "Exported series 'test'" in result.output
        assert "Values: 3" in result.output

        with open("output.csv", "r") as f:
            content = f.read()
        assert "value" in content
        assert "1.0" in content
        assert "2.0" in content
        assert "3.0" in content

    def test_export_series_not_found(self, runner, isolated_store):
        """Fails if series does not exist."""
        result = runner.invoke(
            main, ["series", "export-csv", "--series", "missing", "--file", "output.csv"]
        )
        assert result.exit_code != 0
        assert "not found" in result.output

    def test_export_by_id(self, runner, isolated_store):
        """Can export by series ID."""
        add_result = runner.invoke(main, ["series", "add", "test", "10,20,30"])
        series_id = add_result.output.split("id ")[-1].strip()

        result = runner.invoke(
            main, ["series", "export-csv", "--series", series_id, "--file", "output.csv"]
        )
        assert result.exit_code == 0

    def test_export_has_header(self, runner, isolated_store):
        """Exported CSV has a header row."""
        runner.invoke(main, ["series", "add", "test", "1,2,3"])
        runner.invoke(main, ["series", "export-csv", "--series", "test", "--file", "output.csv"])

        with open("output.csv", "r") as f:
            lines = f.readlines()
        assert lines[0].strip() == "value"

    def test_export_deterministic(self, runner, isolated_store):
        """Export is deterministic (same output for same input)."""
        runner.invoke(main, ["series", "add", "test", "1.5,2.5,3.5"])

        runner.invoke(main, ["series", "export-csv", "--series", "test", "--file", "output1.csv"])
        runner.invoke(main, ["series", "export-csv", "--series", "test", "--file", "output2.csv"])

        with open("output1.csv", "r") as f:
            content1 = f.read()
        with open("output2.csv", "r") as f:
            content2 = f.read()

        assert content1 == content2


class TestCsvRoundTrip:
    """Test that exported CSV can be re-imported with equivalent values."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def isolated_store(self, runner):
        """Provide an isolated storage directory for tests."""
        with runner.isolated_filesystem() as tmpdir:
            data_dir = Path(tmpdir) / ".sequencelab"
            with patch("sequencelab.cli.get_store", lambda: SeriesStore(data_dir=data_dir)):
                yield tmpdir

    def test_roundtrip_integers(self, runner, isolated_store):
        """Integer values round-trip correctly."""
        runner.invoke(main, ["series", "add", "original", "1,2,3,4,5"])
        runner.invoke(main, ["series", "export-csv", "--series", "original", "--file", "data.csv"])
        runner.invoke(main, ["series", "import-csv", "--name", "imported", "--file", "data.csv"])

        orig_result = runner.invoke(main, ["series", "show", "original"])
        imported_result = runner.invoke(main, ["series", "show", "imported"])

        for val in ["1", "2", "3", "4", "5"]:
            assert val in orig_result.output
            assert val in imported_result.output

    def test_roundtrip_floats(self, runner, isolated_store):
        """Float values round-trip with full precision."""
        runner.invoke(main, ["series", "add", "original", "1.123456789,2.987654321,3.141592653"])
        runner.invoke(main, ["series", "export-csv", "--series", "original", "--file", "data.csv"])
        runner.invoke(main, ["series", "import-csv", "--name", "imported", "--file", "data.csv"])

        orig_result = runner.invoke(main, ["series", "show", "original"])
        imported_result = runner.invoke(main, ["series", "show", "imported"])

        assert "1.123456789" in orig_result.output
        assert "1.123456789" in imported_result.output

    def test_roundtrip_negative_values(self, runner, isolated_store):
        """Negative values round-trip correctly."""
        runner.invoke(main, ["series", "add", "original", "--", "-10.5,-20.5,-30.5"])
        runner.invoke(main, ["series", "export-csv", "--series", "original", "--file", "data.csv"])
        runner.invoke(main, ["series", "import-csv", "--name", "imported", "--file", "data.csv"])

        imported_result = runner.invoke(main, ["series", "show", "imported"])
        assert "-10.5" in imported_result.output
        assert "-20.5" in imported_result.output

    def test_roundtrip_scientific_notation(self, runner, isolated_store):
        """Very small/large values round-trip correctly."""
        runner.invoke(main, ["series", "add", "original", "1e-10,1e10"])
        runner.invoke(main, ["series", "export-csv", "--series", "original", "--file", "data.csv"])
        runner.invoke(main, ["series", "import-csv", "--name", "imported", "--file", "data.csv"])

        orig_stats = runner.invoke(main, ["stats", "describe", "--series", "original"])
        imported_stats = runner.invoke(main, ["stats", "describe", "--series", "imported"])

        assert "count:     2" in orig_stats.output
        assert "count:     2" in imported_stats.output
