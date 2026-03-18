# Task 07 - Improvement: Regression Method

Add a stronger baseline forecast option.

## Requirements
- Add forecast method `linear-regression` for one-dimensional sequences.
- Support:
  - `forecast run --method linear-regression`
  - `forecast evaluate --method linear-regression`
- Use index positions as x-values and series values as y-values.
- Document behavior for very short series.

## Constraints
- Keep implementation numerical stable for typical small/medium datasets.
- Preserve previous forecast methods.

## Acceptance Criteria
- Regression method returns sensible predictions.
- Evaluation includes regression in the same MAE/RMSE framework.
