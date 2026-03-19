# Application: KNN Regression CLI

## Purpose
Build a local command-line tool for dataset-based numeric prediction using k-nearest-neighbors regression. The tool should let a user create a dataset, load observations from CSV files, and request predictions for new observations from CSV input.

## Objectives
- Provide a clear CLI workflow for:
  - creating a dataset
  - loading training observations from CSV
  - generating predictions for query observations from CSV
- Support reliable experimentation on medium-scale tabular data.
- Produce deterministic behavior for repeatable evaluation when the same data and settings are used.
- Keep output and errors clear so users can diagnose data and command issues quickly.

## Constraints / Requirements
- Language and dependencies:
  - Python with NumPy is allowed.
  - No other math/scientific libraries are allowed.
  - No external KNN libraries are allowed.
- Scale target:
  - Must handle training on 10,000 observations with 100 numeric features.
  - Must handle prediction on an additional 10,000 observations with 100 numeric features.
- CLI contract (required):
  1. `create --dataset <name> --dimension <int>`
  2. `add-csv --dataset <name> --file <train_csv>`
  3. `query-csv --dataset <name> --file <test_csv> --output <pred_csv>`
- Repeated command support (required):
  - `add-csv` must support being called multiple times for the same dataset, appending new observations each time.
  - `query-csv` must support being called multiple times for the same dataset and produce correct predictions on each call.
- CSV interoperability:
  - Training CSV contains feature columns plus target values.
  - Query CSV contains feature columns only.
  - Prediction CSV contains one numeric prediction per row (header optional).
- Reliability:
  - Input validation must be explicit and actionable.
  - Invalid files/rows must fail clearly without silent corruption.
  - Command behavior must remain predictable across runs.
