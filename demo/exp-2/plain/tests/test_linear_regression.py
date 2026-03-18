"""Tests for linear-regression forecast method."""

import pytest
from click.testing import CliRunner
from sequencelab.cli import (
    FORECAST_METHODS,
    fit_linear_regression,
    forecast_linear_regression,
    main,
    rolling_forecast_linear_regression,
)


class TestLinearRegressionInMethodsList:
    """Test that linear-regression is available as a forecast method."""

    def test_linear_regression_in_methods_list(self):
        """linear-regression is in FORECAST_METHODS."""
        assert "linear-regression" in FORECAST_METHODS


class TestFitLinearRegression:
    """Test the fit_linear_regression helper function."""

    def test_perfect_linear_fit(self):
        """Fits exact line y = 2x + 1."""
        x = [0.0, 1.0, 2.0, 3.0]
        y = [1.0, 3.0, 5.0, 7.0]
        slope, intercept = fit_linear_regression(x, y)
        assert abs(slope - 2.0) < 1e-10
        assert abs(intercept - 1.0) < 1e-10

    def test_horizontal_line(self):
        """Fits horizontal line y = 5."""
        x = [0.0, 1.0, 2.0, 3.0]
        y = [5.0, 5.0, 5.0, 5.0]
        slope, intercept = fit_linear_regression(x, y)
        assert abs(slope) < 1e-10
        assert abs(intercept - 5.0) < 1e-10

    def test_negative_slope(self):
        """Fits line with negative slope y = -2x + 10."""
        x = [0.0, 1.0, 2.0, 3.0]
        y = [10.0, 8.0, 6.0, 4.0]
        slope, intercept = fit_linear_regression(x, y)
        assert abs(slope - (-2.0)) < 1e-10
        assert abs(intercept - 10.0) < 1e-10

    def test_two_points(self):
        """Works with minimum 2 points."""
        x = [0.0, 1.0]
        y = [0.0, 1.0]
        slope, intercept = fit_linear_regression(x, y)
        assert abs(slope - 1.0) < 1e-10
        assert abs(intercept) < 1e-10

    def test_mismatched_lengths_raises(self):
        """Raises ValueError when x and y have different lengths."""
        with pytest.raises(ValueError, match="same length"):
            fit_linear_regression([1.0, 2.0], [1.0])

    def test_single_point_raises(self):
        """Raises ValueError with only 1 point."""
        with pytest.raises(ValueError, match="At least 2 points"):
            fit_linear_regression([1.0], [1.0])

    def test_identical_x_values(self):
        """Handles degenerate case where all x values are identical."""
        x = [1.0, 1.0, 1.0]
        y = [1.0, 2.0, 3.0]
        slope, intercept = fit_linear_regression(x, y)
        assert slope == 0.0
        assert abs(intercept - 2.0) < 1e-10


class TestForecastLinearRegression:
    """Test the forecast_linear_regression function."""

    def test_extrapolate_linear_trend(self):
        """Extrapolates linear trend correctly."""
        values = [1.0, 3.0, 5.0, 7.0]
        result = forecast_linear_regression(values, horizon=2)
        assert len(result) == 2
        assert abs(result[0] - 9.0) < 1e-10
        assert abs(result[1] - 11.0) < 1e-10

    def test_extrapolate_constant_series(self):
        """Constant series extrapolates to same value."""
        values = [5.0, 5.0, 5.0, 5.0]
        result = forecast_linear_regression(values, horizon=3)
        assert len(result) == 3
        for pred in result:
            assert abs(pred - 5.0) < 1e-10

    def test_two_values_minimum(self):
        """Works with minimum 2 values."""
        values = [0.0, 2.0]
        result = forecast_linear_regression(values, horizon=1)
        assert len(result) == 1
        assert abs(result[0] - 4.0) < 1e-10

    def test_single_value_raises(self):
        """Raises ValueError for single-value series."""
        with pytest.raises(ValueError, match="at least 2 values"):
            forecast_linear_regression([5.0], horizon=1)

    def test_empty_series_raises(self):
        """Raises ValueError for empty series."""
        with pytest.raises(ValueError, match="at least 2 values"):
            forecast_linear_regression([], horizon=1)


