"""Tests for forecast method name aliasing (naive -> last-value)."""

import pytest
from click.testing import CliRunner
from sequencelab.cli import (
    FORECAST_METHOD_ALIASES,
    FORECAST_METHODS,
    forecast_last_value,
    main,
    resolve_forecast_method,
    rolling_forecast_last_value,
)


class TestMethodAliasResolution:
    """Test that method name aliasing works correctly."""

    def test_resolve_canonical_name(self):
        """Canonical name 'last-value' resolves to itself."""
        assert resolve_forecast_method("last-value") == "last-value"

    def test_resolve_alias_name(self):
        """Deprecated alias 'naive' resolves to 'last-value'."""
        assert resolve_forecast_method("naive") == "last-value"

    def test_resolve_other_methods_unchanged(self):
        """Other method names pass through unchanged."""
        assert resolve_forecast_method("moving-average") == "moving-average"

    def test_canonical_name_in_methods_list(self):
        """Canonical name 'last-value' is in FORECAST_METHODS."""
        assert "last-value" in FORECAST_METHODS

    def test_alias_in_aliases_dict(self):
        """Alias 'naive' maps to 'last-value' in FORECAST_METHOD_ALIASES."""
        assert FORECAST_METHOD_ALIASES.get("naive") == "last-value"


class TestForecastLastValueFunction:
    """Test the forecast_last_value function directly."""

    def test_basic_forecast(self):
        """Produces correct forecast by repeating last value."""
        values = [1.0, 2.0, 3.0]
        result = forecast_last_value(values, horizon=3)
        assert result == [3.0, 3.0, 3.0]

    def test_single_value(self):
        """Works with single-value series."""
        values = [5.0]
        result = forecast_last_value(values, horizon=2)
        assert result == [5.0, 5.0]

    def test_empty_series_raises(self):
        """Raises ValueError for empty series."""
        with pytest.raises(ValueError, match="at least 1 value"):
            forecast_last_value([], horizon=1)


class TestRollingForecastLastValue:
    """Test the rolling_forecast_last_value function."""

    def test_rolling_predictions(self):
        """Produces correct one-step-ahead predictions."""
        values = [1.0, 2.0, 3.0, 4.0]
        result = rolling_forecast_last_value(values)
        assert result == [1.0, 2.0, 3.0]


class TestForecastRunCLI:
    """Test the forecast run command accepts both method names."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def setup_series(self, runner):
        """Create a test series."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "test", "1,2,3,4,5"])
            yield

    def test_run_with_last_value(self, runner, setup_series):
        """'--method last-value' works and shows 'last-value' in output."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "test", "1,2,3,4,5"])
            result = runner.invoke(
                main,
                ["forecast", "run", "--series", "test", "--method", "last-value", "--horizon", "2"],
            )
            assert result.exit_code == 0
            assert "last-value" in result.output
            assert "naive" not in result.output

    def test_run_with_naive_alias(self, runner, setup_series):
        """'--method naive' works as alias and shows 'last-value' in output."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "test", "1,2,3,4,5"])
            result = runner.invoke(
                main, ["forecast", "run", "--series", "test", "--method", "naive", "--horizon", "2"]
            )
            assert result.exit_code == 0
            assert "last-value" in result.output


class TestForecastEvaluateCLI:
    """Test the forecast evaluate command accepts both method names."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_evaluate_with_last_value(self, runner):
        """'--method last-value' works and shows 'last-value' in output."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "test", "1,2,3,4,5"])
            result = runner.invoke(
                main, ["forecast", "evaluate", "--series", "test", "--method", "last-value"]
            )
            assert result.exit_code == 0
            assert "last-value" in result.output
            assert "naive" not in result.output

    def test_evaluate_with_naive_alias(self, runner):
        """'--method naive' works as alias and shows 'last-value' in output."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["series", "add", "test", "1,2,3,4,5"])
            result = runner.invoke(
                main, ["forecast", "evaluate", "--series", "test", "--method", "naive"]
            )
            assert result.exit_code == 0
            assert "last-value" in result.output
