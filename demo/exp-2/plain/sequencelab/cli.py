"""Command-line interface for SequenceLab."""

import csv
import random
from datetime import datetime
from pathlib import Path

import click

from sequencelab.models import Series, TransformMetadata
from sequencelab.storage import SeriesStore


def transform_diff(values: list[float]) -> list[float]:
    """Compute first difference of a series."""
    if len(values) < 2:
        raise ValueError("Series must have at least 2 values for diff operation")
    return [values[i + 1] - values[i] for i in range(len(values) - 1)]


def transform_moving_average(values: list[float], window: int) -> list[float]:
    """Compute moving average of a series."""
    if window < 2:
        raise ValueError("Window size must be at least 2")
    if window > len(values):
        raise ValueError(f"Window size ({window}) cannot exceed series length ({len(values)})")

    result = []
    for i in range(len(values) - window + 1):
        avg = sum(values[i : i + window]) / window
        result.append(avg)
    return result


def transform_normalize_minmax(values: list[float]) -> list[float]:
    """Normalize a series to [0, 1] range using min-max scaling."""
    if len(values) < 2:
        raise ValueError("Series must have at least 2 values for normalize-minmax operation")

    min_val = min(values)
    max_val = max(values)

    if min_val == max_val:
        raise ValueError("Cannot normalize: all values are identical (min equals max)")

    return [(v - min_val) / (max_val - min_val) for v in values]


def get_store() -> SeriesStore:
    """Get the default series store."""
    return SeriesStore()


def parse_values(values_str: str) -> list[float]:
    """Parse a comma-separated string of values into a list of floats."""
    if not values_str.strip():
        raise click.BadParameter("Values cannot be empty")

    parts = [p.strip() for p in values_str.split(",")]
    result = []
    for part in parts:
        try:
            result.append(float(part))
        except ValueError:
            raise click.BadParameter(f"'{part}' is not a valid number")
    return result


@click.group()
@click.version_option(package_name="sequencelab")
def main():
    """SequenceLab: Explore numeric sequences and simple models."""
    pass


@main.group()
def series():
    """Manage time-ordered numeric data series."""
    pass


@series.command(name="add")
@click.argument("name")
@click.argument("values")
def series_add(name: str, values: str):
    """Add a new series.

    NAME is the name for the series.
    VALUES is a comma-separated list of numbers (e.g., "1.0,2.5,3.7").
    """
    store = get_store()

    existing = store.get_by_name(name)
    if existing:
        raise click.ClickException(f"Series with name '{name}' already exists (id: {existing.id})")

    try:
        parsed_values = parse_values(values)
    except click.BadParameter as e:
        raise click.ClickException(str(e))

    s = Series(name=name, values=parsed_values)
    store.add(s)
    click.echo(f"Created series '{s.name}' with id {s.id}")


@series.command(name="list")
def series_list():
    """List all available series."""
    store = get_store()
    all_series = store.list_all()

    if not all_series:
        click.echo("No series found.")
        return

    click.echo(f"{'ID':<36}  {'Name':<20}  {'Values':<10}  Created")
    click.echo("-" * 90)
    for s in sorted(all_series, key=lambda x: x.created_at):
        created = s.created_at.strftime("%Y-%m-%d %H:%M")
        click.echo(f"{s.id:<36}  {s.name:<20}  {len(s.values):<10}  {created}")


