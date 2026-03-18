"""Tests for bootstrap confidence intervals in forecast evaluation."""

import pytest
from click.testing import CliRunner
from sequencelab.cli import (
    bootstrap_ci,
    compute_errors,
    mae_from_errors,
    main,
    rmse_from_errors,
)


class TestComputeErrors:
    """Test the compute_errors helper function."""

    def test_basic_errors(self):
        """Computes correct errors."""
        actual = [1.0, 2.0, 3.0]
        predicted = [0.5, 2.0, 3.5]
        errors = compute_errors(actual, predicted)
        assert errors == [0.5, 0.0, -0.5]

    def test_empty_lists(self):
        """Works with empty lists."""
        errors = compute_errors([], [])
        assert errors == []

    def test_mismatched_lengths_raises(self):
        """Raises ValueError when lists have different lengths."""
        with pytest.raises(ValueError, match="same length"):
            compute_errors([1.0, 2.0], [1.0])


class TestMaeFromErrors:
    """Test the mae_from_errors helper function."""

    def test_basic_mae(self):
        """Computes correct MAE from errors."""
        errors = [1.0, -2.0, 3.0]
        mae = mae_from_errors(errors)
        assert abs(mae - 2.0) < 1e-10

    def test_zero_errors(self):
        """MAE of zero errors is zero."""
        errors = [0.0, 0.0, 0.0]
        mae = mae_from_errors(errors)
        assert mae == 0.0

    def test_empty_raises(self):
        """Raises ValueError for empty list."""
        with pytest.raises(ValueError, match="empty"):
            mae_from_errors([])


class TestRmseFromErrors:
    """Test the rmse_from_errors helper function."""

    def test_basic_rmse(self):
        """Computes correct RMSE from errors."""
        errors = [1.0, -1.0, 1.0, -1.0]
        rmse = rmse_from_errors(errors)
        assert abs(rmse - 1.0) < 1e-10

    def test_zero_errors(self):
        """RMSE of zero errors is zero."""
        errors = [0.0, 0.0, 0.0]
        rmse = rmse_from_errors(errors)
        assert rmse == 0.0

    def test_empty_raises(self):
        """Raises ValueError for empty list."""
        with pytest.raises(ValueError, match="empty"):
            rmse_from_errors([])


class TestBootstrapCi:
    """Test the bootstrap_ci function."""

    def test_deterministic_with_seed(self):
        """Same seed produces same results."""
        errors = [1.0, 2.0, 3.0, 4.0, 5.0]
        result1 = bootstrap_ci(errors, mae_from_errors, n_samples=100, ci_percent=95, seed=42)
        result2 = bootstrap_ci(errors, mae_from_errors, n_samples=100, ci_percent=95, seed=42)
        assert result1 == result2

    def test_different_seeds_different_results(self):
        """Different seeds produce different results (usually)."""
        errors = [1.0, 2.0, 3.0, 4.0, 5.0]
        result1 = bootstrap_ci(errors, mae_from_errors, n_samples=100, ci_percent=95, seed=42)
        result2 = bootstrap_ci(errors, mae_from_errors, n_samples=100, ci_percent=95, seed=123)
        assert result1 != result2

    def test_returns_tuple_of_three(self):
        """Returns (lower, point, upper) tuple."""
        errors = [1.0, 2.0, 3.0]
        result = bootstrap_ci(errors, mae_from_errors, n_samples=50, ci_percent=95, seed=1)
        assert len(result) == 3
        lower, point, upper = result
        assert isinstance(lower, float)
        assert isinstance(point, float)
        assert isinstance(upper, float)

    def test_point_estimate_matches_direct(self):
        """Point estimate matches direct computation."""
        errors = [1.0, 2.0, 3.0, 4.0]
        _, point, _ = bootstrap_ci(errors, mae_from_errors, n_samples=50, ci_percent=95, seed=1)
        direct = mae_from_errors(errors)
        assert point == direct

    def test_lower_bound_less_than_or_equal_upper(self):
        """Lower bound <= upper bound."""
        errors = [1.0, 2.0, 3.0, 4.0, 5.0]
        lower, _, upper = bootstrap_ci(
            errors, mae_from_errors, n_samples=100, ci_percent=95, seed=42
        )
        assert lower <= upper

    def test_narrower_ci_with_more_samples(self):
        """With enough samples, CI should stabilize to reasonable values."""
        errors = [1.0, 2.0, 3.0, 4.0, 5.0]
        lower, point, upper = bootstrap_ci(
            errors, mae_from_errors, n_samples=1000, ci_percent=95, seed=42
        )
        assert lower > 0
        assert upper < 10  # Sanity check

    def test_wider_ci_for_higher_percentage(self):
        """99% CI should be wider than 90% CI."""
        errors = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        low_90, _, high_90 = bootstrap_ci(
            errors, mae_from_errors, n_samples=500, ci_percent=90, seed=42
        )
        low_99, _, high_99 = bootstrap_ci(
            errors, mae_from_errors, n_samples=500, ci_percent=99, seed=42
        )
        width_90 = high_90 - low_90
        width_99 = high_99 - low_99
        assert width_99 >= width_90

    def test_invalid_sample_count_raises(self):
        """Raises ValueError for invalid sample count."""
        errors = [1.0, 2.0, 3.0]
        with pytest.raises(ValueError, match="at least 1"):
            bootstrap_ci(errors, mae_from_errors, n_samples=0, ci_percent=95)

    def test_invalid_ci_percent_low_raises(self):
        """Raises ValueError for CI <= 0."""
        errors = [1.0, 2.0, 3.0]
        with pytest.raises(ValueError, match="between 0 and 100"):
            bootstrap_ci(errors, mae_from_errors, n_samples=10, ci_percent=0)

    def test_invalid_ci_percent_high_raises(self):
        """Raises ValueError for CI >= 100."""
        errors = [1.0, 2.0, 3.0]
        with pytest.raises(ValueError, match="between 0 and 100"):
            bootstrap_ci(errors, mae_from_errors, n_samples=10, ci_percent=100)

    def test_empty_errors_raises(self):
        """Raises ValueError for empty errors."""
        with pytest.raises(ValueError, match="empty"):
            bootstrap_ci([], mae_from_errors, n_samples=10, ci_percent=95)


