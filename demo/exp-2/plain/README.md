# SequenceLab

A command-line application for exploring numeric sequences and simple models.

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the CLI:

```bash
python -m sequencelab --help
```

### Available Commands

- `series` - Manage time-ordered numeric data series
- `stats` - Statistical summaries and transformations
- `forecast` - Forecasting tools and error reporting

Example:

```bash
python -m sequencelab series --help
python -m sequencelab stats --help
python -m sequencelab forecast --help
```

## Transforms

The `series transform` command applies transformations to create new derived series.
Transforms always produce a new series with a new ID - the source series is never modified.

```bash
python -m sequencelab series transform --series my_data --op diff --name my_data_diff
```

**Note:** The `--overwrite` and `--in-place` options have been removed to protect source data.
Use `--name` to specify a custom name for the output series.