@series.command(name="show")
@click.argument("identifier")
def series_show(identifier: str):
    """Show details of a series.

    IDENTIFIER can be a series ID or name.
    """
    store = get_store()
    s = store.find(identifier)

    if not s:
        raise click.ClickException(f"Series '{identifier}' not found")

    click.echo(f"ID:         {s.id}")
    click.echo(f"Name:       {s.name}")
    click.echo(f"Created:    {s.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    click.echo(f"Updated:    {s.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")

    if s.transform_metadata:
        click.echo(f"Derived:    Yes")
        source = store.get(s.transform_metadata.source_id)
        source_name = source.name if source else "(deleted)"
        click.echo(f"Source:     {source_name} ({s.transform_metadata.source_id})")
        click.echo(f"Operation:  {s.transform_metadata.operation}")
        if s.transform_metadata.arguments:
            args_str = ", ".join(f"{k}={v}" for k, v in s.transform_metadata.arguments.items())
            click.echo(f"Arguments:  {args_str}")

    click.echo(f"Values ({len(s.values)}):")
    for i, v in enumerate(s.values):
        click.echo(f"  [{i}] {v}")


@series.command(name="update")
@click.argument("identifier")
@click.option("--name", "-n", help="New name for the series")
@click.option("--values", "-v", help="New comma-separated values")
def series_update(identifier: str, name: str | None, values: str | None):
    """Update an existing series.

    IDENTIFIER can be a series ID or name.
    """
    if not name and not values:
        raise click.ClickException("Nothing to update. Provide --name or --values.")

    store = get_store()
    s = store.find(identifier)

    if not s:
        raise click.ClickException(f"Series '{identifier}' not found")

    if name:
        existing = store.get_by_name(name)
        if existing and existing.id != s.id:
            raise click.ClickException(
                f"Series with name '{name}' already exists (id: {existing.id})"
            )
        s.name = name

    if values:
        try:
            s.values = parse_values(values)
        except click.BadParameter as e:
            raise click.ClickException(str(e))

    s.updated_at = datetime.now()
    store.update(s)
    click.echo(f"Updated series '{s.name}' (id: {s.id})")


@series.command(name="delete")
@click.argument("identifier")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
def series_delete(identifier: str, force: bool):
    """Delete a series.

    IDENTIFIER can be a series ID or name.
    """
    store = get_store()
    s = store.find(identifier)

    if not s:
        raise click.ClickException(f"Series '{identifier}' not found")

    if not force:
        click.confirm(f"Delete series '{s.name}' (id: {s.id})?", abort=True)

    store.delete(s.id)
    click.echo(f"Deleted series '{s.name}' (id: {s.id})")


def parse_csv_value(value_str: str, line_num: int) -> float:
    """Parse a single CSV value string to float.

    Raises ValueError with line number on failure.
    """
    stripped = value_str.strip()
    if not stripped:
        raise ValueError(f"Line {line_num}: empty value")
    try:
        return float(stripped)
    except ValueError:
        raise ValueError(f"Line {line_num}: '{stripped}' is not a valid number")


def is_header_row(value: str) -> bool:
    """Check if the value looks like a header (non-numeric text)."""
    stripped = value.strip()
    if not stripped:
        return False
    try:
        float(stripped)
        return False
    except ValueError:
        return True


@series.command(name="import-csv")
@click.option("--name", required=True, help="Name for the imported series")
@click.option(
    "--file",
    "filepath",
    required=True,
    type=click.Path(exists=True),
    help="Path to CSV file to import",
)
def series_import_csv(name: str, filepath: str):
    """Import a series from a CSV file.

    CSV format: one numeric value per line. An optional header row is detected
    and skipped if the first line is non-numeric.

    The import is atomic: if any row is malformed, no series is created.
    """
    store = get_store()

    existing = store.get_by_name(name)
    if existing:
        raise click.ClickException(f"Series with name '{name}' already exists (id: {existing.id})")

    path = Path(filepath)
    values: list[float] = []
    errors: list[str] = []

    try:
        with open(path, "r", newline="") as f:
            reader = csv.reader(f)
            line_num = 0
            skip_header = False

            for row in reader:
                line_num += 1

                if not row or all(cell.strip() == "" for cell in row):
                    continue

                cell = row[0]

                if line_num == 1 and is_header_row(cell):
                    skip_header = True
                    continue

                try:
                    value = parse_csv_value(cell, line_num)
                    values.append(value)
                except ValueError as e:
                    errors.append(str(e))

    except OSError as e:
        raise click.ClickException(f"Failed to read file: {e}")

    if errors:
        error_msg = "CSV validation failed:\n" + "\n".join(f"  {err}" for err in errors)
        raise click.ClickException(error_msg)

    if not values:
        raise click.ClickException("CSV file contains no valid numeric values")

    s = Series(name=name, values=values)
    store.add(s)
    click.echo(f"Imported series '{s.name}' with id {s.id}")
    click.echo(f"  Values: {len(values)}")


@series.command(name="export-csv")
@click.option("--series", "identifier", required=True, help="Series ID or name to export")
@click.option(
    "--file", "filepath", required=True, type=click.Path(), help="Path to output CSV file"
)
def series_export_csv(identifier: str, filepath: str):
    """Export a series to a CSV file.

    Output format: one numeric value per line with a 'value' header.
    Values are written with full floating-point precision to ensure
    round-trip fidelity when re-imported.
    """
    store = get_store()
    s = store.find(identifier)

    if not s:
        raise click.ClickException(f"Series '{identifier}' not found")

    path = Path(filepath)

    try:
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["value"])
            for v in s.values:
                writer.writerow([repr(v)])
    except OSError as e:
        raise click.ClickException(f"Failed to write file: {e}")

    click.echo(f"Exported series '{s.name}' to {filepath}")
    click.echo(f"  Values: {len(s.values)}")


VALID_OPERATIONS = ["diff", "moving-average", "normalize-minmax"]


def reject_overwrite_option(ctx, param, value):
    """Callback to reject deprecated overwrite flags with migration guidance."""
    if value:
        raise click.ClickException(
            f"The '{param.opts[0]}' option has been removed. "
            "Transforms now always create a new derived series to protect source data. "
            "Use --name to specify a custom name for the output series."
        )
    return value


@series.command(name="transform")
@click.option("--series", "identifier", required=True, help="Source series ID or name")
@click.option(
    "--op",
    "operation",
    required=True,
    type=click.Choice(VALID_OPERATIONS),
    help="Transformation operation to apply",
)
@click.option(
    "--window",
    type=int,
    default=None,
    help="Window size for moving-average operation (required, must be >= 2)",
)
@click.option(
    "--name",
    "output_name",
    default=None,
    help="Name for the derived series (defaults to '<source>_<operation>')",
)
@click.option(
    "--overwrite",
    is_flag=True,
    hidden=True,
    expose_value=False,
    callback=reject_overwrite_option,
    is_eager=True,
    help="REMOVED: This option is no longer supported.",
)
@click.option(
    "--in-place",
    is_flag=True,
    hidden=True,
    expose_value=False,
    callback=reject_overwrite_option,
    is_eager=True,
    help="REMOVED: This option is no longer supported.",
)
def series_transform(identifier: str, operation: str, window: int | None, output_name: str | None):
    """Transform a series and create a new derived series.

    Applies the specified operation to create a new series. The original
    series remains unchanged.

    Operations:
      - diff: First difference (y[i] = x[i+1] - x[i])
      - moving-average: Rolling mean (requires --window)
      - normalize-minmax: Scale values to [0, 1] range
    """
    store = get_store()
    source = store.find(identifier)

    if not source:
        raise click.ClickException(f"Series '{identifier}' not found")

    if len(source.values) == 0:
        raise click.ClickException(f"Series '{source.name}' is empty")

    arguments: dict = {}

    try:
        if operation == "diff":
            transformed_values = transform_diff(source.values)
        elif operation == "moving-average":
            if window is None:
                raise click.ClickException("--window is required for moving-average operation")
            if window < 2:
                raise click.ClickException("Window size must be at least 2")
            arguments["window"] = window
            transformed_values = transform_moving_average(source.values, window)
        elif operation == "normalize-minmax":
            transformed_values = transform_normalize_minmax(source.values)
        else:
            raise click.ClickException(f"Unknown operation: {operation}")
    except ValueError as e:
        raise click.ClickException(str(e))

    derived_name = output_name or f"{source.name}_{operation}"

    existing = store.get_by_name(derived_name)
    if existing:
        raise click.ClickException(
            f"Series with name '{derived_name}' already exists (id: {existing.id}). "
            "Use --name to specify a different name."
        )

    metadata = TransformMetadata(
        source_id=source.id,
        operation=operation,
        arguments=arguments,
    )

    derived = Series(
        name=derived_name,
        values=transformed_values,
        transform_metadata=metadata,
    )

    store.add(derived)
    click.echo(f"Created derived series '{derived.name}' with id {derived.id}")
    click.echo(f"  Source: {source.name} ({source.id})")
    click.echo(f"  Operation: {operation}")
    if arguments:
        args_str = ", ".join(f"{k}={v}" for k, v in arguments.items())
        click.echo(f"  Arguments: {args_str}")
    click.echo(f"  Values: {len(transformed_values)}")


@main.group()
def stats():
    """Statistical summaries and transformations."""
    pass


def compute_stats(values: list[float]) -> dict:
    """Compute descriptive statistics for a list of values."""
    n = len(values)
    mean = sum(values) / n

    sorted_values = sorted(values)
    if n % 2 == 0:
        median = (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2
    else:
        median = sorted_values[n // 2]

    variance = sum((x - mean) ** 2 for x in values) / n
    std_dev = variance**0.5

    return {
        "count": n,
        "mean": mean,
        "median": median,
        "variance": variance,
        "std_dev": std_dev,
        "min": min(values),
        "max": max(values),
    }


@stats.command(name="describe")
@click.option("--series", "identifier", required=True, help="Series ID or name")
def stats_describe(identifier: str):
    """Show descriptive statistics for a series."""
    store = get_store()
    s = store.find(identifier)

    if not s:
        raise click.ClickException(f"Series '{identifier}' not found")

    if len(s.values) == 0:
        raise click.ClickException(f"Series '{s.name}' is empty")

    if len(s.values) < 2:
        raise click.ClickException(
            f"Series '{s.name}' has only {len(s.values)} value(s). "
            "At least 2 values are required for meaningful statistics."
        )

    result = compute_stats(s.values)

    click.echo(f"Statistics for series '{s.name}':")
    click.echo(f"  count:     {result['count']}")
    click.echo(f"  mean:      {result['mean']:.6f}")
    click.echo(f"  median:    {result['median']:.6f}")
    click.echo(f"  variance:  {result['variance']:.6f}")
    click.echo(f"  std_dev:   {result['std_dev']:.6f}")
    click.echo(f"  min:       {result['min']:.6f}")
    click.echo(f"  max:       {result['max']:.6f}")


@stats.command(name="zscore")
@click.option("--series", "identifier", required=True, help="Series ID or name")
def stats_zscore(identifier: str):
    """Print each value in a series with its z-score."""
    store = get_store()
    s = store.find(identifier)

    if not s:
        raise click.ClickException(f"Series '{identifier}' not found")

    if len(s.values) == 0:
        raise click.ClickException(f"Series '{s.name}' is empty")

    if len(s.values) < 2:
        raise click.ClickException(
            f"Series '{s.name}' has only {len(s.values)} value(s). "
            "At least 2 values are required to compute z-scores."
        )

    n = len(s.values)
    mean = sum(s.values) / n
    variance = sum((x - mean) ** 2 for x in s.values) / n
    std_dev = variance**0.5

    if std_dev == 0:
        raise click.ClickException(
            f"Series '{s.name}' has zero standard deviation (all values are identical). "
            "Z-scores cannot be computed."
        )

    click.echo(f"Z-scores for series '{s.name}':")
    click.echo(f"{'Index':<8}{'Value':<16}{'Z-Score':<16}")
    click.echo("-" * 40)
    for i, v in enumerate(s.values):
        z = (v - mean) / std_dev
        click.echo(f"{i:<8}{v:<16.6f}{z:<16.6f}")


FORECAST_METHODS = ["last-value", "moving-average", "linear-regression"]
FORECAST_METHOD_ALIASES = {"naive": "last-value"}


def resolve_forecast_method(method: str) -> str:
    """Resolve method name, handling deprecated aliases."""
    return FORECAST_METHOD_ALIASES.get(method, method)


def forecast_last_value(values: list[float], horizon: int) -> list[float]:
    """Last-value forecast: repeat the last observed value."""
    if len(values) == 0:
        raise ValueError("Series must have at least 1 value for last-value forecast")
    last_value = values[-1]
    return [last_value] * horizon


def forecast_moving_average(values: list[float], horizon: int, window: int) -> list[float]:
    """Moving average forecast: use trailing window average."""
    if len(values) < window:
        raise ValueError(
            f"Series must have at least {window} values for moving-average forecast with window={window}"
        )

    predictions = []
    extended_values = list(values)

    for _ in range(horizon):
        avg = sum(extended_values[-window:]) / window
        predictions.append(avg)
        extended_values.append(avg)

    return predictions


def compute_mae(actual: list[float], predicted: list[float]) -> float:
    """Compute Mean Absolute Error."""
    if len(actual) != len(predicted):
        raise ValueError("Actual and predicted lists must have the same length")
    if len(actual) == 0:
        raise ValueError("Cannot compute MAE on empty lists")
    return sum(abs(a - p) for a, p in zip(actual, predicted)) / len(actual)


def compute_rmse(actual: list[float], predicted: list[float]) -> float:
    """Compute Root Mean Squared Error."""
    if len(actual) != len(predicted):
        raise ValueError("Actual and predicted lists must have the same length")
    if len(actual) == 0:
        raise ValueError("Cannot compute RMSE on empty lists")
    mse = sum((a - p) ** 2 for a, p in zip(actual, predicted)) / len(actual)
    return mse**0.5


def compute_errors(actual: list[float], predicted: list[float]) -> list[float]:
    """Compute prediction errors (actual - predicted) for each pair."""
    if len(actual) != len(predicted):
        raise ValueError("Actual and predicted lists must have the same length")
    return [a - p for a, p in zip(actual, predicted)]


def mae_from_errors(errors: list[float]) -> float:
    """Compute MAE from a list of errors."""
    if len(errors) == 0:
        raise ValueError("Cannot compute MAE from empty list")
    return sum(abs(e) for e in errors) / len(errors)


def rmse_from_errors(errors: list[float]) -> float:
    """Compute RMSE from a list of errors."""
    if len(errors) == 0:
        raise ValueError("Cannot compute RMSE from empty list")
    mse = sum(e**2 for e in errors) / len(errors)
    return mse**0.5


def bootstrap_ci(
    errors: list[float],
    metric_fn,
    n_samples: int,
    ci_percent: float,
    seed: int | None = None,
) -> tuple[float, float, float]:
    """Compute bootstrap confidence interval for a metric.

    Returns (lower_bound, point_estimate, upper_bound).

    Args:
        errors: List of prediction errors
        metric_fn: Function to compute metric from errors (e.g., mae_from_errors)
        n_samples: Number of bootstrap resamples
        ci_percent: Confidence interval percentage (e.g., 95 for 95% CI)
        seed: Optional random seed for reproducibility
    """
    if n_samples < 1:
        raise ValueError("Bootstrap sample count must be at least 1")
    if not 0 < ci_percent < 100:
        raise ValueError("Confidence interval must be between 0 and 100 (exclusive)")
    if len(errors) == 0:
        raise ValueError("Cannot compute bootstrap CI from empty errors")

    if seed is not None:
        random.seed(seed)

    n = len(errors)
    bootstrap_estimates = []

    for _ in range(n_samples):
        resampled = [errors[random.randint(0, n - 1)] for _ in range(n)]
        bootstrap_estimates.append(metric_fn(resampled))

    bootstrap_estimates.sort()

    point_estimate = metric_fn(errors)

    alpha = (100 - ci_percent) / 100
    lower_idx = int((alpha / 2) * n_samples)
    upper_idx = int((1 - alpha / 2) * n_samples) - 1

    lower_idx = max(0, min(lower_idx, n_samples - 1))
    upper_idx = max(0, min(upper_idx, n_samples - 1))

    return bootstrap_estimates[lower_idx], point_estimate, bootstrap_estimates[upper_idx]


def rolling_forecast_last_value(values: list[float]) -> list[float]:
    """Generate one-step-ahead predictions using last-value method."""
    return values[:-1]


def rolling_forecast_moving_average(values: list[float], window: int) -> list[float]:
    """Generate one-step-ahead predictions using moving average method."""
    if len(values) < window + 1:
        raise ValueError(
            f"Series must have at least {window + 1} values for moving-average evaluation with window={window}"
        )

    predictions = []
    for i in range(window, len(values)):
        avg = sum(values[i - window : i]) / window
        predictions.append(avg)

    return predictions


def fit_linear_regression(x: list[float], y: list[float]) -> tuple[float, float]:
    """Fit a simple linear regression y = slope * x + intercept.

    Uses ordinary least squares with numerically stable computation.
    Returns (slope, intercept).
    """
    n = len(x)
    if n != len(y):
        raise ValueError("x and y must have the same length")
    if n < 2:
        raise ValueError("At least 2 points are required for linear regression")

    x_mean = sum(x) / n
    y_mean = sum(y) / n

    numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
    denominator = sum((xi - x_mean) ** 2 for xi in x)

    if denominator == 0:
        slope = 0.0
    else:
        slope = numerator / denominator

    intercept = y_mean - slope * x_mean
    return slope, intercept


def forecast_linear_regression(values: list[float], horizon: int) -> list[float]:
    """Linear regression forecast: fit trend line and extrapolate.

    Uses index positions (0, 1, 2, ...) as x-values and series values as y-values.
    For series with fewer than 2 values, raises an error since regression requires
    at least 2 points to fit a line.
    """
    if len(values) < 2:
        raise ValueError(
            "Series must have at least 2 values for linear-regression forecast. "
            "Linear regression requires at least 2 points to fit a trend line."
        )

    x = list(range(len(values)))
    y = values
    slope, intercept = fit_linear_regression(x, y)

    predictions = []
    start_idx = len(values)
    for i in range(horizon):
        pred = slope * (start_idx + i) + intercept
        predictions.append(pred)

    return predictions


def rolling_forecast_linear_regression(values: list[float]) -> list[float]:
    """Generate one-step-ahead predictions using linear regression.

    For each position i >= 2, fits a regression on values[0:i] and predicts values[i].
    Requires at least 3 values (2 for initial fit, 1 for first prediction).
    """
    if len(values) < 3:
        raise ValueError(
            "Series must have at least 3 values for linear-regression evaluation. "
            "Need at least 2 points to fit initial model and 1 point to evaluate."
        )

    predictions = []
    for i in range(2, len(values)):
        x = list(range(i))
        y = values[:i]
        slope, intercept = fit_linear_regression(x, y)
        pred = slope * i + intercept
        predictions.append(pred)

    return predictions


@main.group()
def forecast():
    """Forecasting tools and error reporting."""
    pass


@forecast.command(name="run")
@click.option("--series", "identifier", required=True, help="Series ID or name")
@click.option(
    "--method",
    "method",
    required=True,
    type=click.Choice(FORECAST_METHODS + list(FORECAST_METHOD_ALIASES.keys())),
    help="Forecasting method to use (last-value, moving-average, or linear-regression)",
)
@click.option(
    "--horizon", "horizon", required=True, type=int, help="Number of steps to forecast ahead"
)
@click.option(
    "--window", type=int, default=3, help="Window size for moving-average method (default: 3)"
)
def forecast_run(identifier: str, method: str, horizon: int, window: int):
    """Run a forecast on a series.

    Generate predicted values for future time steps using the specified method.

    Methods:
      - last-value: Repeat the last observed value
      - moving-average: Use trailing window average (requires --window)
      - linear-regression: Fit trend line and extrapolate (requires >= 2 values)
    """
    store = get_store()
    s = store.find(identifier)

    if not s:
        raise click.ClickException(f"Series '{identifier}' not found")

    if len(s.values) == 0:
        raise click.ClickException(f"Series '{s.name}' is empty")

    if horizon < 1:
        raise click.ClickException("Horizon must be at least 1")

    resolved_method = resolve_forecast_method(method)

    if resolved_method == "moving-average" and window < 1:
        raise click.ClickException("Window must be at least 1")

    try:
        if resolved_method == "last-value":
            predictions = forecast_last_value(s.values, horizon)
        elif resolved_method == "moving-average":
            predictions = forecast_moving_average(s.values, horizon, window)
        elif resolved_method == "linear-regression":
            predictions = forecast_linear_regression(s.values, horizon)
        else:
            raise click.ClickException(f"Unknown method: {resolved_method}")
    except ValueError as e:
        raise click.ClickException(str(e))

    click.echo(f"Forecast for series '{s.name}' using {resolved_method}:")
    click.echo(f"  Horizon: {horizon} step(s)")
    if resolved_method == "moving-average":
        click.echo(f"  Window: {window}")
    click.echo(f"Predicted values:")
    start_idx = len(s.values)
    for i, pred in enumerate(predictions):
        click.echo(f"  [{start_idx + i}] {pred:.6f}")


@forecast.command(name="evaluate")
@click.option("--series", "identifier", required=True, help="Series ID or name")
@click.option(
    "--method",
    "method",
    required=True,
    type=click.Choice(FORECAST_METHODS + list(FORECAST_METHOD_ALIASES.keys())),
    help="Forecasting method to evaluate (last-value, moving-average, or linear-regression)",
)
@click.option(
    "--window", type=int, default=3, help="Window size for moving-average method (default: 3)"
)
@click.option(
    "--bootstrap-samples",
    type=int,
    default=None,
    help="Number of bootstrap samples for confidence intervals",
)
@click.option(
    "--ci",
    "ci_percent",
    type=float,
    default=95.0,
    help="Confidence interval percentage (default: 95)",
)
@click.option(
    "--seed", type=int, default=None, help="Random seed for reproducible bootstrap sampling"
)
def forecast_evaluate(
    identifier: str,
    method: str,
    window: int,
    bootstrap_samples: int | None,
    ci_percent: float,
    seed: int | None,
):
    """Evaluate a forecasting method using rolling one-step prediction.

    Computes error metrics by making one-step-ahead predictions at each point
    in the series and comparing against actual values.

    Reports:
      - MAE (Mean Absolute Error)
      - RMSE (Root Mean Squared Error)

    Optionally, use --bootstrap-samples to compute confidence intervals via
    bootstrap resampling. Use --ci to specify the confidence level (default 95%).
    Use --seed for deterministic results.
    """
    store = get_store()
    s = store.find(identifier)

    if not s:
        raise click.ClickException(f"Series '{identifier}' not found")

    if len(s.values) == 0:
        raise click.ClickException(f"Series '{s.name}' is empty")

    resolved_method = resolve_forecast_method(method)

    if resolved_method == "moving-average" and window < 1:
        raise click.ClickException("Window must be at least 1")

    if bootstrap_samples is not None:
        if bootstrap_samples < 1:
            raise click.ClickException("Bootstrap sample count must be at least 1")
        if not 0 < ci_percent < 100:
            raise click.ClickException("Confidence interval must be between 0 and 100 (exclusive)")

    try:
        if resolved_method == "last-value":
            if len(s.values) < 2:
                raise click.ClickException(
                    f"Series '{s.name}' must have at least 2 values for last-value evaluation"
                )
            predictions = rolling_forecast_last_value(s.values)
            actual = s.values[1:]
        elif resolved_method == "moving-average":
            predictions = rolling_forecast_moving_average(s.values, window)
            actual = s.values[window:]
        elif resolved_method == "linear-regression":
            predictions = rolling_forecast_linear_regression(s.values)
            actual = s.values[2:]
        else:
            raise click.ClickException(f"Unknown method: {resolved_method}")

        mae = compute_mae(actual, predictions)
        rmse = compute_rmse(actual, predictions)

        mae_ci = None
        rmse_ci = None
        if bootstrap_samples is not None:
            errors = compute_errors(actual, predictions)
            mae_ci = bootstrap_ci(errors, mae_from_errors, bootstrap_samples, ci_percent, seed)
            rmse_ci = bootstrap_ci(errors, rmse_from_errors, bootstrap_samples, ci_percent, seed)
    except ValueError as e:
        raise click.ClickException(str(e))

    click.echo(f"Evaluation for series '{s.name}' using {resolved_method}:")
    if resolved_method == "moving-average":
        click.echo(f"  Window: {window}")
    click.echo(f"  Predictions: {len(predictions)}")
    click.echo(f"Error metrics:")
    if bootstrap_samples is not None:
        click.echo(f"  MAE:  {mae:.6f}  [{ci_percent:.0f}% CI: {mae_ci[0]:.6f} - {mae_ci[2]:.6f}]")
        click.echo(
            f"  RMSE: {rmse:.6f}  [{ci_percent:.0f}% CI: {rmse_ci[0]:.6f} - {rmse_ci[2]:.6f}]"
        )
    else:
        click.echo(f"  MAE:  {mae:.6f}")
        click.echo(f"  RMSE: {rmse:.6f}")


if __name__ == "__main__":
    main()