class TestRollingForecastLinearRegression:
    """Test the rolling_forecast_linear_regression function."""

    def test_rolling_predictions(self):
        """Produces correct one-step-ahead predictions."""
        values = [1.0, 3.0, 5.0, 7.0, 9.0]
        result = rolling_forecast_linear_regression(values)
        assert len(result) == 3
        assert abs(result[0] - 5.0) < 1e-10
        assert abs(result[1] - 7.0) < 1e-10
        assert abs(result[2] - 9.0) < 1e-10

    def test_minimum_three_values(self):
        """Works with minimum 3 values."""
        values = [0.0, 1.0, 2.0]
        result = rolling_forecast_linear_regression(values)
        assert len(result) == 1
        assert abs(result[0] - 2.0) < 1e-10

    def test_two_values_raises(self):
        """Raises ValueError for 2-value series."""
        with pytest.raises(ValueError, match="at least 3 values"):
            rolling_forecast_linear_regression([1.0, 2.0])

    def test_single_value_raises(self):
        """Raises ValueError for single-value series."""
        with pytest.raises(ValueError, match="at least 3 values"):
            rolling_forecast_linear_regression([5.0])


class TestForecastRunLinearRegressionCLI:
    """Test the forecast run command with linear-regression."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_run_linear_regression(self, runner):
        """--method linear-regression works and shows method in output."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "test", "1,2,3,4,5"])
            result = runner.invoke(
                main,
                [
                    "forecast",
                    "run",
                    "--series",
                    "test",
                    "--method",
                    "linear-regression",
                    "--horizon",
                    "2",
                ],
            )
            assert result.exit_code == 0
            assert "linear-regression" in result.output
            assert "Predicted values" in result.output

    def test_run_linear_regression_values(self, runner):
        """Linear regression produces expected forecast values."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "linear", "0,2,4,6"])
            result = runner.invoke(
                main,
                [
                    "forecast",
                    "run",
                    "--series",
                    "linear",
                    "--method",
                    "linear-regression",
                    "--horizon",
                    "2",
                ],
            )
            assert result.exit_code == 0
            assert "8.000000" in result.output
            assert "10.000000" in result.output

    def test_run_linear_regression_short_series(self, runner):
        """Linear regression fails gracefully for single-value series."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "short", "5"])
            result = runner.invoke(
                main,
                [
                    "forecast",
                    "run",
                    "--series",
                    "short",
                    "--method",
                    "linear-regression",
                    "--horizon",
                    "1",
                ],
            )
            assert result.exit_code != 0
            assert "at least 2 values" in result.output


class TestForecastEvaluateLinearRegressionCLI:
    """Test the forecast evaluate command with linear-regression."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_evaluate_linear_regression(self, runner):
        """--method linear-regression works for evaluation."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "test", "1,2,3,4,5"])
            result = runner.invoke(
                main, ["forecast", "evaluate", "--series", "test", "--method", "linear-regression"]
            )
            assert result.exit_code == 0
            assert "linear-regression" in result.output
            assert "MAE" in result.output
            assert "RMSE" in result.output

    def test_evaluate_linear_regression_perfect_fit(self, runner):
        """Perfect linear series has zero error."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "perfect", "0,2,4,6,8"])
            result = runner.invoke(
                main,
                ["forecast", "evaluate", "--series", "perfect", "--method", "linear-regression"],
            )
            assert result.exit_code == 0
            assert "MAE:  0.000000" in result.output
            assert "RMSE: 0.000000" in result.output

    def test_evaluate_linear_regression_short_series(self, runner):
        """Linear regression evaluation fails for 2-value series."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "short", "1,2"])
            result = runner.invoke(
                main, ["forecast", "evaluate", "--series", "short", "--method", "linear-regression"]
            )
            assert result.exit_code != 0
            assert "at least 3 values" in result.output