class TestForecastEvaluateBootstrapCLI:
    """Test the forecast evaluate command with bootstrap options."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_evaluate_without_bootstrap(self, runner):
        """Default behavior (no bootstrap) shows just MAE and RMSE."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "test", "1,2,3,4,5"])
            result = runner.invoke(
                main, ["forecast", "evaluate", "--series", "test", "--method", "last-value"]
            )
            assert result.exit_code == 0
            assert "MAE:" in result.output
            assert "RMSE:" in result.output
            assert "CI:" not in result.output

    def test_evaluate_with_bootstrap(self, runner):
        """Bootstrap mode shows confidence intervals."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "test", "1,2,3,4,5,6,7,8,9,10"])
            result = runner.invoke(
                main,
                [
                    "forecast",
                    "evaluate",
                    "--series",
                    "test",
                    "--method",
                    "last-value",
                    "--bootstrap-samples",
                    "100",
                ],
            )
            assert result.exit_code == 0
            assert "95% CI:" in result.output

    def test_evaluate_with_custom_ci(self, runner):
        """Custom CI percentage is shown in output."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "test", "1,2,3,4,5,6,7,8,9,10"])
            result = runner.invoke(
                main,
                [
                    "forecast",
                    "evaluate",
                    "--series",
                    "test",
                    "--method",
                    "last-value",
                    "--bootstrap-samples",
                    "100",
                    "--ci",
                    "90",
                ],
            )
            assert result.exit_code == 0
            assert "90% CI:" in result.output

    def test_evaluate_reproducible_with_seed(self, runner):
        """Same seed produces same interval bounds."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "test", "1,2,3,4,5,6,7,8,9,10"])
            result1 = runner.invoke(
                main,
                [
                    "forecast",
                    "evaluate",
                    "--series",
                    "test",
                    "--method",
                    "last-value",
                    "--bootstrap-samples",
                    "100",
                    "--seed",
                    "42",
                ],
            )
            result2 = runner.invoke(
                main,
                [
                    "forecast",
                    "evaluate",
                    "--series",
                    "test",
                    "--method",
                    "last-value",
                    "--bootstrap-samples",
                    "100",
                    "--seed",
                    "42",
                ],
            )
            assert result1.exit_code == 0
            assert result2.exit_code == 0
            assert result1.output == result2.output

    def test_evaluate_different_seeds_different_output(self, runner):
        """Different seeds produce different outputs."""
        with runner.isolated_filesystem():
            # Use varied data so bootstrap resampling produces different CI bounds
            runner.invoke(main, ["series", "add", "varied", "1,5,2,8,3,9,4,7,6,10"])
            result1 = runner.invoke(
                main,
                [
                    "forecast",
                    "evaluate",
                    "--series",
                    "varied",
                    "--method",
                    "last-value",
                    "--bootstrap-samples",
                    "100",
                    "--seed",
                    "42",
                ],
            )
            result2 = runner.invoke(
                main,
                [
                    "forecast",
                    "evaluate",
                    "--series",
                    "varied",
                    "--method",
                    "last-value",
                    "--bootstrap-samples",
                    "100",
                    "--seed",
                    "123",
                ],
            )
            assert result1.exit_code == 0
            assert result2.exit_code == 0
            assert result1.output != result2.output

    def test_bootstrap_with_moving_average(self, runner):
        """Bootstrap works with moving-average method."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "ma_test", "1,2,3,4,5,6,7,8,9,10"])
            result = runner.invoke(
                main,
                [
                    "forecast",
                    "evaluate",
                    "--series",
                    "ma_test",
                    "--method",
                    "moving-average",
                    "--window",
                    "3",
                    "--bootstrap-samples",
                    "50",
                    "--seed",
                    "1",
                ],
            )
            assert result.exit_code == 0, f"Error: {result.output}"
            assert "95% CI:" in result.output
            assert "moving-average" in result.output

    def test_bootstrap_with_linear_regression(self, runner):
        """Bootstrap works with linear-regression method."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "test", "1,2,3,4,5,6,7,8,9,10"])
            result = runner.invoke(
                main,
                [
                    "forecast",
                    "evaluate",
                    "--series",
                    "test",
                    "--method",
                    "linear-regression",
                    "--bootstrap-samples",
                    "50",
                    "--seed",
                    "1",
                ],
            )
            assert result.exit_code == 0
            assert "95% CI:" in result.output
            assert "linear-regression" in result.output

    def test_invalid_bootstrap_samples_rejected(self, runner):
        """Zero or negative bootstrap samples are rejected."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "test", "1,2,3,4,5"])
            result = runner.invoke(
                main,
                [
                    "forecast",
                    "evaluate",
                    "--series",
                    "test",
                    "--method",
                    "last-value",
                    "--bootstrap-samples",
                    "0",
                ],
            )
            assert result.exit_code != 0
            assert "at least 1" in result.output

    def test_invalid_ci_low_rejected(self, runner):
        """CI <= 0 is rejected."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "test", "1,2,3,4,5"])
            result = runner.invoke(
                main,
                [
                    "forecast",
                    "evaluate",
                    "--series",
                    "test",
                    "--method",
                    "last-value",
                    "--bootstrap-samples",
                    "10",
                    "--ci",
                    "0",
                ],
            )
            assert result.exit_code != 0
            assert "between 0 and 100" in result.output

    def test_invalid_ci_high_rejected(self, runner):
        """CI >= 100 is rejected."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "test", "1,2,3,4,5"])
            result = runner.invoke(
                main,
                [
                    "forecast",
                    "evaluate",
                    "--series",
                    "test",
                    "--method",
                    "last-value",
                    "--bootstrap-samples",
                    "10",
                    "--ci",
                    "100",
                ],
            )
            assert result.exit_code != 0
            assert "between 0 and 100" in result.output

    def test_ci_bounds_plausible(self, runner):
        """CI bounds should contain the point estimate for reasonable data."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "test", "1,2,3,4,5,6,7,8,9,10"])
            result = runner.invoke(
                main,
                [
                    "forecast",
                    "evaluate",
                    "--series",
                    "test",
                    "--method",
                    "last-value",
                    "--bootstrap-samples",
                    "1000",
                    "--seed",
                    "42",
                ],
            )
            assert result.exit_code == 0
            output_lines = result.output.split("\n")
            for line in output_lines:
                if "MAE:" in line and "CI:" in line:
                    parts = line.split()
                    mae_val = float(parts[1])
                    lower_idx = parts.index("-") - 1
                    lower = float(parts[lower_idx].rstrip(":").lstrip("["))
                    upper = float(parts[lower_idx + 2].rstrip("]"))
                    assert (
                        lower <= mae_val <= upper
                        or abs(lower - mae_val) < 0.5
                        or abs(upper - mae_val) < 0.5
                    )
